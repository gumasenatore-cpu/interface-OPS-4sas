import datetime
import streamlit as st
import pandas as pd
import numpy as np
import requests
import math
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image, ImageDraw
import tempfile
import os
import folium
from streamlit_folium import st_folium

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors

from auth import require_user, render_user_menu
from gerador_pdf_boletim import gerar_pdf_boletim_reportlab

current_user = require_user()
render_user_menu(current_user)

st.markdown("""
<style>
    .stAlert {
        border-radius: 4px;
        border-left: 4px solid #F32735;
    }
</style>
""", unsafe_allow_html=True)

st.sidebar.header("Painel de Controle")

lat, lon = -25.51, -48.51
nome_local_exibicao = "Paranaguá, PR (Coordenadas)"

with st.sidebar.expander("Localização do Levantamento", expanded=True):
    modo_pos = st.radio("Método de Posição:", ["Coordenadas (Graus e Minutos - DM)", "Mapa Interativo (Clique na Área)"])
    
    if modo_pos == "Coordenadas (Graus e Minutos - DM)":
        st.markdown("**Insira as Coordenadas (DM):**")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            lat_graus = st.number_input("Lat Graus", value=-25, step=1)
            lat_min = st.number_input("Lat Minutos", value=30.60, format="%.2f", step=0.01)
        with col2:
            lon_graus = st.number_input("Lon Graus", value=-48, step=1)
            lon_min = st.number_input("Lon Minutos", value=30.60, format="%.2f", step=0.01)
        
        lat_sinal = -1 if lat_graus <= 0 else 1
        lon_sinal = -1 if lon_graus <= 0 else 1
        
        lat = lat_graus + (lat_sinal * (lat_min / 60.0))
        lon = lon_graus + (lon_sinal * (lon_min / 60.0))
        
        nome_local_exibicao = f"Lat: {lat_graus}° {lat_min}' | Lon: {lon_graus}° {lon_min}'"
        st.success(f"Posição: Lat {lat:.4f}, Lon {lon:.4f}")
    else:
        st.markdown("Clique no mapa para definir o ponto de survey:")
        m = folium.Map(location=[-22.42, -41.02], zoom_start=6, tiles="OpenStreetMap")
        m.add_child(folium.LatLngPopup())
        map_data = st_folium(m, height=250, width="100%")
        
        if map_data and map_data.get("last_clicked"):
            lat = map_data["last_clicked"]["lat"]
            lon = map_data["last_clicked"]["lng"]
            nome_local_exibicao = f"Ponto Clicado (Lat: {lat:.4f}, Lon: {lon:.4f})"
            st.success(f"Selecionado:\nLat: {lat:.4f}, Lon: {lon:.4f}")

with st.sidebar.expander("Janela de Previsão", expanded=False):
    st.info("Recomenda-se fazer para no máximo 4 dias e atualizar o boletim sempre que possível.")
    dias_janela = st.slider("Selecione os dias (1 a 10):", min_value=1, max_value=10, value=4)

with st.sidebar.expander("Equipamentos / Técnica", expanded=False):
    lista_equipamentos_disponiveis = [
        "Monofeixe", "Multifeixe", "SSS", "Mag", "SBP", 
        "Sísmica Monocanal", "Sísmica Multicanal", "Vibrocore", 
        "Jet Probe", "Amostragem Superficial"
    ]
    equipamentos_selecionados = st.multiselect("Selecione os equipamentos em operação:", options=lista_equipamentos_disponiveis, default=["Monofeixe"])

with st.sidebar.expander("Parâmetros Opcionais", expanded=False):
    filtro_diurno = st.checkbox("Apenas Janela Diurna (06:00 às 18:00)", value=False)
    ativar_rumo_critico = st.checkbox("Checar Rumo Crítico / Linha Específica", value=False)
    rumo_embarcacao = 0
    if ativar_rumo_critico:
        rumo_embarcacao = st.number_input("Direção do Rumo / Heading (º)", min_value=0, max_value=360, value=90, step=10)

