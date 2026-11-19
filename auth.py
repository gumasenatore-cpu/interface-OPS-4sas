from datetime import datetime, timedelta
import json
import extra_streamlit_components as stx
import streamlit as st
from supabase import Client, create_client


AUTH_SESSION_KEY = "portal_auth_session"
AUTH_USER_KEY = "portal_authenticated_user"
AUTH_PENDING_ACTION_KEY = "portal_auth_pending_action"
AUTH_COOKIE_SYNC_KEY = "portal_cookie_pending_sync"
AUTH_COOKIE_NAME = "4sas_portal_session"
AUTH_COOKIE_DAYS = 14


class SupabaseConfigurationError(RuntimeError):
    pass


def _get_cookie_manager(suffix: str = "main") -> stx.CookieManager:
    """Instancia o gerenciador de cookies com chave determinística por contexto."""
    return stx.CookieManager(key=f"portal_cookie_mgr_{suffix}")


def create_supabase_client() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception as exc:
        raise SupabaseConfigurationError(
            "Configure SUPABASE_URL e SUPABASE_KEY nos secrets do Streamlit."
        ) from exc

    if not isinstance(url, str) or not isinstance(key, str) or not url.strip() or not key.strip():
        raise SupabaseConfigurationError(
            "Credenciais SUPABASE_URL e SUPABASE_KEY inválidas nos secrets."
        )

    return create_client(url.strip(), key.strip())


def _response_user(response, client: Client):
    user = getattr(response, "user", None)
    if user is None:
        session = getattr(response, "session", None)
        user = getattr(session, "user", None)
    if user is None:
        user_response = client.auth.get_user()
        user = getattr(user_response, "user", user_response)
    if user is None:
        raise ValueError("O Supabase não retornou um usuário válido para esta sessão.")
    return user


def _store_session(session, user, defer_cookie: bool = True) -> dict:
    if not session:
        raise ValueError("A sessão Supabase não foi criada.")

    session_data = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
    }
    st.session_state[AUTH_SESSION_KEY] = session_data

    authenticated_user = {"id": str(user.id), "email": user.email or ""}
    st.session_state[AUTH_USER_KEY] = authenticated_user

    if defer_cookie:
        # Adia a escrita do cookie para o próximo render estável (evita aborto por st.rerun)
        st.session_state[AUTH_COOKIE_SYNC_KEY] = True
    else:
        sync_pending_cookie()

    return authenticated_user


def sync_pending_cookie() -> None:
    """Sincroniza o cookie no navegador após a transição de tela estabilizar."""
    if not st.session_state.get(AUTH_COOKIE_SYNC_KEY):
        return

    session_data = st.session_state.get(AUTH_SESSION_KEY)
    if not isinstance(session_data, dict):
        st.session_state.pop(AUTH_COOKIE_SYNC_KEY, None)
        return

    try:
        cookie_mgr = _get_cookie_manager("sync")
        expires_at = datetime.now() + timedelta(days=AUTH_COOKIE_DAYS)
        cookie_mgr.set(
            AUTH_COOKIE_NAME,
            json.dumps(session_data),
            expires_at=expires_at,
            key="set_auth_cookie_val",
        )
        st.session_state.pop(AUTH_COOKIE_SYNC_KEY, None)
    except Exception:
        # Mantém a sessão ativa em memória mesmo se o navegador bloquear cookies de terceiros
        st.session_state.pop(AUTH_COOKIE_SYNC_KEY, None)


def sign_in(email: str, password: str) -> dict:
    client = create_supabase_client()
    response = client.auth.sign_in_with_password(
        {"email": email.strip(), "password": password}
    )
    session = getattr(response, "session", None)
    if not session:
        raise ValueError("Não foi possível iniciar uma sessão para esta conta.")

    user = _response_user(response, client)
    return _store_session(session, user, defer_cookie=True)


