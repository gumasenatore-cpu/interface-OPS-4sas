import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium

from utils.geo_engine import (
    get_geotiff_overlay_data,
    calculate_survey_parameters,
    generate_survey_lines,
    calculate_bearing,
)
from utils.exports import generate_hypack_lnw, generate_qinsy_txt, generate_csv

st.set_page_config(page_title="Planejador de Linhas | 4SAS", layout="wide")

st.title("Planejador de Linhas")
st.caption("Módulo Geoespacial para Batimetria (NORMAM-501 / IHO) e Geofísica Rasa (EdgeTech 2000-DSS SSS/SBP)")

# --- GUIA RÁPIDO DE OPERAÇÃO (UX) ---
with st.expander("📌 **Guia Rápido de Operação & Orientação de Rumo (Clique para expandir)**", expanded=True):
    st.markdown("""
    **Como planejar a grade de linhas em 4 passos:**
    
    1. 🖼️ **(Opcional) Subir Imagem GeoTIFF:**
       - Use o campo na barra lateral para carregar a imagem georreferenciada (`.tif` ou `.tiff`). Ela será sobreposta no topo do mapa.
    2. 📏 **Medir o Rumo (Azimute) Ideal:**
       - Ative a ferramenta de linha no mapa (ícone de linha à esquerda) e trace um segmento sobre a feição de referência.
       - O Azimute calculado aparecerá na barra lateral.
    3. ⬡ **Delimitar a Área de Levantamento:**
       - Clique no ícone de **Polígono** no mapa e desenhe o perímetro da área diretamente sobre a imagem carregada.
    4. ⚙️ **Configurar Bordo do Transdutor & Sensor:**
       - Indique a posição de montagem da haste do MBES (Bombordo/Estibordo/Centro) para garantir a cobertura nas margens e exporte o grid pronto (`.lnw`, `.txt`, `.csv`).
    """)

# --- BARRA LATERAL: UPLOAD E PARÂMETROS OPERACIONAIS ---
st.sidebar.header("📂 Imagem de Fundo (GeoTIFF)")
uploaded_geotiff = st.sidebar.file_uploader("Carregar GeoTIFF (.tif / .tiff)", type=["tif", "tiff"])

image_opacity = 0.85
if uploaded_geotiff is not None:
    image_opacity = st.sidebar.slider("Opacidade da Imagem", min_value=0.1, max_value=1.0, value=0.85, step=0.05)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Configurações do Levantamento")

method = st.sidebar.selectbox(
    "Método / Equipamento",
    ["Batimetria (NORMAM-501 / IHO S-44)", "Geofísica Rasa (EdgeTech 2000-DSS SSS/SBP)"]
)

tie_line_spacing = None

if method == "Batimetria (NORMAM-501 / IHO S-44)":
    st.sidebar.subheader("🚤 Instalação do Transdutor (MBES)")
    transducer_pos = st.sidebar.selectbox(
        "Bordo de Montagem da Haste / Sonar",
        [
            "Centro / Quilha (Midship)",
            "Haste a Bombordo (Port Side)",
            "Haste a Estibordo (Starboard Side)",
            "Dual Head (Cabeça Dupla - Inclinado BB/ES)"
        ]
    )
    
    transducer_offset = 0.0
    if "Haste" in transducer_pos:
        transducer_offset = st.sidebar.number_input(
            "Offset Transversal da Haste em Relação ao Centro (m)",
            min_value=0.1, max_value=10.0, value=1.5, step=0.1
        )
        st.sidebar.warning(
            f"⚠️ **Atenção Operacional:** O transdutor está montado a {transducer_offset:.1f}m a "
            f"{'Bombordo' if 'Bombordo' in transducer_pos else 'Estibordo'}. Na navegação próximo a estruturas/margens, "
            f"garanta que este bordo esteja voltado para o raso para manter a cobertura total!"
        )

    norm = st.sidebar.selectbox(
        "Norma / Categoria",
        ["NORMAM-501 Cat A", "NORMAM-501 Cat B", "NORMAM-501 Cat C", "IHO S-44 Special Order", "IHO S-44 Order 1a"]
    )
    depth = st.sidebar.number_input("Profundidade Média Local (m)", min_value=1.0, value=12.0, step=0.5)
    beam_angle = st.sidebar.slider("Abertura do Feixe Multifeixe (°)", min_value=60, max_value=140, value=120)
    overlap = st.sidebar.slider("Sobreposição Mínima (%)", min_value=10, max_value=50, value=20)
    
    line_spacing = calculate_survey_parameters(
        method, depth=depth, norm=norm, beam_angle=beam_angle, overlap=overlap, transducer_pos=transducer_pos
    )

