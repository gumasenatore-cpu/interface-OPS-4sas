from datetime import datetime, timedelta
import json
import extra_streamlit_components as stx
import streamlit as st
from supabase import Client, create_client


AUTH_SESSION_KEY = "portal_auth_session"
AUTH_USER_KEY = "portal_authenticated_user"
AUTH_PENDING_ACTION_KEY = "portal_auth_pending_action"
AUTH_COOKIE_NAME = "4sas_portal_session"
AUTH_COOKIE_DAYS = 14


class SupabaseConfigurationError(RuntimeError):
    pass


def _get_cookie_manager(suffix: str = "main") -> stx.CookieManager:
    """
    Garante chave única caso seja instanciado em contextos diferentes no mesmo rerun.
    """
    counter_key = "_cookie_mgr_calls"
    call_idx = st.session_state.get(counter_key, 0)
    st.session_state[counter_key] = call_idx + 1
    return stx.CookieManager(key=f"portal_cookie_mgr_{suffix}_{call_idx}")


def create_supabase_client() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception as exc:
        raise SupabaseConfigurationError(
            "Configure SUPABASE_URL e SUPABASE_KEY nos secrets do Streamlit."
        ) from exc

    if not url or not key:
        raise SupabaseConfigurationError(
            "Configure SUPABASE_URL e SUPABASE_KEY nos secrets do Streamlit."
        )

    return create_client(url, key)


def _response_user(response, client: Client):
    user = getattr(response, "user", None)
    if user is None:
        session = getattr(response, "session", None)
        user = getattr(session, "user", None)
    if user is None:
        user_response = client.auth.get_user()
        user = getattr(user_response, "user", user_response)
    if user is None:
        raise ValueError("O Supabase não retornou um usuário para esta sessão.")
    return user


def _store_session(session, user, persist_cookie: bool = True) -> dict:
    if not session:
        raise ValueError("A sessão Supabase não foi criada.")

    session_data = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
    }
    st.session_state[AUTH_SESSION_KEY] = session_data

    if persist_cookie:
        try:
            cookie_mgr = _get_cookie_manager("write")
            expires_at = datetime.now() + timedelta(days=AUTH_COOKIE_DAYS)
            cookie_mgr.set(
                AUTH_COOKIE_NAME,
                json.dumps(session_data),
                expires_at=expires_at,
                key="set_auth_cookie_val",
            )
        except Exception:
            pass

    authenticated_user = {"id": str(user.id), "email": user.email or ""}
    st.session_state[AUTH_USER_KEY] = authenticated_user
    return authenticated_user


def sign_in(email: str, password: str) -> dict:
    client = create_supabase_client()
    response = client.auth.sign_in_with_password(
        {"email": email.strip(), "password": password}
    )
    session = getattr(response, "session", None)
    if not session:
        raise ValueError("Não foi possível iniciar uma sessão para esta conta.")

    user = _response_user(response, client)
    return _store_session(session, user, persist_cookie=True)


def accept_email_invitation(token_hash: str) -> dict:
    client = create_supabase_client()
    response = client.auth.verify_otp(
        {"token_hash": token_hash, "type": "invite"}
    )
    session = getattr(response, "session", None)
    if not session:
        raise ValueError("O convite não gerou uma sessão válida.")
    user = _response_user(response, client)
    return _store_session(session, user, persist_cookie=True)


def restore_session() -> dict | None:
    saved_session = st.session_state.get(AUTH_SESSION_KEY)

    # Só instancia o CookieManager se a sessão ainda não estiver carregada na memória
    if not isinstance(saved_session, dict):
        try:
            cookie_mgr = _get_cookie_manager("read")
            raw_cookie = cookie_mgr.get(cookie=AUTH_COOKIE_NAME)
            if raw_cookie:
                if isinstance(raw_cookie, dict):
                    saved_session = raw_cookie
                elif isinstance(raw_cookie, str):
                    saved_session = json.loads(raw_cookie)
        except Exception:
            saved_session = None

    if not isinstance(saved_session, dict) or not saved_session.get("refresh_token"):
        return None

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
        return _store_session(session, user, persist_cookie=token_changed)
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
        _store_session(session, user, persist_cookie=token_changed)
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
    try:
        cookie_mgr = _get_cookie_manager("delete")
        cookie_mgr.delete(AUTH_COOKIE_NAME, key="del_auth_cookie_val")
    except Exception:
        pass


def require_user() -> dict:
    # Se o usuário já foi validado pelo app.py neste ciclo, retorna direto sem re-instanciar cookies
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