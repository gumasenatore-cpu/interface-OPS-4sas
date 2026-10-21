import importlib
import gerador_pdf

# Força a atualização do gerador em tempo de execução
importlib.reload(gerador_pdf)

from gerador_pdf import criar_pdf_apr
import streamlit as st
import json
import datetime
from gerador_pdf import criar_pdf_apr 
from auth import require_user, render_user_menu

current_user = require_user()
render_user_menu(current_user)

@st.cache_data
def load_data():
    with open('riscos_db_clean.json', 'r', encoding='utf-8') as f:
        return json.load(f)

riscos_db = load_data()

# --- BARRA LATERAL ---
st.sidebar.title("4SAS Offshore")
st.sidebar.markdown("*Precisão além da superfície*")
st.sidebar.divider()

st.sidebar.header("1. Detalhes da Campanha")
colaborador = st.sidebar.text_input("Nome do Colaborador")
data_apr = st.sidebar.date_input("Data da APR", datetime.date.today())
os_num = st.sidebar.text_input("Número da OS")
local = st.sidebar.text_input("Local da Operação")

st.sidebar.header("2. Seleção de Equipamentos")
sensores = ["SBES", "MBES", "SSS", "MAG", "SBP", "Sísmica Monocanal", "Sísmica Multicanal", "Vibro Core", "Jet Probe"]
selecao_sensores = st.sidebar.multiselect("Marque os sensores da OS:", sensores)

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
            pdf_bytes = criar_pdf_apr(os_num, local, selecao_sensores, riscos_filtrados, colaborador, data_apr.strftime('%d/%m/%Y'))
            st.download_button(label="📥 Baixar PDF Finalizado", data=pdf_bytes, file_name="APR_4SAS.pdf", mime='application/pdf', type="primary")
else:
    st.info("👈 Preencha todos os dados na barra lateral (Colaborador, Data, OS, Local e Sensores) para carregar os riscos específicos.")