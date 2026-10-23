import streamlit as st

from auth import restore_session


st.set_page_config(
    page_title="OPS - 4SAS | Portal",
    page_icon="assets/logo_4sas.png",
    layout="wide",
)

if restore_session():
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
