import streamlit as st

from auth import restore_session


st.set_page_config(page_title="Portal 4SAS | Operações", page_icon="⚓", layout="wide")

if restore_session():
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
