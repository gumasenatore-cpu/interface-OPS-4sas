import streamlit as st

from auth import (
    AUTH_PENDING_ACTION_KEY,
    accept_email_invitation,
    restore_session,
)


st.set_page_config(
    page_title="OPS - 4SAS | Portal",
    page_icon="assets/logo_4sas.png",
    layout="wide",
)

invite_token = st.query_params.get("token_hash")
invite_type = st.query_params.get("type")
if invite_token and invite_type == "invite":
    try:
        accept_email_invitation(invite_token)
        st.session_state[AUTH_PENDING_ACTION_KEY] = "invite"
        st.query_params.clear()
        st.rerun()
    except Exception:
        st.query_params.clear()
        st.error("Este convite é inválido ou expirou. Peça ao administrador para enviar outro.")
        st.stop()

user = restore_session()
if not user and st.session_state.get(AUTH_PENDING_ACTION_KEY):
    st.session_state.pop(AUTH_PENDING_ACTION_KEY, None)

if user:
    st.logo("assets/logo_4sas.png", size="small")
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

            :root {
                --portal-font: 'Carbona Variable', 'Inter', 'Segoe UI', sans-serif;
            }

            html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
                font-family: var(--portal-font) !important;
                font-size: 16px;
            }

            p, label, input, textarea, select, button,
            [data-testid="stSidebarNav"] a,
            [data-testid="stMarkdownContainer"] {
                font-family: var(--portal-font) !important;
                font-size: 0.875rem;
            }

            h1, h2, h3 {
                font-family: var(--portal-font) !important;
                letter-spacing: 0;
            }

            h1 { font-size: 1.75rem !important; }
            h2 { font-size: 1.35rem !important; }
            h3 { font-size: 1.1rem !important; }

            [data-testid="stCaptionContainer"] {
                font-family: var(--portal-font) !important;
                font-size: 0.75rem !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if st.session_state.get(AUTH_PENDING_ACTION_KEY) == "invite":
        pages = [
            st.Page(
                "set_password.py",
                title="Definir senha",
                icon=":material/key:",
                default=True,
            )
        ]
    else:
        pages = {
            "Portal": [
                st.Page("portal_home.py", title="Início", icon=":material/home:", default=True)
            ],
            "Operações": [
                st.Page("pages/1_Boletim.py", title="Boletim", icon=":material/monitoring:"),
                st.Page("pages/2_APR.py", title="APR", icon=":material/health_and_safety:"),
                st.Page(
                    "pages/3_Fornecedores.py",
                    title="Fornecedores",
                    icon=":material/local_shipping:",
                ),
            ],
        }
else:
    pages = [st.Page("login.py", title="Entrar", icon=":material/login:", default=True)]

st.navigation(pages, position="sidebar").run()
