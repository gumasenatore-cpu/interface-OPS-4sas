import base64
from pathlib import Path

import streamlit as st

from auth import SupabaseConfigurationError, sign_in


def login_error_message(error: Exception) -> str:
    details = " ".join(
        [
            str(error),
            *(str(getattr(error, attribute, "")) for attribute in ("message", "code", "status_code")),
        ]
    ).lower()

    if "email not confirmed" in details or "email_not_confirmed" in details:
        return "Confirme o e-mail da conta no Supabase ou peça ao administrador para verificá-la."
    if "rate limit" in details or "too many requests" in details:
        return "Muitas tentativas. Aguarde alguns minutos antes de tentar novamente."
    if "invalid login credentials" in details or "invalid_credentials" in details:
        return (
            "E-mail ou senha inválidos, ou a conta pertence a outro projeto Supabase. "
            "Confirme que SUPABASE_URL aponta para o projeto onde a conta foi criada."
        )
    if "invalid api key" in details or "invalid api-key" in details or "401" in details:
        return "A chave Supabase configurada foi recusada. Confira SUPABASE_KEY nos Secrets do app."
    if any(term in details for term in ("connecterror", "connectionerror", "timed out", "timeout")):
        return "Não foi possível alcançar o Supabase. Confira a URL e a conexão do app."
    if isinstance(error, AttributeError):
        message = str(error)
        missing_attribute = message.rsplit("'", 2)[1] if "'" in message else "desconhecido"
        return (
            f"Erro interno ao validar a sessão (atributo ausente: {missing_attribute}). "
            "Atualize o app e tente novamente."
        )

    return (
        f"Falha ao autenticar ({type(error).__name__}). "
        "Confirme se a conta existe no projeto configurado e está habilitada no Supabase Auth."
    )


st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        [data-testid="stAppViewContainer"] {
            background: #050505;
            color: #f5f5f5;
        }

        [data-testid="stHeader"],
        [data-testid="stSidebar"] {
            background: #050505;
        }

        [data-testid="stMainBlockContainer"] {
            max-width: none;
            padding: 0 1.25rem;
        }

        .st-key-login-shell {
            box-sizing: border-box;
            width: 100%;
            min-height: calc(100svh - 2rem);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            margin: 0 auto !important;
            padding: 0.5rem 0;
        }

        .st-key-login-brand {
            width: min(100%, 360px);
            margin-left: auto !important;
            margin-right: auto !important;
            align-items: center !important;
            text-align: center;
            margin-bottom: 0.75rem;
        }

        .login-wordmark {
            width: min(100%, 220px);
            margin: 0 auto;
        }

        .login-wordmark img {
            display: block;
            width: 100%;
            height: auto;
            object-fit: contain;
            border-radius: 2px;
        }

        .st-key-login-brand .login-title {
            margin: 0.6rem 0 0 !important;
            color: #ffffff;
            font-family: 'Carbona Variable', 'Inter', sans-serif;
            font-size: 1.2rem !important;
            font-weight: 400 !important;
            letter-spacing: 0;
            line-height: 1.3;
            text-align: center;
        }

        .st-key-login-panel {
            box-sizing: border-box;
            width: min(100%, 360px);
            margin-left: auto !important;
            margin-right: auto !important;
            padding: 1.05rem 1.2rem 0.9rem;
            border: 1px solid #303030;
            border-top: 3px solid #f32735;
            border-radius: 4px;
            background: #111111;
            box-shadow: 0 16px 40px rgba(0, 0, 0, 0.45);
        }

        .st-key-login-panel [data-testid="stForm"] {
            padding: 0;
            border: 0;
        }

        .st-key-login-panel label {
            color: #eeeeee;
        }

        .st-key-login-panel [data-testid="stTextInputRootElement"] {
            background: #1a1a1a !important;
            border-color: #444444 !important;
        }

        .st-key-login-panel [data-testid="stTextInputRootElement"] input {
            color: #ffffff;
            background: transparent;
        }

        .st-key-login-panel [data-testid="stTextInputRootElement"] button {
            color: #dddddd;
        }

        .st-key-login-panel [data-testid="stFormSubmitButton"] button {
            min-height: 2.8rem;
            background: #f32735;
            border-color: #f32735;
            color: #ffffff;
            font-weight: 600;
        }

        .login-help {
            width: min(100%, 360px);
            margin-top: 0.65rem;
            margin-left: auto !important;
            margin-right: auto !important;
            color: #a0a0a0;
            font-family: 'Carbona Variable', 'Inter', sans-serif;
            font-size: 0.82rem;
            text-align: center;
        }

        @media (max-width: 520px) {
            .st-key-login-shell {
                min-height: calc(100svh - 2rem);
            }

            .st-key-login-panel {
                padding: 0.9rem 0.9rem 0.75rem;
            }

            .login-wordmark {
                width: min(100%, 220px);
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="login-shell"):
    with st.container(key="login-brand"):
        wordmark_data = base64.b64encode(
            Path("assets/logo_4sas_wordmark.png").read_bytes()
        ).decode("ascii")
        st.markdown(
            f'<div class="login-wordmark"><img src="data:image/png;base64,{wordmark_data}" alt="4SAS"></div>'
            '<h1 class="login-title">OPERAÇÕES</h1>',
            unsafe_allow_html=True,
        )

    with st.container(key="login-panel", border=True):
        with st.form("portal_login"):
            email = st.text_input("E-mail", autocomplete="email")
            password = st.text_input(
                "Senha", type="password", autocomplete="current-password"
            )
            submitted = st.form_submit_button(
                "Entrar", type="primary", use_container_width=True
            )

        if submitted:
            try:
                sign_in(email, password)
                st.rerun()
            except SupabaseConfigurationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(login_error_message(exc))

    st.markdown(
        '<p class="login-help">Problemas de acesso? Fale com o administrador do portal.</p>',
        unsafe_allow_html=True,
    )