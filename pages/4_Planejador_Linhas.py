from utils.geo_engine import get_image_bounds_from_bytes, calculate_survey_parameters, generate_survey_lines, calculate_bearing
from utils.exports import generate_csv_report, generate_hypack_lnw, generate_qinsy_txt
from utils.geo_engine import get_image_bounds_from_bytes, calculate_survey_parameters, generate_survey_lines
import streamlit as st
import folium
from streamlit_folium import st_folium
import os


# Importa a função de upload que criamos no utils
from utils.supabase_client import upload_image_to_storage

# 1. Configuração do Padrão Corporativo 4SAS
st.set_page_config(page_title="4SAS | Planejador de Linhas", layout="wide")
st.markdown("""
    <style>
    /* Tipografia Carbona Variable e design system 4SAS */
    html, body, [class*="css"] {
        font-family: 'Carbona Variable', sans-serif !important;
    }
    .stButton>button {
        background-color: #0056b3;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

st.title("Planejador de Linhas")
st.markdown("Planejamento automatizado de malhas de levantamento hidrográfico (NORMAM-501).")

# 2. Sidebar - Upload e Parâmetros
with st.sidebar:
    st.header("1. Ingestão de Dados")
    uploaded_file = st.file_uploader("Upload da Imagem GeoTIFF", type=["tif", "tiff", "png", "jpeg"])
    
    st.markdown("---")
    st.header("2. Parâmetros do Survey")
    sensor = st.selectbox("Sensor Utilizado", ["Kongsberg EA440 (SBES)", "R2Sonic 2024 (MBES)"])
    scope = st.selectbox("Escopo Normativo", ["NORMAM-501 Ordem Especial", "NORMAM-501 Ordem 1a", "Reconhecimento"])
    depth = st.number_input("Profundidade Média (m)", min_value=1, value=20)
    heading = st.number_input("Rumo Desejado das Linhas (°)", min_value=0, max_value=359, value=0)

# 3. Lógica de Upload para o Supabase (Com controle de Estado)
image_url = None

if uploaded_file is not None:
    # Verifica se já subimos ESSE arquivo específico na sessão atual
    if "uploaded_filename" not in st.session_state or st.session_state.uploaded_filename != uploaded_file.name:
        with st.spinner("Enviando imagem para o Storage da 4SAS..."):
            file_bytes = uploaded_file.getvalue()
            
            # Executa o upload e salva a URL na memória do Streamlit
            url = upload_image_to_storage(file_bytes, uploaded_file.name)
            if url:
                st.session_state.image_url = url
                st.session_state.uploaded_filename = uploaded_file.name
    
    # Recupera a URL da memória para não precisar subir de novo
    if "image_url" in st.session_state:
        image_url = st.session_state.image_url
        st.sidebar.success("Upload concluído com sucesso!")

# 4. Renderização do Mapa Principal
st.subheader("Mapa de Planejamento")

# Coordenada padrão (vai mudar automaticamente se tiver imagem)
center_lat, center_lon = -22.90, -43.15
zoom = 12
bounds = None

# Se tivermos a imagem carregada na sessão, extraímos os dados geográficos
if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    bounds = get_image_bounds_from_bytes(file_bytes)
    
    if bounds:
        # Calcula o centro da imagem para o mapa iniciar focado nela
        center_lat = (bounds[0][0] + bounds[1][0]) / 2.0
        center_lon = (bounds[0][1] + bounds[1][1]) / 2.0
    else:
        st.warning("Aviso: A imagem enviada não possui dados de georeferenciamento (Spatial Reference). O mapa ficará na posição padrão.")

# Inicializa o mapa focado no centro correto
m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom, tiles="Esri.WorldImagery")

# Adiciona as ferramentas de desenho
# Adiciona as ferramentas de desenho
from folium.plugins import Draw
draw = Draw(
    draw_options={'polygon': True, 'polyline': True, 'rectangle': True, 'circle': False, 'marker': False, 'circlemarker': False},
    edit_options={'edit': True, 'remove': True} # Ativa a lixeirinha para apagar a linha depois
)
m.add_child(draw)

# Se temos a URL pública do Supabase e as coordenadas da imagem, nós a "colamos" no mapa
if image_url and bounds:
    folium.raster_layers.ImageOverlay(
        image=image_url,
        bounds=bounds,
        opacity=0.6, # 60% de opacidade para vermos o satélite por baixo
        name="Imagem de Survey"
    ).add_to(m)
    
    # Força o mapa a dar zoom exato na sua imagem
    m.fit_bounds(bounds)

# Renderiza tudo na tela
output = st_folium(m, width=1200, height=600, returned_objects=["last_active_drawing"])

if output and output.get("last_active_drawing"):
    geom = output["last_active_drawing"]["geometry"]
    geom_type = geom["type"]
    
    if geom_type == "LineString":
        # Se o usuário desenhou uma linha reta
        coords = geom["coordinates"]
        lon1, lat1 = coords[0]
        lon2, lat2 = coords[-1]
        
        rumo = calculate_bearing(lon1, lat1, lon2, lat2)
        st.info(f"🧭 **Rumo Medido:** {rumo}° (Use este valor no menu lateral. Para apagar a linha, use o ícone de lixeira no mapa).")
        st.warning("Agora desenhe o Polígono para definir a área do survey.")
        
    elif geom_type == "Polygon":
        # Lógica original para quando o usuário desenha a área do survey
        geojson_polygon = geom
        st.success("Polígono desenhado com sucesso! Processando malha...")
        
        spacing, justificativa = calculate_survey_parameters(sensor, scope, depth)
        st.markdown("### Justificativa Técnica")
        st.info(justificativa)
        
        if st.button("Gerar Linhas de Survey", type="primary"):
            with st.spinner("Calculando geometria e interseções..."):
                survey_lines = generate_survey_lines(geojson_polygon, spacing, heading)
                
                for i, line in enumerate(survey_lines):
                    coords_line = [(lat, lon) for lon, lat in line.coords]
                    folium.PolyLine(
                        locations=coords_line,
                        color='red',
                        weight=2,
                        tooltip=f"Linha {i+1}"
                    ).add_to(m)
                
                st.session_state["lines_generated"] = True
                st_folium(m, width=1200, height=600, key="mapa_com_linhas")
                
                st.success(f"Foram geradas {len(survey_lines)} linhas com espaçamento de {spacing:.1f}m no rumo {heading}°.")
                
                # --- MÓDULO DE EXPORTAÇÃO ---
                st.markdown("---")
                st.subheader("📥 Exportar Plano de Linhas")
                csv_bytes = generate_csv_report(survey_lines, heading)
                hypack_bytes = generate_hypack_lnw(survey_lines)
                qinsy_bytes = generate_qinsy_txt(survey_lines)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.download_button("📄 Planilha (CSV)", csv_bytes, "plano.csv", "text/csv", use_container_width=True)
                with col2:
                    st.download_button("🎯 Exportar Hypack", hypack_bytes, "linhas.lnw", "text/plain", use_container_width=True)
                with col3:
                    st.download_button("⚓ Exportar Qinsy", qinsy_bytes, "linhas.txt", "text/plain", use_container_width=True)