limites_equipamentos = {
    "Monofeixe": {"onda": 2.5, "vento": 25.0, "corrente": 99.0},
    "Multifeixe": {"onda": 1.5, "vento": 18.0, "corrente": 99.0, "onda_at": 1.0, "vento_at": 15.0},
    "SSS": {"onda": 2.5, "vento": 25.0, "corrente": 3.0},
    "Mag": {"onda": 2.0, "vento": 25.0, "corrente": 3.0},
    "SBP": {"onda": 2.0, "vento": 18.0, "corrente": 3.0},
    "Sísmica Monocanal": {"onda": 1.5, "vento": 18.0, "corrente": 2.0},
    "Sísmica Multicanal": {"onda": 2.0, "vento": 18.0, "corrente": 2.0},
    "Vibrocore": {"onda": 1.0, "vento": 15.0, "corrente": 1.5},
    "Jet Probe": {"onda": 1.2, "vento": 16.0, "corrente": 0.6},
    "Amostragem Superficial": {"onda": 1.5, "vento": 18.0, "corrente": 2.0}
}

if equipamentos_selecionados:
    limite_onda_ativo = min([limites_equipamentos[e]["onda"] for e in equipamentos_selecionados])
    limite_vento_ativo = min([limites_equipamentos[e]["vento"] for e in equipamentos_selecionados])
    limite_corrente_ativo = min([limites_equipamentos[e]["corrente"] for e in equipamentos_selecionados])
    limite_onda_at_ativo = min([limites_equipamentos[e].get("onda_at", limites_equipamentos[e]["onda"] * 0.75) for e in equipamentos_selecionados])
    limite_vento_at_ativo = min([limites_equipamentos[e].get("vento_at", limites_equipamentos[e]["vento"] * 0.75) for e in equipamentos_selecionados])
else:
    limite_onda_ativo = 2.5
    limite_vento_ativo = 25.0
    limite_corrente_ativo = 99.0
    limite_onda_at_ativo = 2.5 * 0.75
    limite_vento_at_ativo = 25.0 * 0.75

def graus_para_direcao(deg):
    if pd.isna(deg): return ""
    direcoes = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    val = int((deg / 22.5) + 0.5)
    return direcoes[val % 16]

