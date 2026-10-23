import rasterio
from rasterio.io import MemoryFile
from pyproj import Transformer
import streamlit as st
from shapely.geometry import shape, Polygon, LineString
import numpy as np
import math

@st.cache_data
def get_image_bounds_from_bytes(file_bytes: bytes):
    """Extrai os limites da imagem e converte para Lat/Lon (WGS84) para o Folium."""
    try:
        with MemoryFile(file_bytes) as memfile:
            with memfile.open() as dataset:
                bounds = dataset.bounds
                crs = dataset.crs
                if not crs:
                    return None
                transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
                lon_min, lat_min = transformer.transform(bounds.left, bounds.bottom)
                lon_max, lat_max = transformer.transform(bounds.right, bounds.top)
                return [[lat_min, lon_min], [lat_max, lon_max]]
    except Exception as e:
        st.error(f"Erro ao processar georeferenciamento: {e}")
        return None

def calculate_survey_parameters(sensor, scope, depth):
    """Calcula o espaçamento das linhas baseado na NORMAM-501 e no sensor."""
    spacing = 10
    justification = ""
    
    if "MBES" in sensor:
        swath = 3.4 * depth
        if "Ordem Especial" in scope:
            spacing = swath * 0.8
            justification = f"Multifeixe em {depth}m (varredura ~{swath:.1f}m). Para {scope}, adotou-se espaçamento de {spacing:.1f}m garantindo 100% de cobertura + 20% de sobreposição (NORMAM-501)."
        else:
            spacing = swath * 1.5
            justification = f"Multifeixe de Reconhecimento. Espaçamento relaxado para {spacing:.1f}m para maximizar eficiência de área coberta."
            
    elif "SBES" in sensor:
        if "Ordem Especial" in scope:
            spacing = 25
            justification = f"Monofeixe em {scope}. Distância máxima restrita a {spacing}m para adensamento rigoroso da batimetria."
        else:
            spacing = 50
            justification = f"Monofeixe em {scope}. Adotado espaçamento de {spacing}m seguindo padrão de menor restrição."
            
    return spacing, justification

def generate_survey_lines(geojson_polygon, spacing_meters, heading_degrees):
    """Gera um grid de linhas paralelas recortadas dentro do polígono."""
    poly = shape(geojson_polygon)
    minx, miny, maxx, maxy = poly.bounds
    
    mean_lat = math.radians((miny + maxy) / 2)
    deg_to_meters_y = 111320.0
    deg_to_meters_x = 111320.0 * math.cos(mean_lat)
    
    spacing_deg_y = spacing_meters / deg_to_meters_y
    lines = []
    angle_rad = math.radians(heading_degrees)
    
    diagonal = math.hypot(maxx - minx, maxy - miny)
    center_x = (minx + maxx) / 2
    center_y = (miny + maxy) / 2
    
    num_lines = int((diagonal * 2) / spacing_deg_y)
    
    for i in range(-num_lines, num_lines):
        offset = i * spacing_deg_y
        p1_x = center_x - diagonal * math.sin(angle_rad) + offset * math.cos(angle_rad)
        p1_y = center_y - diagonal * math.cos(angle_rad) - offset * math.sin(angle_rad)
        p2_x = center_x + diagonal * math.sin(angle_rad) + offset * math.cos(angle_rad)
        p2_y = center_y + diagonal * math.cos(angle_rad) - offset * math.sin(angle_rad)
        
        line = LineString([(p1_x, p1_y), (p2_x, p2_y)])
        intersected = line.intersection(poly)
        
        if not intersected.is_empty:
            if intersected.geom_type == 'MultiLineString':
                for geom in intersected.geoms:
                    lines.append(geom)
            elif intersected.geom_type == 'LineString':
                lines.append(intersected)
                
    return lines

def calculate_bearing(lon1, lat1, lon2, lat2):
    """Calcula o rumo verdadeiro (azimute em graus) entre dois pontos na Terra."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
    
    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360
    
    return round(compass_bearing, 1)