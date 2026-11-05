import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import pandas as pd
import json

from utils.geo_engine import (
    get_geotiff_overlay_data,
    calculate_survey_parameters,
    generate_survey_lines,
    calculate_bearing,
)
from utils.exports import generate_hypack_lnw, generate_qinsy_txt, generate_csv

st.set_page_config(page_title="Planejador de Linhas | 4SAS", layout="wide")

st.title("Planejador de Linhas de Levantamento")
st.caption("Módulo Geoespacial para Batimetria (NORMAM-501 / IHO) e Geofísica Rasa (EdgeTech 2000-DSS SSS/SBP)")

# --- GUIA RÁPIDO DE OPERAÇÃO ---
with st.expander("📌 **Guia Rápido de Operação & Orientação de Rumo (Clique para expandir)**", expanded=False):
    st.markdown("""
    **Como planejar a grade de linhas em 4 passos:**
    
    1. 🖼️ **(Opcional) Imagem GeoTIFF ou Vértices TXT:**
       - Carregue uma imagem GeoTIFF ou um arquivo `.txt`/`.csv` contendo as coordenadas precisas do polígono da área.
    2. 📏 **Medir ou Inserir o Rumo (Azimute):**
       - Meça o azimute no mapa com a ferramenta de linha ou defina o azimute diretamente na barra lateral.
    3. ⚙️ **Configurar Espaçamentos e Crosslines:**
       - Escolha o método de cálculo automático ou defina manualmente o espaçamento entre linhas principais e transversais (*crosslines*).
    4. 📥 **Exportar Arquivos de Navegação:**
       - Faça o download nos formatos Hypack (`.lnw`), Qinsy (`.txt`) ou Tabela (`.csv`).
    """)

# --- INICIALIZAÇÃO DE ESTADOS DA SESSÃO ---
if "last_polygon" not in st.session_state:
    st.session_state["last_polygon"] = None

# --- BARRA LATERAL: ENTRADA DE DADOS & ARQUIVOS ---
st.sidebar.header("📂 1. Dados de Área e Fundo")

# File Uploader 1: GeoTIFF
uploaded_geotiff = st.sidebar.file_uploader("Carregar GeoTIFF (.tif / .tiff)", type=["tif", "tiff"])
image_opacity = 0.85
if uploaded_geotiff is not None:
    image_opacity = st.sidebar.slider("Opacidade da Imagem", min_value=0.1, max_value=1.0, value=0.85, step=0.05)

# File Uploader 2: Vértices do Polígono por TXT/CSV
uploaded_txt_poly = st.sidebar.file_uploader(
    "Carregar Coordenadas do Polígono (.txt / .csv / .xyz)", 
    type=["txt", "csv", "xyz"]
)

if uploaded_txt_poly is not None:
    try:
        # Leitura flexível de delimitadores
        df_coords = pd.read_csv(uploaded_txt_poly, sep=r'\s+|,|;', engine='python', header=None)
        df_coords = df_coords.dropna().select_dtypes(include=['float64', 'int64'])
        
        if df_coords.shape[1] >= 2:
            st.sidebar.subheader("📌 Formato do Arquivo de Vértices")
            coord_order = st.sidebar.radio("Ordem das Colunas", ["Lat, Lon", "Lon, Lat"], index=0)
            
            if coord_order == "Lat, Lon":
                lats = df_coords.iloc[:, 0].tolist()
                lons = df_coords.iloc[:, 1].tolist()
            else:
                lons = df_coords.iloc[:, 0].tolist()
                lats = df_coords.iloc[:, 1].tolist()
                
            # Monta o GeoJSON de Polígono (coordenadas no padrão GeoJSON [Lon, Lat])
            polygon_coords = [[lon, lat] for lon, lat in zip(lons, lats)]
            if polygon_coords[0] != polygon_coords[-1]:
                polygon_coords.append(polygon_coords[0]) # Fechar o anel do polígono
                
            st.session_state["last_polygon"] = {
                "type": "Polygon",
                "coordinates": [polygon_coords]
            }
            st.sidebar.success(f"✅ {len(polygon_coords)-1} vértices carregados com sucesso!")
        else:
            st.sidebar.error("❌ O arquivo deve conter pelo menos 2 colunas numéricas.")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler arquivo de texto: {e}")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 2. Parâmetros de Linha e Espaçamento")

mode_spacing = st.sidebar.radio(
    "Modo de Dimensionamento",
    ["Calculado (MBES / SSS por Norma)", "Manual (Espaçamento Definido pelo Usuário)"]
)

calculated_spacing = 50.0