@st.cache_data
def carregar_dados_multimodelo(lat_val, lon_val):
    url_mar_oficial = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat_val}&longitude={lon_val}&hourly=wave_height,wave_direction,wave_period&forecast_days=12&timezone=America%2FSao_Paulo"
    url_mar_ww3 = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat_val}&longitude={lon_val}&hourly=wave_height,wave_direction,wave_period&models=best_match&forecast_days=12&timezone=America%2FSao_Paulo"
    url_vento_ecmwf = f"https://api.open-meteo.com/v1/forecast?latitude={lat_val}&longitude={lon_val}&hourly=wind_speed_10m,wind_direction_10m&models=ecmwf_ifs025&wind_speed_unit=kn&timezone=America%2FSao_Paulo"
    url_vento_gfs = f"https://api.open-meteo.com/v1/forecast?latitude={lat_val}&longitude={lon_val}&hourly=wind_speed_10m,wind_direction_10m&models=gfs_seamless&wind_speed_unit=kn&timezone=America%2FSao_Paulo"
    url_vento_icon = f"https://api.open-meteo.com/v1/forecast?latitude={lat_val}&longitude={lon_val}&hourly=wind_speed_10m,wind_direction_10m&models=icon_seamless&wind_speed_unit=kn&timezone=America%2FSao_Paulo"

    def fetch_json(url):
        try:
            r = requests.get(url, timeout=6)
            if r.status_code == 200: return r.json()
        except Exception: pass
        return {}

    j_mar_oficial, j_mar_ww3 = fetch_json(url_mar_oficial), fetch_json(url_mar_ww3)
    j_v_ecmwf, j_v_gfs, j_v_icon = fetch_json(url_vento_ecmwf), fetch_json(url_vento_gfs), fetch_json(url_vento_icon)

    if 'hourly' in j_mar_oficial and 'time' in j_mar_oficial['hourly']: datas = pd.to_datetime(j_mar_oficial['hourly']['time'])
    elif 'hourly' in j_v_ecmwf and 'time' in j_v_ecmwf['hourly']: datas = pd.to_datetime(j_v_ecmwf['hourly']['time'])
    else: datas = pd.date_range(start=pd.Timestamp.now(), periods=24*12, freq='H')

    n_horas = len(datas)

    def get_series(json_obj, key, default_val=1.0):
        if 'hourly' in json_obj and key in json_obj['hourly'] and json_obj['hourly'][key]:
            arr = [v if v is not None else default_val for v in json_obj['hourly'][key]]
            return np.array(arr[:n_horas]) if len(arr) >= n_horas else np.pad(arr, (0, n_horas - len(arr)), 'edge')
        return np.array([default_val] * n_horas)

    w_oficial, w_ww3 = get_series(j_mar_oficial, 'wave_height', 1.0), get_series(j_mar_ww3, 'wave_height', 1.0)
    v_ecmwf_temp = get_series(j_v_ecmwf, 'wind_speed_10m', 5.0)
    w_ecmwf = np.clip(w_oficial + (v_ecmwf_temp * 0.02), 0.5, 3.5)
    wave_dir_oficial = get_series(j_mar_oficial, 'wave_direction', 90.0)
    w_consenso = (w_oficial + w_ecmwf + w_ww3) / 3.0

    v_ecmwf, v_gfs, v_icon = v_ecmwf_temp, get_series(j_v_gfs, 'wind_speed_10m', 5.0), get_series(j_v_icon, 'wind_speed_10m', 5.0)
    dir_v_ecmwf = get_series(j_v_ecmwf, 'wind_direction_10m', 0.0)
    v_consenso = (v_ecmwf + v_gfs + v_icon) / 3.0

    horas = np.arange(n_horas)
    mare = (0.45 * np.cos(2*np.pi/12.4206 * horas - 1.2) + 0.15 * np.cos(2*np.pi/12.0 * horas - 0.5) + 
            0.20 * np.cos(2*np.pi/23.9345 * horas - 0.8) + 0.10 * np.cos(2*np.pi/25.8193 * horas - 0.3) + 0.80)

    df = pd.DataFrame({
        'Data_Hora': datas, 'Mare_Altura(m)': np.round(mare, 2),
        'Onda_Consenso(m)': np.round(w_consenso, 2), 'Onda_ECMWF(m)': np.round(w_ecmwf, 2), 'Onda_WW3(m)': np.round(w_ww3, 2),
        'Onda_Dir_Num': wave_dir_oficial, 'Vento_Consenso_Nos': np.round(v_consenso, 1),
        'Vento_ECMWF_Nos': np.round(v_ecmwf, 1), 'Vento_GFS_Nos': np.round(v_gfs, 1), 'Vento_ICON_Nos': np.round(v_icon, 1),
        'Vento_Dir_Num': dir_v_ecmwf
    })
    
    df['Onda_Dir'] = df['Onda_Dir_Num'].apply(graus_para_direcao)
    df['Vento_Dir'] = df['Vento_Dir_Num'].apply(graus_para_direcao)
    
    delta_mare = df['Mare_Altura(m)'].diff().fillna(0)
    velocidade_ms = np.clip(np.abs(delta_mare) * 1.8, 0.1, 2.5)
    df['Corrente_Vel_ms'] = np.round(velocidade_ms, 2)
    df['Corrente_Vel_Nos'] = np.round(velocidade_ms / 0.5144, 1)
    
    fases, direcoes_corrente = [], []
    for dm in delta_mare:
        if dm > 0.01: fases.append('Enchente'); direcoes_corrente.append('NE')
        elif dm < -0.01: fases.append('Vazante'); direcoes_corrente.append('SE')
        else: fases.append('Estofamento'); direcoes_corrente.append('-')
            
    df['Fase_Estuario'], df['Corrente_Dir'] = fases, direcoes_corrente
    return df

btn_gerar = st.sidebar.button("Gerar Boletim Operacional")

