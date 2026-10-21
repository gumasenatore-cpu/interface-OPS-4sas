import streamlit as st
import pandas as pd
import json
import os
import datetime
import copy
from gerador_pdf import criar_pdf_apr 

st.set_page_config(page_title="APR 4SAS - Gestão de Riscos", layout="wide")

if 'riscos_customizados' not in st.session_state:
    st.session_state.riscos_customizados = []

@st.cache_data
def load_data():
    try:
        with open('riscos_db_clean.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

riscos_db = load_data()

# --- BARRA LATERAL ---
col_espaco1, col_logo, col_espaco2 = st.sidebar.columns([1, 2, 1])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.markdown("### 4SAS")

st.sidebar.divider()

st.sidebar.header("1. Detalhes da Campanha")
colaborador = st.sidebar.text_input("Nome do Colaborador (Autor)", placeholder="Ex: Gustavo Senatore")
data_apr = st.sidebar.date_input("Data da APR", datetime.date.today())
os_num = st.sidebar.text_input("Número da OS", placeholder="Ex: 1045")
local = st.sidebar.text_input("Local da Operação", placeholder="Ex: Porto do Açu")

st.sidebar.header("2. Seleção de Equipamentos")
sensores = ["MBES", "SBES", "SVP", "SSS", "MAG", "SBP", "Sísmica Monocanal", "Sísmica Multicanal", "Vibro Core", "Jet Probe"]
selecao_sensores = st.sidebar.multiselect("Marque os sensores da OS:", sensores)

st.sidebar.header("3. Controle de Revisão")
historico_padrao = pd.DataFrame([
    {"Rev": 0, "Data": data_apr.strftime('%d/%m/%Y'), "Autor": colaborador if colaborador else "Autor", "Descrição": "Emissão Inicial"}
])
historico_df = st.sidebar.data_editor(historico_padrao, num_rows="dynamic", use_container_width=True)

# --- LÓGICA DE SEPARAÇÃO ---
riscos_gerais = []
riscos_especificos = {}

for r in riscos_db:
    tags = r.get("sensores_aplicaveis", ["Geral"])
    if "Geral" in tags:
        riscos_gerais.append(r)
    else:
        for s in selecao_sensores:
            if s in tags:
                r_copy = copy.deepcopy(r)
                r_copy['tarefa'] = f"[{s}] {r['tarefa']}"
                r_copy['id_unique'] = f"{r['id']}-{s}"
                if s not in riscos_especificos: riscos_especificos[s] = []
                riscos_especificos[s].append(r_copy)

# --- ÁREA PRINCIPAL ---
st.title("Análise Preliminar de Risco (APR)")

if os_num and local and colaborador and selecao_sensores:
    st.success(f"**Gestão Ativa:** {colaborador} | **OS:** {os_num} | **Local:** {local}")
    
    st.markdown("### Seleção e Controle Adicional de Riscos")
    riscos_selecionados_para_pdf = []
    
    st.subheader("🌐 Riscos Gerais (Aplicáveis a toda a operação)")
    fases_gerais = sorted(list(set([r['categoria_fase'] for r in riscos_gerais])))
    for fase in fases_gerais:
        with st.expander(f"Fase: {fase}", expanded=True):
            for risco in [r for r in riscos_gerais if r['categoria_fase'] == fase]:
                incluir = st.checkbox(f"**{risco['id']} - {risco['tarefa']}** (Nível Inicial {risco['risco_inicial']['nivel']})", value=True, key=f"chk_geral_{risco['id']}")
                if incluir:
                    # Campo dinâmico para preencher o Controle Adicional
                    controle_adicional = st.text_input("Controle Adicional (opcional):", value="N/A", key=f"ctrl_geral_{risco['id']}")
                    r_final = copy.deepcopy(risco)
                    r_final['mitigacao']['controle_adicional'] = controle_adicional
                    riscos_selecionados_para_pdf.append(r_final)
                    st.caption(f"**Perigo:** {risco['perigo']} | **Mitigação:** {risco['mitigacao']['medidas_padrao']}")

    if riscos_especificos:
        st.subheader("⚙️ Riscos Específicos por Equipamento")
        for sensor in selecao_sensores:
            if sensor in riscos_especificos:
                with st.expander(f"Equipamento: {sensor}", expanded=True):
                    for risco in riscos_especificos[sensor]:
                        incluir = st.checkbox(f"**{risco['id']} - {risco['tarefa']}** (Nível Inicial {risco['risco_inicial']['nivel']})", value=True, key=f"chk_esp_{risco['id_unique']}")
                        if incluir:
                            # Campo dinâmico para preencher o Controle Adicional
                            controle_adicional = st.text_input("Controle Adicional (opcional):", value="N/A", key=f"ctrl_esp_{risco['id_unique']}")
                            r_final = copy.deepcopy(risco)
                            r_final['mitigacao']['controle_adicional'] = controle_adicional
                            riscos_selecionados_para_pdf.append(r_final)
                            st.caption(f"**Perigo:** {risco['perigo']} | **Mitigação:** {risco['mitigacao']['medidas_padrao']}")

    st.divider()

    # --- ADICIONAR RISCO COM MATEMÁTICA ---
    st.subheader("Adicionar Risco Específico do Local")
    with st.expander("➕ Adicionar risco não mapeado"):
        with st.form("form_novo_risco", clear_on_submit=True):
            fase_custom = st.selectbox("Fase", ["1 - Preparação e Onshore", "2 - Mobilização", "3 - Operação", "4 - Desmobilização"])
            tarefa_c = st.text_input("Tarefa / Processo")
            perigo_c = st.text_area("Perigo Identificado")
            cons_c = st.text_input("Possíveis Consequências")
            
            st.markdown("##### Avaliação Inicial")
            col1, col2 = st.columns(2)
            sev_i = col1.number_input("Severidade Inicial (1-5)", 1, 5, 3)
            prob_i = col2.number_input("Probabilidade Inicial (1-5)", 1, 5, 3)
            
            mit_c = st.text_area("Medidas de Controle")
            adic_c = st.text_input("Projeto de Controle Adicional", value="N/A")
            resp_c = st.text_input("Responsável", value="Equipe")
            
            st.markdown("##### Avaliação Residual")
            col3, col4 = st.columns(2)
            sev_r = col3.number_input("Severidade Residual (1-5)", 1, 5, 1)
            prob_r = col4.number_input("Probabilidade Residual (1-5)", 1, 5, 1)
            
            if st.form_submit_button("Salvar Novo Risco"):
                if tarefa_c and perigo_c and mit_c:
                    novo_risco = {
                        "id": f"EXT-{len(st.session_state.riscos_customizados)+1}",
                        "categoria_fase": fase_custom,
                        "tarefa": tarefa_c,
                        "perigo": perigo_c,
                        "consequencias": cons_c,
                        "risco_inicial": {"severidade": sev_i, "probabilidade": prob_i, "nivel": sev_i * prob_i},
                        "mitigacao": {"medidas_padrao": mit_c, "controle_adicional": adic_c, "responsavel": resp_c},
                        "risco_residual": {"severidade": sev_r, "probabilidade": prob_r, "nivel": sev_r * prob_r},
                        "sensores_aplicaveis": ["Geral"]
                    }
                    st.session_state.riscos_customizados.append(novo_risco)
                    st.success("Risco adicionado!")
                    
    if st.session_state.riscos_customizados:
        for rc in st.session_state.riscos_customizados:
            riscos_selecionados_para_pdf.append(rc)
            
    st.divider()
    
    st.subheader("Finalizar Documentação")
    if st.button("📄 Gerar Relatório PDF da APR", use_container_width=True):
        with st.spinner("Desenhando Matriz de 14 colunas..."):
            historico_dict = historico_df.to_dict('records')
            try:
                pdf_bytes = criar_pdf_apr(os_num, local, selecao_sensores, riscos_selecionados_para_pdf, colaborador, data_apr.strftime('%d/%m/%Y'), historico_dict)
                st.download_button("📥 Baixar PDF Finalizado", data=pdf_bytes, file_name="APR_4SAS.pdf", mime='application/pdf', type="primary")
            except Exception as e:
                st.error(f"Erro: {e}")
else:
    st.info("👈 Preencha os dados básicos na barra lateral.")