if mode_spacing == "Calculado (MBES / SSS por Norma)":
    method = st.sidebar.selectbox(
        "Método / Equipamento",
        ["Batimetria (NORMAM-501 / IHO S-44)", "Geofísica Rasa (EdgeTech 2000-DSS SSS/SBP)"]
    )

    if method == "Batimetria (NORMAM-501 / IHO S-44)":
        transducer_pos = st.sidebar.selectbox(
            "Bordo de Montagem da Haste / Sonar",
            ["Centro / Quilha (Midship)", "Haste a Bombordo (Port Side)", "Haste a Estibordo (Starboard Side)", "Dual Head"]
        )
        norm = st.sidebar.selectbox(
            "Norma / Categoria",
            ["NORMAM-501 Cat A", "NORMAM-501 Cat B", "NORMAM-501 Cat C", "IHO S-44 Special Order", "IHO S-44 Order 1a"]
        )
        depth = st.sidebar.number_input("Profundidade Média Local (m)", min_value=1.0, value=12.0, step=0.5)
        beam_angle = st.sidebar.slider("Abertura do Feixe Multifeixe (°)", min_value=60, max_value=140, value=120)
        overlap = st.sidebar.slider("Sobreposição Mínima (%)", min_value=10, max_value=50, value=20)
        
        calculated_spacing = calculate_survey_parameters(
            method, depth=depth, norm=norm, beam_angle=beam_angle, overlap=overlap, transducer_pos=transducer_pos
        )
    else:
        range_m = st.sidebar.select_slider("Alcance por Canal SSS (m)", options=[37.5, 50.0, 75.0, 100.0, 150.0, 200.0], value=75.0)
        coverage_opt = st.sidebar.selectbox("Nível de Cobertura SSS", ["200% - Cobertura Dupla", "150% - Sobreposição 50%", "100% - Mosaico Simples"])
        coverage_pct = 200 if "200%" in coverage_opt else (150 if "150%" in coverage_opt else 100)
        
        calculated_spacing = calculate_survey_parameters(method, range_m=range_m, coverage_pct=coverage_pct)

    final_spacing = st.sidebar.number_input("Espaçamento das Linhas Principais (m)", value=float(calculated_spacing), min_value=1.0, step=1.0)
else:
    final_spacing = st.sidebar.number_input("Espaçamento das Linhas Principais (m)", value=25.0, min_value=1.0, step=1.0)

# --- CONFIGURAÇÃO DE CROSSLINES / TRANSVERSAIS ---
st.sidebar.markdown("---")
st.sidebar.header("📐 3. Crosslines (Linhas Transversais)")

enable_crosslines = st.sidebar.checkbox("Gerar Crosslines / Transversais de Amarração", value=True)

crossline_spacing = None
if enable_crosslines:
    crossline_spacing = st.sidebar.number_input(
        "Espaçamento entre Crosslines (m)",
        min_value=5.0,
        value=float(final_spacing * 10), # Padrão recomendado IHO: 10x o espaçamento principal
        step=5.0
    )
    st.sidebar.info(f"💡 Sugestão IHO/NORMAM: 10x Linha Principal ({final_spacing * 10:.1f} m)")

st.sidebar.markdown("---")
st.sidebar.header("🧭 4. Azimute & Orientação")
azimuth = st.sidebar.number_input("Rumo / Azimute Linhas Principais (°)", min_value=0.0, max_value=360.0, value=45.0, step=1.0)

# --- PROCESSAMENTO DO GEOTIFF E POSICIONAMENTO DO MAPA ---
map_location = [-22.9, -43.1]
map_zoom = 13
overlay_img_url = None
geotiff_bounds = None

if uploaded_geotiff is not None:
    try:
        overlay_img_url, geotiff_bounds = get_geotiff_overlay_data(uploaded_geotiff.getvalue())
        lat_center = (geotiff_bounds[0][0] + geotiff_bounds[1][0]) / 2.0
        lon_center = (geotiff_bounds[0][1] + geotiff_bounds[1][1]) / 2.0
        map_location = [lat_center, lon_center]
        map_zoom = 14
        st.sidebar.success("✅ GeoTIFF renderizado!")
    except Exception as e:
        st.sidebar.error(f"Erro ao processar GeoTIFF: {e}")

# Se um polígono foi carregado via TXT e não há GeoTIFF, foca a câmera no centro do polígono
if uploaded_txt_poly is not None and st.session_state["last_polygon"] and uploaded_geotiff is None:
    poly_coords = st.session_state["last_polygon"]["coordinates"][0]
    avg_lon = sum(pt[0] for pt in poly_coords) / len(poly_coords)
    avg_lat = sum(pt[1] for pt in poly_coords) / len(poly_coords)
    map_location = [avg_lat, avg_lon]
    map_zoom = 15