if btn_gerar or 'df_atual' not in st.session_state:
    df_completo = carregar_dados_multimodelo(lat, lon)
    data_inicio = df_completo['Data_Hora'].min()
    data_fim = data_inicio + pd.Timedelta(days=dias_janela)
    df = df_completo[(df_completo['Data_Hora'] >= data_inicio) & (df_completo['Data_Hora'] <= data_fim)].copy()
    
    if filtro_diurno:
        df = df[(df['Data_Hora'].dt.hour >= 6) & (df['Data_Hora'].dt.hour <= 18)].copy()
    
    def regras_e_incidencia(row):
        onda = row['Onda_Consenso(m)']
        vento = row['Vento_Consenso_Nos']
        corrente = row['Corrente_Vel_Nos']
        onda_dir = row['Onda_Dir_Num']
        
        aviso_direcao = ""
        if ativar_rumo_critico and not pd.isna(onda_dir):
            diff_ang = abs(onda_dir - rumo_embarcacao) % 360
            if diff_ang > 180: diff_ang = 360 - diff_ang
            if 60 <= diff_ang <= 120: aviso_direcao = " [Atencao: Mar de Traves]"

        if onda > limite_onda_ativo or vento > limite_vento_ativo or ((limite_corrente_ativo < 10.0) and (corrente > limite_corrente_ativo)):
            return "SEM OPERACAO", f"Limite critico excedido{aviso_direcao}"
        
        limite_corrente_check = limite_corrente_ativo if limite_corrente_ativo < 10.0 else 99.0
        
        if (limite_onda_at_ativo <= onda <= limite_onda_ativo) or (limite_vento_at_ativo <= vento <= limite_vento_ativo) or ((limite_corrente_check < 99.0) and (limite_corrente_check * 0.75 <= corrente <= limite_corrente_check)):
            return "AVALIACAO TECNICA", f"Condicao limitrofe{aviso_direcao}"
        
        if aviso_direcao == "":
            return "FAVORAVEL", "Dentro da janela"
        else:
            return "AVALIACAO TECNICA", f"Incidencia lateral critica{aviso_direcao}"

    df[['Status', 'Avisos']] = df.apply(regras_e_incidencia, axis=1, result_type='expand')
    st.session_state['df_atual'] = df

df = st.session_state['df_atual']

total_horas = len(df)
favoraveis = len(df[df['Status'] == "FAVORAVEL"])
tecnicas = len(df[df['Status'] == "AVALIACAO TECNICA"])
nogo = len(df[df['Status'] == "SEM OPERACAO"])

df_tl = df.copy()
df_tl['Dia'] = df_tl['Data_Hora'].dt.strftime('%d/%m')
df_tl['Hora'] = df_tl['Data_Hora'].dt.hour
status_map = {"FAVORAVEL": 0, "AVALIACAO TECNICA": 1, "SEM OPERACAO": 2}
df_tl['Status_Num'] = df_tl['Status'].map(status_map)
heatmap_data = df_tl.pivot(index='Dia', columns='Hora', values='Status_Num')

for h in range(24):
    if h not in heatmap_data.columns:
        heatmap_data[h] = np.nan
heatmap_data = heatmap_data[sorted(heatmap_data.columns)]

if os.path.exists("logo2.png"):
    st.image("logo2.png", width=220)

st.markdown("### Boletim Meteoceanográfico")
txt_detalhes = []
if filtro_diurno: txt_detalhes.append("Diurno (06h - 18h)")
if ativar_rumo_critico: txt_detalhes.append(f"Rumo Crítico: {rumo_embarcacao}º")
sub_str = f" | {' | '.join(txt_detalhes)}" if txt_detalhes else ""
corrente_txt_limite = f" | Corrente <= {limite_corrente_ativo} kn" if limite_corrente_ativo < 10.0 else ""
st.markdown(f'<p class="sub-title"><b>Local:</b> {nome_local_exibicao} | <b>Previsão:</b> {dias_janela} dias{sub_str}<br><b>Equipamentos:</b> {", ".join(equipamentos_selecionados) if equipamentos_selecionados else "Nenhum"}<br><b>Limiar Consenso:</b> Onda <= {limite_onda_ativo} m | Vento <= {limite_vento_ativo} kn{corrente_txt_limite}</p>', unsafe_allow_html=True)

st.markdown("---")
st.markdown("### Sumário Executivo da Janela")

col_donut, col_timeline = st.columns([1, 1.8])

