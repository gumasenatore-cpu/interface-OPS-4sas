import streamlit as st

from auth import (
    AUTH_PENDING_ACTION_KEY,
    authenticated_client,
    require_user,
)


if st.session_state.get(AUTH_PENDING_ACTION_KEY) != "invite":
    st.error("Esta etapa só pode ser acessada pelo link de convite enviado por e-mail.")
    st.stop()

user = require_user()
client = authenticated_client()

st.title("Defina sua senha")
st.write("Escolha uma senha para acessar o Portal de Operações 4SAS.")

with st.form("set_invited_user_password"):
    password = st.text_input("Nova senha", type="password", autocomplete="new-password")
    password_confirmation = st.text_input(
        "Confirme a nova senha", type="password", autocomplete="new-password"
    )
    submitted = st.form_submit_button("Salvar senha", type="primary")

if submitted:
    if len(password) < 10:
        st.error("Use uma senha com pelo menos 10 caracteres.")
    elif password != password_confirmation:
        st.error("As senhas não coincidem.")
    else:
        try:
            client.auth.update_user({"password": password})
            st.session_state.pop(AUTH_PENDING_ACTION_KEY, None)
            st.success("Senha definida. Abrindo o portal...")
            st.rerun()
        except Exception:
            st.error("Não foi possível salvar a senha. Solicite um novo convite ao administrador.")