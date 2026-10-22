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

    return (
        f"Falha ao autenticar ({type(error).__name__}). "
        "Confirme se a conta existe no projeto configurado e está habilitada no Supabase Auth."
    )


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