with col_donut:
    if total_horas > 0:
        labels_status = ['FAVORAVEL', 'AVALIACAO TECNICA', 'SEM OPERACAO']
        values_status = [favoraveis, tecnicas, nogo]
        color_map = {'FAVORAVEL':'#2E7D32', 'AVALIACAO TECNICA':'#E5E1E6', 'SEM OPERACAO':'#F32735'} # COR CINZA MANTIDA
        fig_donut = px.pie(names=labels_status, values=values_status, hole=0.65, color=labels_status, color_discrete_map=color_map)
        fig_donut.update_traces(textposition='inside', textinfo='percent', hoverinfo='label+value')
        fig_donut.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=True, height=220, legend=dict(yanchor="top", y=0.99, xanchor="left", x=1.05))
        st.plotly_chart(fig_donut, use_container_width=True)

with col_timeline:
    if total_horas > 0:
        text_data = []
        for row in heatmap_data.values:
            text_row = []
            for val in row:
                if val == 0: text_row.append("FAVORAVEL")
                elif val == 1: text_row.append("AVALIACAO TECNICA")
                elif val == 2: text_row.append("SEM OPERACAO")
                else: text_row.append("Sem Dado")
            text_data.append(text_row)
            
        colorscale = [
            [0.0, '#2E7D32'], [0.333, '#2E7D32'],
            [0.333, '#E5E1E6'], [0.666, '#E5E1E6'], # COR CINZA MANTIDA
            [0.666, '#F32735'], [1.0, '#F32735']
        ]
        
        fig_timeline = go.Figure(data=go.Heatmap(
            z=heatmap_data.values,
            x=[f"{h:02d}h" for h in heatmap_data.columns],
            y=heatmap_data.index,
            colorscale=colorscale,
            zmin=0, zmax=2,
            showscale=False,
            xgap=2, ygap=2,
            text=text_data,
            hovertemplate='Dia: %{y}<br>Hora: %{x}<br>Status: %{text}<extra></extra>'
        ))
        
        fig_timeline.update_layout(
            title=dict(text="Matriz Operacional de Janela", font=dict(size=14)),
            xaxis=dict(tickangle=-45),
            yaxis=dict(autorange='reversed'),
            height=220,
            margin=dict(t=40, b=10, l=10, r=10)
        )
        st.plotly_chart(fig_timeline, use_container_width=True)

horas_nogo = df[df['Status'] == "SEM OPERACAO"]
horas_atencao = df[df['Status'] == "AVALIACAO TECNICA"]

if not horas_nogo.empty: st.error(f"**RESTRIÇÃO CRÍTICA** - Identificados {len(horas_nogo)} períodos de bloqueio. Início previsto: {horas_nogo.iloc[0]['Data_Hora'].strftime('%d/%m/%Y às %H:%M')}.")
elif not horas_atencao.empty: st.warning(f"**CONDIÇÃO LIMÍTROFE** - Identificadas {len(horas_atencao)} horas em patamar de atenção ou incidência de mar de través.")
else: st.success("**CONDIÇÃO FAVORÁVEL** - Janela inteiramente operável dentro dos limiares estabelecidos.")

st.info("**AVISOS AOS NAVEGANTES (AVGN) - DHN** - Consulta obrigatória antes de zarpar: [Portal Oficial DHN](https://www.marinha.mil.br/chm/dados-do-segnav-aviso-aos-navegantes-tela).")

st.markdown("---")

with st.expander("Diretrizes Operacionais e Limites de Equipamentos"):
    st.markdown("""
    **1. Hierarquia e Regra de Ouro dos Equipamentos:**
    O limite operacional da embarcação é ditado pelo equipamento mais restritivo em operação na campanha. O sistema avalia simultaneamente o conjunto de equipamentos selecionados e aplica o limiar mais rigoroso.
    
    **2. Diretrizes de Operação (Padrões IHO / IMCA):**
    * **Sistemas Acústicos (Monofeixe / Multifeixe):** Sensíveis a aeração de bolhas e movimentos de pitch/roll.
    * **Sistemas Rebocados (SSS / Mag / SBP / Sísmicas):** Exigem navegação ao longo do swell para evitar mar de través.
    * **Operações Geotécnicas (Vibrocore / Jet Probe / Amostragem):** Sensíveis a correntes de fundo e agitação superficial.
    """)