m = folium.Map(location=map_location, zoom_start=map_zoom, tiles="OpenStreetMap")

if overlay_img_url and geotiff_bounds:
    folium.raster_layers.ImageOverlay(
        image=overlay_img_url,
        bounds=geotiff_bounds,
        opacity=image_opacity,
        interactive=True,
        zindex=10
    ).add_to(m)

# RENDERIZAÇÃO DO POLÍGONO E DAS LINHAS GERADAS
if st.session_state["last_polygon"]:
    poly_wgs = [[pt[1], pt[0]] for pt in st.session_state["last_polygon"]["coordinates"][0]]
    folium.Polygon(
        locations=poly_wgs,
        color="#D32F2F",
        weight=2,
        fill=True,
        fill_opacity=0.15,
        popup="Área de Levantamento (Polígono)"
    ).add_to(m)

    current_lines = generate_survey_lines(
        st.session_state["last_polygon"], azimuth, final_spacing, crossline_spacing
    )
    for line in current_lines:
        is_crossline = line["type"].startswith("Amarração") or line["type"].startswith("Crossline")
        color = "#E65100" if is_crossline else "#0D47A1"
        dash_array = "6, 6" if is_crossline else None
        
        folium.PolyLine(
            locations=line["coords_wgs84"],
            color=color,
            weight=2.5,
            dash_array=dash_array,
            popup=f"Linha: {line['id']} | Tipo: {line['type']} | Az: {line['azimuth']}° | Comp: {line['length_m']}m"
        ).add_to(m)

# FERRAMENTA DE DESENHO MANUAL NO MAPA
draw = Draw(
    export=True,
    filename="area_survey.geojson",
    position="topleft",
    draw_options={
        "polyline": True,
        "polygon": True,
        "rectangle": True,
        "circle": False,
        "marker": False,
        "circlemarker": False,
    },
    edit_options={"edit": True}
)
draw.add_to(m)

map_data = st_folium(m, width="100%", height=550)

# CAPTURA DE INTERAÇÕES DE DESENHO NO MAPA
if map_data and map_data.get("all_drawings"):
    for feature in map_data["all_drawings"]:
        geom_type = feature["geometry"]["type"]
        coords = feature["geometry"]["coordinates"]
        
        if geom_type == "LineString" and len(coords) >= 2:
            lon1, lat1 = coords[0]
            lon2, lat2 = coords[1]
            measured_bearing = calculate_bearing(lat1, lon1, lat2, lon2)
            st.sidebar.success(f"🎯 Azimute Medido: **{measured_bearing:.1f}°**")
            
        elif geom_type in ["Polygon"]:
            st.session_state["last_polygon"] = feature["geometry"]

# --- QUADRO DE MÉTRICAS & DOWNLOADS ---
if st.session_state["last_polygon"]:
    generated_lines = generate_survey_lines(
        st.session_state["last_polygon"], azimuth, final_spacing, crossline_spacing
    )
    
    if generated_lines:
        total_len_km = sum(l["length_m"] for l in generated_lines) / 1000.0
        n_main = sum(1 for l in generated_lines if not (l["type"].startswith("Amarração") or l["type"].startswith("Crossline")))
        n_cross = len(generated_lines) - n_main
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Espaçamento Principal", f"{final_spacing:.1f} m")
        col2.metric("Linhas Principais", f"{n_main}")
        col3.metric("Crosslines", f"{n_cross}" if enable_crosslines else "Desativado")
        col4.metric("Quilometragem Total", f"{total_len_km:.2f} km")
        
        st.markdown("### 📥 Exportar Grid de Navegação")
        exp_col1, exp_col2, exp_col3 = st.columns(3)
        
        lnw_data = generate_hypack_lnw(generated_lines)
        exp_col1.download_button(
            "📄 Baixar Hypack (.lnw)",
            data=lnw_data,
            file_name="grid_survey_4sas.lnw",
            mime="text/plain"
        )
        
        txt_data = generate_qinsy_txt(generated_lines)
        exp_col2.download_button(
            "📄 Baixar Qinsy (.txt)",
            data=txt_data,
            file_name="grid_survey_4sas.txt",
            mime="text/plain"
        )
        
        csv_data = generate_csv(generated_lines)
        exp_col3.download_button(
            "📊 Baixar Lista de Linhas (.csv)",
            data=csv_data,
            file_name="grid_survey_4sas.csv",
            mime="text/csv"
        )
    else:
        st.warning("⚠️ O polígono informado é muito pequeno para os espaçamentos configurados.")
else:
    st.info("💡 Carregue um arquivo TXT com as coordenadas do polígono ou desenhe a área diretamente no mapa para gerar o grid.")