def accept_email_invitation(token_hash: str) -> dict:
    client = create_supabase_client()
    response = client.auth.verify_otp(
        {"token_hash": token_hash, "type": "invite"}
    )
    session = getattr(response, "session", None)
    if not session:
        raise ValueError("O convite não gerou uma sessão válida.")
    user = _response_user(response, client)
    return _store_session(session, user, defer_cookie=True)


def restore_session() -> dict | None:
    saved_session = st.session_state.get(AUTH_SESSION_KEY)
    cached_user = st.session_state.get(AUTH_USER_KEY)

    # 1. Sessão já ativa na memória do Streamlit
    if isinstance(saved_session, dict) and isinstance(cached_user, dict):
        sync_pending_cookie()
        return cached_user

    # 2. Tentativa de recuperação via cookie persistido no navegador
    if not isinstance(saved_session, dict):
        try:
            cookie_mgr = _get_cookie_manager("read")
            raw_cookie = cookie_mgr.get(cookie=AUTH_COOKIE_NAME)
            if isinstance(raw_cookie, dict):
                saved_session = raw_cookie
            elif isinstance(raw_cookie, str) and raw_cookie.strip():
                saved_session = json.loads(raw_cookie)
        except Exception:
            saved_session = None

    if not isinstance(saved_session, dict) or not saved_session.get("refresh_token"):
        return None

    # 3. Revalidação do token junto ao Supabase Auth
    try:
        client = create_supabase_client()
        response = client.auth.set_session(
            saved_session["access_token"], saved_session["refresh_token"]
        )
        session = getattr(response, "session", None)
        user = _response_user(response, client)
        token_changed = (
            session is not None
            and session.refresh_token != saved_session.get("refresh_token")
        )
        return _store_session(session, user, defer_cookie=token_changed)
    except Exception:
        clear_session()
        return None


def authenticated_client() -> Client:
    saved_session = st.session_state.get(AUTH_SESSION_KEY)
    if not isinstance(saved_session, dict):
        raise PermissionError("É necessário entrar no portal.")

    client = create_supabase_client()
    try:
        response = client.auth.set_session(
            saved_session["access_token"], saved_session["refresh_token"]
        )
        session = getattr(response, "session", None)
        user = _response_user(response, client)
        token_changed = (
            session is not None
            and session.refresh_token != saved_session.get("refresh_token")
        )
        _store_session(session, user, defer_cookie=token_changed)
    except Exception as exc:
        clear_session()
        raise PermissionError("A sessão expirou. Entre novamente.") from exc
    return client


def sign_out() -> None:
    saved_session = st.session_state.get(AUTH_SESSION_KEY)
    if isinstance(saved_session, dict):
        try:
            client = create_supabase_client()
            client.auth.set_session(
                saved_session["access_token"], saved_session["refresh_token"]
            )
            client.auth.sign_out({"scope": "local"})
        except Exception:
            pass
    clear_session()


def clear_session() -> None:
    st.session_state.pop(AUTH_SESSION_KEY, None)
    st.session_state.pop(AUTH_USER_KEY, None)
    st.session_state.pop(AUTH_COOKIE_SYNC_KEY, None)
    try:
        cookie_mgr = _get_cookie_manager("delete")
        cookie_mgr.delete(AUTH_COOKIE_NAME, key="del_auth_cookie_val")
    except Exception:
        pass


def require_user() -> dict:
    cached_user = st.session_state.get(AUTH_USER_KEY)
    if isinstance(cached_user, dict) and st.session_state.get(AUTH_SESSION_KEY):
        return cached_user

    user = restore_session()
    if not user:
        st.error("Entre no portal para acessar esta página.")
        st.stop()
    return user


def render_user_menu(user: dict) -> None:
    st.sidebar.caption(f"Sessão: {user['email']}")
    if st.sidebar.button("Sair do portal", key="portal_sign_out"):
        sign_out()
        st.rerun()