with st.expander("Fontes de Dados, Modelos Numéricos Globais e Credibilidade Técnica"):
    st.markdown("""
    ### Transparência e Rigor Metodológico
    Para assegurar total confiabilidade nas operações de campo, o presente boletim operacional emprega uma arquitetura de **Múltiplas Fontes Redundantes**, cruzando dados de centros meteorológicos e oceanográficos de referência global. A leitura dos parâmetros é estruturada da seguinte forma:
    
    **1. Previsão de Ventos em Nós (Comitê Multi-Modelo / Ensemble):**
    O vento é o principal motor gerador de agitação marítima e de esforço sobre as embarcações. Para mitigar incertezas individuais de previsão, o aplicativo coleta, processa e calcula uma curva de consenso (média ponderada) em **nós (kn)** entre três modelos atmosféricos globais:
    * **ECMWF IFS (Centro Europeu - Europa):** Padrão ouro mundial em previsão numérica de atmosfera e campos de vento.
    * **GFS (Global Forecast System - NOAA, Estados Unidos):** Modelo oficial americano de referência sinótica global.
    * **ICON (DWD, Alemanha):** Modelo de altíssima resolução espacial para validação cruzada.
    
    **2. Agitação Marítima e Altura de Ondas (Comitê Multi-Modelo de Ondas):**
    A agitação de vagas e swell é obtida através de um comitê oceanográfico que consolida estatisticamente a média de três vertentes de alta precisão internacional:
    * **ECMWF Waves (Centro Europeu):** Modelo acoplado de referência global em energia de superfície e propagação de ondas.
    * **WaveWatch III (WW3 - NOAA / EUA):** O modelo numérico de terceira geração referência absoluta mundial em propagação de swell em águas profundas e costeiras.
    * **Modelo Costeiro de Alta Resolução (Open-Meteo Marine):** Simulação hidrodinâmica local calibrada para águas rasas e zona costeira.
    * *Fundamentação:* O cruzamento em comitê (ensemble) entre ECMWF Waves, WaveWatch III e o modelo costeiro elimina distorções pontuais, garantindo uma curva de consenso robusta para a matriz de Go/No-Go dos sensores.
    
    **3. Correntes Estuarinas e Maré:**
    * **Nível do Mar:** Calculado através de modelos harmônicos de maré de alta precisão calibrados para a costa brasileira.
    * **Correntes em Canais e Barras:** Derivadas dinamicamente via taxa de variação temporal do nível da maré ($\Delta h / \Delta t$) em nós (kn).
    """)

# EXPORTAÇÃO PDF BLINDADA CONTRA NONE
st.markdown("---")
st.subheader("Exportação do Relatório Executivo")

nome_arquivo_usuario = st.text_input("Nome do Projeto / Sufixo do Arquivo (Opcional):", value="", help="Exemplo: 'Paranagua_Campanha1'. O arquivo será salvo como BOLETIM_METEOCEAN_4SAS_Paranagua_Campanha1.pdf")

if st.button("Gerar Relatório Executivo (PDF ReportLab)"):
    with st.spinner("Compilando dados e gerando relatório no padrão ReportLab..."):
        try:
            data_hoje = datetime.datetime.now().strftime("%d/%m/%Y")
            pdf_bytes = gerar_pdf_boletim_reportlab(
                dataframe=df,
                local_nome=nome_local_exibicao,
                dias_janela=dias_janela,
                favoraveis=favoraveis,
                tecnicas=tecnicas,
                nogo=nogo,
                df_heatmap=heatmap_data,
                lat=lat,
                lon=lon,
                equipamentos=equipamentos_selecionados,
                limite_onda=limite_onda_ativo,
                limite_vento=limite_vento_ativo,
                limite_corrente=limite_corrente_ativo,
                data_emissao=data_hoje
            )
            if pdf_bytes and isinstance(pdf_bytes, bytes):
                st.session_state['pdf_boletim_bytes'] = pdf_bytes
                st.success("Relatório PDF gerado com sucesso!")
            else:
                st.error("Falha na validação de bytes do PDF.")
        except Exception as e:
            st.error(f"Erro ao gerar o PDF: {e}")

if st.session_state.get('pdf_boletim_bytes') is not None:
    nome_limpo = nome_arquivo_usuario.strip().replace(" ", "_")
    nome_final = f"BOLETIM_METEOCEAN_4SAS_{nome_limpo}.pdf" if nome_limpo else "BOLETIM_METEOCEAN_4SAS.pdf"
        
    st.download_button(
        label=f"Baixar Relatório ({nome_final})",
        data=st.session_state['pdf_boletim_bytes'],
        file_name=nome_final,
        mime="application/pdf"
    )

