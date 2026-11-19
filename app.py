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
    st.logo("assets/logo_4sas.png", size="large")
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

            h1, h2, h3, h4 {
                font-family: var(--portal-font) !important;
                letter-spacing: 0;
            }

            h1 { font-size: 1.75rem !important; }
            h2 { font-size: 1.35rem !important; }
            h3 { font-size: 1.1rem !important; }
            h4 { font-size: 1.05rem !important; margin-top: 0.2rem; margin-bottom: 0.4rem; }

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
        nav_position = "hidden"
    else:
        pg_inicio = st.Page(
            "pages/inicio.py",
            title="Início",
            icon=":material/home:",
            default=True,
        )

        # Grupo: Operação & Planejamento
        pg_boletim = st.Page(
            "pages/1_Boletim.py",
            title="1 - Boletim",
            icon=":material/monitoring:",
        )
        pg_linhas = st.Page(
            "pages/4_Planejador_Linhas.py",
            title="4 - Planejador de Linhas",
            icon=":material/map:",
        )

        # Grupo: Segurança & Campo
        pg_apr = st.Page(
            "pages/2_APR.py",
            title="2 - APR",
            icon=":material/health_and_safety:",
        )
        pg_checklist = st.Page(
            "pages/6_MobDesmob.py",
            title="6 - Checklist Mob/Demob",
            icon=":material/fact_check:",
        )

        # Grupo: Recursos & Apoio
        pg_fornecedores = st.Page(
            "pages/3_Fornecedores.py",
            title="3 - Fornecedores",
            icon=":material/local_shipping:",
        )
        pg_inventario = st.Page(
            "pages/5_Inventario.py",
            title="5 - Inventário & Manutenção",
            icon=":material/inventory_2:",
        )

        st.session_state["portal_pages"] = {
            "boletim": pg_boletim,
            "apr": pg_apr,
            "fornecedores": pg_fornecedores,
            "linhas": pg_linhas,
            "inventario": pg_inventario,
            "checklist": pg_checklist,
        }

        pages = {
            "": [pg_inicio],
            "Operação & Planejamento": [pg_boletim, pg_linhas],
            "Segurança & Campo": [pg_apr, pg_checklist],
            "Recursos & Apoio": [pg_fornecedores, pg_inventario],
        }
        nav_position = "top"
else:
    pages = [st.Page("login.py", title="Entrar", icon=":material/login:", default=True)]
    nav_position = "hidden"

st.navigation(pages, position=nav_position).run()