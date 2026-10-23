import pandas as pd
import requests
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
st.caption("Consulta interna, busca inteligente via Google Maps e cadastro operacional")

tab_consulta, tab_google, tab_cadastro = st.tabs(
    ["Consultar Banco Interno", "🔍 Buscar no Google Maps", "Cadastrar Manualmente"]
)

# --- ABA 1: CONSULTAR BANCO INTERNO ---
with tab_consulta:
    st.subheader("Pesquisar fornecedores cadastrados")
    col_categoria, col_cidade = st.columns(2)
    filtro_categoria = col_categoria.selectbox(
        "Categoria", ["Todas", *categorias], key="supplier_category_filter"
    )
    filtro_cidade = col_cidade.text_input(
        "Cidade", placeholder="Ex.: Macaé", key="supplier_city_filter"
    )

    if st.button("Buscar no Banco", type="primary", key="supplier_search"):
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

# --- ABA 2: BUSCAR NO GOOGLE MAPS (PLACES API NEW) ---
with tab_google:
    st.subheader("Buscar fornecedores locais via Google Places (New)")
    st.caption("Localize estabelecimentos locais com filtro automático de avaliação superior a 4.0 estrelas.")

    api_key = st.secrets.get("GOOGLE_MAPS_API_KEY", None)

    if not api_key:
        st.warning(
            "⚠️ A chave `GOOGLE_MAPS_API_KEY` não foi configurada nos segredos do Streamlit. "
            "Adicione-a no `secrets.toml` para ativar a busca externa."
        )

    col_g_cidade, col_g_termo, col_g_cat = st.columns([2, 2, 2])
    g_cidade = col_g_cidade.text_input("Cidade / Porto Base *", placeholder="Ex.: Macaé, RJ", key="g_city")
    g_termo = col_g_termo.text_input("Serviço / Termo de Busca *", placeholder="Ex.: Mecânica Naval, Tornearia", key="g_term")
    g_categoria = col_g_cat.selectbox("Categoria para Salvar", categorias, key="g_cat")

    min_rating = st.slider("Avaliação Mínima do Google (Estrelas)", min_value=3.5, max_value=5.0, value=4.0, step=0.1)

    if st.button("Buscar no Google Maps", type="primary", key="g_search_btn"):
        if not g_cidade.strip() or not g_termo.strip():
            st.warning("Preencha a cidade e o termo de busca.")
        elif not api_key:
            st.error("Chave de API do Google Maps ausente.")
        else:
            with st.spinner("Consultando estabelecimentos na Places API (New)..."):
                try:
                    # Endpoint moderno da Places API (New)
                    url = "https://places.googleapis.com/v1/places:searchText"
                    headers = {
                        "Content-Type": "application/json",
                        "X-Goog-Api-Key": api_key,
                        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.googleMapsUri",
                    }
                    payload = {
                        "textQuery": f"{g_termo.strip()} em {g_cidade.strip()}",
                        "languageCode": "pt-BR",
                    }

                    response = requests.post(url, json=payload, headers=headers, timeout=10)
                    data = response.json()

                    if response.status_code == 200:
                        raw_results = data.get("places", [])
                        filtered_places = [
                            p for p in raw_results if p.get("rating", 0) >= min_rating
                        ]
                        st.session_state["g_places_results"] = filtered_places
                        st.session_state["g_search_city"] = g_cidade.strip()
                        st.session_state["g_search_cat"] = g_categoria
                    else:
                        error_msg = data.get("error", {}).get("message", response.text)
                        st.error(f"Erro na API do Google ({response.status_code}): {error_msg}")
                except Exception as e:
                    st.error(f"Erro na conexão com o Google Maps: {e}")

    # Exibição dos resultados mantidos no session_state
    if "g_places_results" in st.session_state:
        results = st.session_state["g_places_results"]
        if results:
            st.success(f"Encontrados **{len(results)}** estabelecimentos com avaliação ≥ {min_rating} ⭐!")
            st.markdown("---")

            for idx, place in enumerate(results):
                nome_place = place.get("displayName", {}).get("text", "Sem Nome")
                rating_place = place.get("rating", "N/A")
                total_ratings = place.get("userRatingCount", 0)
                address_place = place.get("formattedAddress", "")
                place_id = place.get("id", "")
                maps_link = place.get("googleMapsUri", f"https://www.google.com/maps/place/?q=place_id:{place_id}")

                with st.container(border=True):
                    c_info, c_action = st.columns([3, 1])
                    with c_info:
                        st.markdown(f"#### {nome_place}")
                        st.markdown(f"⭐ **{rating_place} / 5.0** ({total_ratings} avaliações no Google)")
                        st.markdown(f"📍 **Endereço:** {address_place}")
                        if maps_link:
                            st.markdown(f"[🔗 Abrir no Google Maps]({maps_link})")

                    with c_action:
                        save_key = f"save_btn_{idx}_{place_id}"
                        if st.button("➕ Salvar no Banco", key=save_key):
                            payload = {
                                "nome": nome_place,
                                "categoria": st.session_state.get("g_search_cat", "Outros"),
                                "cidade": st.session_state.get("g_search_city", g_cidade.strip()),
                                "estado": "RJ",
                                "telefone": "",
                                "endereco_completo": address_place,
                                "link_google_maps": maps_link,
                                "observacoes_4sas": f"Importado do Google Maps (Nota: {rating_place} ⭐ com {total_ratings} avaliações).",
                            }
                            try:
                                supabase.table("fornecedores_operacionais").insert(payload).execute()
                                st.success(f"**{nome_place}** salvo no banco Supabase!")
                            except Exception as err:
                                st.error(f"Erro ao salvar no banco: {err}")
        else:
            st.info(f"Nenhum estabelecimento encontrado com nota superior a {min_rating} para essa busca.")

# --- ABA 3: CADASTRAR MANUALMENTE ---
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