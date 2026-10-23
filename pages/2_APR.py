import streamlit as st
import json
import datetime
import copy
import pandas as pd
from auth import require_user, render_user_menu
from gerador_pdf import criar_pdf_apr

current_user = require_user()
render_user_menu(current_user)

@st.cache_data
def load_data():
    with open('riscos_db_clean.json', 'r', encoding='utf-8') as f:
        return json.load(f)

riscos_db = load_data()

# --- BARRA LATERAL ---
st.sidebar.header("1. Detalhes da Campanha")
colaborador = st.sidebar.text_input("Nome do Colaborador")
data_apr = st.sidebar.date_input("Data da APR", datetime.date.today())
os_num = st.sidebar.text_input("Número da OS")
local = st.sidebar.text_input("Local da Operação")

st.sidebar.header("2. Seleção de Equipamentos")
sensores = ["SBES", "MBES", "SSS", "MAG", "SBP", "Sísmica Monocanal", "Sísmica Multicanal", "Vibro Core", "Jet Probe"]
selecao_sensores = st.sidebar.multiselect("Marque os sensores da OS:", sensores)

st.sidebar.header("3. Controle de Revisão")
historico_inicial = pd.DataFrame([
    {
        "Rev": 0,
        "Data": data_apr.strftime("%d/%m/%Y"),
        "Autor": colaborador or "Autor",
        "Descrição": "Emissão Inicial",
    }
])
historico_df = st.sidebar.data_editor(
    historico_inicial,
    num_rows="dynamic",
    use_container_width=True,
    key="apr_revision_history",
)

# Lógica de filtragem
riscos_filtrados = []
for r in riscos_db:
    tags = r.get("sensores_aplicaveis", ["Geral"])
    if "Geral" in tags:
        riscos_filtrados.append(r)
    elif any(sensor in tags for sensor in selecao_sensores):
        riscos_filtrados.append(r)

# --- ÁREA PRINCIPAL ---
st.title("Avaliação Preliminar de Risco (APR)")

if os_num and local and colaborador and selecao_sensores:
    st.success(f"**Colaborador:** {colaborador} | **Data:** {data_apr.strftime('%d/%m/%Y')} | **OS:** {os_num} | **Local:** {local}")
    
    fases = sorted(list(set([r['categoria_fase'] for r in riscos_filtrados])))
    aba_selecionada = st.selectbox("Selecione a Fase para Revisão de Riscos:", fases)
    
    st.markdown(f"### Riscos Mapeados: {aba_selecionada} ({len([r for r in riscos_filtrados if r['categoria_fase'] == aba_selecionada])} aplicáveis)")
    riscos_fase = [r for r in riscos_filtrados if r['categoria_fase'] == aba_selecionada]
    
    for risco in riscos_fase:
        with st.expander(f"{risco['id']} - {risco['tarefa']} | {risco['perigo']}"):
            st.write(f"**Possíveis Consequências:** {risco['consequencias']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.warning(f"🔴 **Risco Inicial:** Severidade {risco['risco_inicial']['severidade']} x Probabilidade {risco['risco_inicial']['probabilidade']} = Nível {risco['risco_inicial']['nivel']}")
                st.write("**Mitigação Padrão 4SAS:**")
                st.info(risco['mitigacao']['medidas_padrao'])
            
            with col2:
                st.success(f"🟢 **Risco Residual:** Severidade {risco['risco_residual']['severidade']} x Probabilidade {risco['risco_residual']['probabilidade']} = Nível {risco['risco_residual']['nivel']}")
                st.text_area("Adicionar controlo específico para esta campanha (Opcional):", key=f"obs_{risco['id']}")
    
    st.divider()
    st.subheader("Finalizar Documentação")
    if st.button("📄 Gerar Relatório PDF da APR", use_container_width=True):
        with st.spinner("A desenhar matriz de risco em PDF..."):
            riscos_para_pdf = copy.deepcopy(riscos_filtrados)
            for risco in riscos_para_pdf:
                mitigacao = risco.get("mitigacao", {})
                chave_controle = f"obs_{risco.get('id')}"
                controle_adicional = st.session_state.get(chave_controle)
                if not controle_adicional or not str(controle_adicional).strip():
                    controle_adicional = mitigacao.get("controle_adicional", "N/A")
                mitigacao["controle_adicional"] = controle_adicional
            pdf_bytes = criar_pdf_apr(
                os_num,
                local,
                selecao_sensores,
                riscos_para_pdf,
                colaborador,
                data_apr.strftime("%d/%m/%Y"),
                historico_df.to_dict("records"),
            )
            st.download_button(label="📥 Baixar PDF Finalizado", data=pdf_bytes, file_name="APR_4SAS.pdf", mime='application/pdf', type="primary")
else:
    st.info("👈 Preencha todos os dados na barra lateral (Colaborador, Data, OS, Local e Sensores) para carregar os riscos específicos.")