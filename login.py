import streamlit as st

from auth import SupabaseConfigurationError, sign_in


def login_error_message(error: Exception) -> str:
    details = " ".join(
        str(getattr(error, attribute, ""))
        for attribute in ("message", "code", "status_code")
    ).lower()

    if "email not confirmed" in details or "email_not_confirmed" in details:
        return "Confirme o e-mail da conta no Supabase ou peça ao administrador para verificá-la."
    if "rate limit" in details or "too many requests" in details:
        return "Muitas tentativas. Aguarde alguns minutos antes de tentar novamente."
    if "invalid login credentials" in details:
        return (
            "E-mail ou senha inválidos, ou a conta pertence a outro projeto Supabase. "
            "Confirme que SUPABASE_URL aponta para o projeto onde a conta foi criada."
        )
    return "Falha ao autenticar. Confirme a conta e o projeto Supabase configurado."


st.title("Portal de Operações 4SAS")
st.write("Acesse com a conta cadastrada no portal.")

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

st.caption("Problemas de acesso? Fale com o administrador do portal.")