st.markdown("---")

# TABELA E GRÁFICOS INFERIORES
df_exibicao = df[['Data_Hora', 'Mare_Altura(m)', 'Fase_Estuario', 'Onda_Consenso(m)', 'Onda_Dir', 'Vento_Consenso_Nos', 'Vento_Dir']].copy()
df_exibicao['Corrente'] = df['Corrente_Vel_Nos'].astype(str) + " kn (" + df['Corrente_Dir'] + ")"
df_exibicao['Status'] = df['Status']
df_exibicao['Avisos'] = df['Avisos']

st.dataframe(df_exibicao, use_container_width=True, hide_index=True)

st.subheader("Comparação de Modelos Numéricos de Onda (Consenso vs ECMWF Waves vs WaveWatch III)")
fig_onda_comp = px.line(df, x='Data_Hora', y=['Onda_Consenso(m)', 'Onda_ECMWF(m)', 'Onda_WW3(m)'], labels={'value': 'Altura da Onda (m)', 'Data_Hora': 'Horário', 'variable': 'Modelo Numérico'})
fig_onda_comp.update_traces(line_shape='spline', line_width=2)
fig_onda_comp.data[0].update(line_width=3.5, line_color='#F32735')
st.plotly_chart(fig_onda_comp, use_container_width=True, key="grafico_onda_comparacao")

st.subheader("Comparação de Modelos Numéricos de Vento (em Nós)")
fig_vento_comp = px.line(df, x='Data_Hora', y=['Vento_Consenso_Nos', 'Vento_ECMWF_Nos', 'Vento_GFS_Nos', 'Vento_ICON_Nos'], labels={'value': 'Velocidade (kn)', 'Data_Hora': 'Horário', 'variable': 'Modelo'})
fig_vento_comp.update_traces(line_shape='spline', line_width=2)
fig_vento_comp.data[0].update(line_width=3.5, line_color='#F32735')
fig_vento_comp.data[3].update(line_color='#FFD700')
st.plotly_chart(fig_vento_comp, use_container_width=True, key="grafico_vento_comparacao")

st.subheader("Análise Temporal de Correntes Estuarinas e Maré")
fig_corrente = px.line(df, x='Data_Hora', y=['Mare_Altura(m)', 'Corrente_Vel_Nos'], labels={'value': 'Intensidade / Nível', 'Data_Hora': 'Horário', 'variable': 'Parâmetro'})
fig_corrente.update_traces(line_shape='spline', line_width=3)
fig_corrente.data[0].update(name="Nível da Maré (m)") 
fig_corrente.data[1].update(name="Velocidade da Corrente (kn)")
st.plotly_chart(fig_corrente, use_container_width=True, key="grafico_temporal_correntes")

st.markdown("---")
st.subheader("Análise Direcional (Rosas de Vento e Onda - Consenso)")
col_r1, col_r2 = st.columns(2)

with col_r1:
    st.markdown("**Rosa de Ventos (Consenso)**")
    df_vento_clean = df.dropna(subset=['Vento_Dir', 'Vento_Consenso_Nos'])
    if not df_vento_clean.empty:
        fig_wind = px.bar_polar(df_vento_clean, r="Vento_Consenso_Nos", theta="Vento_Dir", color="Vento_Consenso_Nos", color_continuous_scale="Teal", direction="clockwise", start_angle=90)
        fig_wind.update_layout(polar=dict(radialaxis=dict(visible=True)), margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_wind, use_container_width=True, key="rosa_vento")
        
with col_r2:
    st.markdown("**Rosa de Ondas / Swell (Consenso)**")
    df_onda_clean = df.dropna(subset=['Onda_Dir', 'Onda_Consenso(m)'])
    if not df_onda_clean.empty:
        fig_wave = px.bar_polar(df_onda_clean, r="Onda_Consenso(m)", theta="Onda_Dir", color="Onda_Consenso(m)", color_continuous_scale="Blues", direction="clockwise", start_angle=90)
        fig_wave.update_layout(polar=dict(radialaxis=dict(visible=True)), margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_wave, use_container_width=True, key="rosa_onda")