else:  # Geofísica Rasa EdgeTech 2000-DSS
    st.sidebar.subheader("🔊 Parâmetros EdgeTech 2000-DSS")
    range_m = st.sidebar.select_slider(
        "Alcance por Canal SSS (Range em metros)",
        options=[37.5, 50.0, 75.0, 100.0, 150.0, 200.0],
        value=75.0
    )
    
    coverage_opt = st.sidebar.selectbox(
        "Nível de Cobertura SSS",
        [
            "200% - Cobertura Dupla / Padrão Petrobras",
            "150% - 50% de Sobreposição entre faixas",
            "100% - Mosaico Simples (Sem sobreposição)"
        ]
    )
    coverage_pct = 200 if "200%" in coverage_opt else (150 if "150%" in coverage_opt else 100)
    
    line_spacing = calculate_survey_parameters(
        method, range_m=range_m, coverage_pct=coverage_pct
    )
    
    enable_sbp = st.sidebar.checkbox("Gerar Transversais de Amarração (SBP)", value=True)
    if enable_sbp:
        tie_line_spacing = st.sidebar.selectbox(
            "Espaçamento das Transversais SBP (m)",
            [50, 100, 200, 500],
            index=2
        )

st.sidebar.markdown("---")
st.sidebar.subheader("📐 Geometria & Rumo")

azimuth = st.sidebar.number_input("Rumo / Azimute das Linhas Principais (°)", min_value=0.0, max_value=360.0, value=45.0, step=1.0)
manual_spacing_override = st.sidebar.checkbox("Sobrescrever Espaçamento Calculado")

if manual_spacing_override:
    final_spacing = st.sidebar.number_input("Espaçamento Manual (m)", min_value=1.0, value=float(line_spacing), step=1.0)
else:
    final_spacing = line_spacing

st.sidebar.info(f"📏 **Espaçamento Calculado:** {final_spacing:.1f} m")

# --- PROCESSAMENTO DO GEOTIFF E CONFIGURAÇÃO DO MAPA ---
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
        st.sidebar.success("✅ GeoTIFF renderizado com sucesso!")
    except Exception as e:
        st.sidebar.error(f"Erro ao processar GeoTIFF: {e}")

m = folium.Map(location=map_location, zoom_start=map_zoom, tiles="OpenStreetMap")

# Renderização da Imagem por cima do mapa base (zindex=10)
if overlay_img_url and geotiff_bounds:
    folium.raster_layers.ImageOverlay(
        image=overlay_img_url,
        bounds=geotiff_bounds,
        opacity=image_opacity,
        interactive=True,
        zindex=10
    ).add_to(m)
    m.fit_bounds(geotiff_bounds)

# --- RECUPERAÇÃO DO POLÍGONO DE STATE / DESENHO ---
if "last_polygon" not in st.session_state:
    st.session_state["last_polygon"] = None

# Se já houver um polígono salvo, desenha as linhas calculadas no próprio mapa
if st.session_state["last_polygon"]:
    current_lines = generate_survey_lines(
        st.session_state["last_polygon"], azimuth, final_spacing, tie_line_spacing
    )
    for line in current_lines:
        color = "#E65100" if line["type"].startswith("Amarração") else "#0D47A1"
        dash_array = "5, 5" if line["type"].startswith("Amarração") else None
        
        folium.PolyLine(
            locations=line["coords_wgs84"],
            color=color,
            weight=2.5,
            dash_array=dash_array,
            popup=f"Linha: {line['id']} | Az: {line['azimuth']}° | Comp: {line['length_m']}m"
        ).add_to(m)

# Ferramentas de Desenho no Mapa
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

# --- PROCESSAMENTO DOS DADOS DESENHADOS NO MAPA ---
polygon_geom = st.session_state["last_polygon"]
measured_bearing = None

if map_data and map_data.get("all_drawings"):
    drawings = map_data["all_drawings"]
    
    for feature in drawings:
        geom_type = feature["geometry"]["type"]
        coords = feature["geometry"]["coordinates"]
        
        # Medição de Rumo (Linha)
        if geom_type == "LineString" and len(coords) >= 2:
            lon1, lat1 = coords[0]
            lon2, lat2 = coords[1]
            measured_bearing = calculate_bearing(lat1, lon1, lat2, lon2)
            st.sidebar.success(f"🎯 Azimute Medido no Mapa: **{measured_bearing:.1f}°**")
            
        # Área do Levantamento (Polígono)
        elif geom_type in ["Polygon"]:
            polygon_geom = feature["geometry"]
            st.session_state["last_polygon"] = polygon_geom

# --- GERAÇÃO E EXIBIÇÃO DE MÉTRICAS & DOWNLOADS ---
if polygon_geom:
    generated_lines = generate_survey_lines(
        polygon_geom, azimuth, final_spacing, tie_line_spacing
    )
    
    if generated_lines:
        total_len_km = sum(l["length_m"] for l in generated_lines) / 1000.0
        n_main = sum(1 for l in generated_lines if l["type"].startswith("Principal"))
        n_tie = len(generated_lines) - n_main
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Espaçamento Principal", f"{final_spacing:.1f} m")
        col2.metric("Linhas Principais", f"{n_main}")
        col3.metric("Transversais (SBP)", f"{n_tie}")
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
        st.warning("⚠️ O polígono desenhado é muito pequeno para o espaçamento selecionado.")
else:
    st.info("💡 Suba uma imagem GeoTIFF ou desenhe um **Polígono** no mapa para gerar o grid automático.")