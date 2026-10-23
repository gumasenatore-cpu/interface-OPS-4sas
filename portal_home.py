import streamlit as st

from auth import require_user, render_user_menu


user = require_user()
render_user_menu(user)

st.title("Portal de Operações")
st.caption(f"Conectado como {user['email']}")
st.write("Selecione um módulo para continuar.")

col_boletim, col_apr, col_fornecedores, col_planejador = st.columns(4)

with col_boletim:
    st.subheader("Boletim")
    st.page_link(
        "pages/1_Boletim.py",
        label="Abrir boletim operacional",
        icon=":material/monitoring:",
        width="stretch",
    )

with col_apr:
    st.subheader("APR")
    st.page_link(
        "pages/2_APR.py",
        label="Abrir análise de risco",
        icon=":material/health_and_safety:",
        width="stretch",
    )

with col_fornecedores:
    st.subheader("Fornecedores")
    st.page_link(
        "pages/3_Fornecedores.py",
        label="Abrir banco de fornecedores",
        icon=":material/local_shipping:",
        width="stretch",
    )

with col_planejador:
    st.subheader("Planejador de Linhas")
    st.page_link(
        "pages/4_Planejador_Linhas.py",
        label="Abrir planejamento de linhas",
        icon=":material/map:",
        width="stretch",
    )