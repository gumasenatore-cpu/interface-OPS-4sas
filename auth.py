import streamlit as st
from supabase import Client, create_client


AUTH_SESSION_KEY = "portal_auth_session"
AUTH_USER_KEY = "portal_authenticated_user"


class SupabaseConfigurationError(RuntimeError):
    pass


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


def _store_session(session, user) -> dict:
    if not session:
        raise ValueError("A sessão Supabase não foi criada.")

    st.session_state[AUTH_SESSION_KEY] = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
    }
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
    return _store_session(session, user)


def restore_session() -> dict | None:
    saved_session = st.session_state.get(AUTH_SESSION_KEY)
    if not isinstance(saved_session, dict):
        return None

    try:
        client = create_supabase_client()
        response = client.auth.set_session(
            saved_session["access_token"], saved_session["refresh_token"]
        )
        session = getattr(response, "session", None)
        user = _response_user(response, client)
        return _store_session(session, user)
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
        _store_session(session, user)
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


def require_user() -> dict:
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