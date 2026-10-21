import pandas as pd
import streamlit as st

from auth import authenticated_client, require_user, render_user_menu


current_user = require_user()
render_user_menu(current_user)

try:
    supabase = authenticated_client()
except Exception:
    st.error("Sua sessão expirou. Volte ao portal e entre novamente.")
    st.stop()

categorias = [
    "Náutica",
    "Elétrica/Ferragens",
    "Logística de Pessoal",
    "Barcos de Oportunidade",
    "Alimentação/Restaurante",
    "Frete Rodoviário",
    "Geradores/Máquinas",
    "Construção Civil",
    "Outros",
]

st.title("Banco de Fornecedores")
st.caption("Consulta e cadastro operacional")

tab_consulta, tab_cadastro = st.tabs(["Consultar", "Cadastrar"])

with tab_consulta:
    st.subheader("Pesquisar fornecedores")
    col_categoria, col_cidade = st.columns(2)
    filtro_categoria = col_categoria.selectbox(
        "Categoria", ["Todas", *categorias], key="supplier_category_filter"
    )
    filtro_cidade = col_cidade.text_input(
        "Cidade", placeholder="Ex.: Macaé", key="supplier_city_filter"
    )

    if st.button("Buscar", type="primary", key="supplier_search"):
        try:
            query = (
                supabase.table("fornecedores_operacionais")
                .select(
                    "id,nome,categoria,cidade,estado,telefone,endereco_completo,"
                    "link_google_maps,observacoes_4sas"
                )
                .order("nome")
                .limit(100)
            )
            if filtro_categoria != "Todas":
                query = query.eq("categoria", filtro_categoria)
            if filtro_cidade.strip():
                query = query.ilike("cidade", f"%{filtro_cidade.strip()}%")

            fornecedores = query.execute().data or []
            if fornecedores:
                df_fornecedores = pd.DataFrame(fornecedores).rename(
                    columns={
                        "id": "ID",
                        "nome": "Nome",
                        "categoria": "Categoria",
                        "cidade": "Cidade",
                        "estado": "UF",
                        "telefone": "Telefone",
                        "endereco_completo": "Endereço",
                        "link_google_maps": "Mapa",
                        "observacoes_4sas": "Observações internas",
                    }
                )
                st.dataframe(
                    df_fornecedores,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Mapa": st.column_config.LinkColumn("Mapa", display_text="Abrir mapa")
                    },
                )
                st.caption("Exibindo até 100 registros por busca.")
            else:
                st.info("Nenhum fornecedor encontrado para esses filtros.")
        except Exception:
            st.error("Não foi possível consultar a base. Verifique a configuração do banco.")

with tab_cadastro:
    st.subheader("Novo fornecedor")
    with st.form("supplier_registration", clear_on_submit=True):
        nome = st.text_input("Nome do estabelecimento ou contato *", max_chars=160)
        categoria = st.selectbox("Categoria *", categorias)
        col_cidade, col_estado, col_telefone = st.columns([2, 1, 2])
        cidade = col_cidade.text_input("Cidade / porto base *", max_chars=100)
        estado = col_estado.text_input("UF *", max_chars=2)
        telefone = col_telefone.text_input("Telefone / WhatsApp", max_chars=40)
        endereco = st.text_input("Endereço completo", max_chars=300)
        link_maps = st.text_input("Link do Google Maps", max_chars=500)
        observacoes = st.text_area("Observações internas", max_chars=2000)
        submitted = st.form_submit_button("Salvar fornecedor", type="primary")

    if submitted:
        if not all((nome.strip(), cidade.strip(), estado.strip())):
            st.warning("Preencha nome, cidade e UF.")
        elif link_maps and not link_maps.startswith(("https://", "http://")):
            st.warning("O link do mapa deve começar com http:// ou https://.")
        else:
            payload = {
                "nome": nome.strip(),
                "categoria": categoria,
                "cidade": cidade.strip(),
                "estado": estado.strip().upper(),
                "telefone": telefone.strip(),
                "endereco_completo": endereco.strip(),
                "link_google_maps": link_maps.strip(),
                "observacoes_4sas": observacoes.strip(),
            }
            try:
                supabase.table("fornecedores_operacionais").insert(payload).execute()
                st.success("Fornecedor cadastrado.")
            except Exception:
                st.error("Não foi possível salvar. Confirme se a tabela e as políticas RLS estão configuradas.")