import math
import io
import base64
import rasterio
from rasterio.io import MemoryFile
import pyproj
import numpy as np
from PIL import Image
from shapely.geometry import shape, Polygon, LineString
from shapely.affinity import rotate

def get_geotiff_overlay_data(file_bytes):
    """
    Lê os bytes de um GeoTIFF, extrai os pixels e retorna uma URL Base64 (Data URI)
    com os limites [[lat_min, lon_min], [lat_max, lon_max]] em EPSG:4326.
    """
    with MemoryFile(file_bytes) as memfile:
        with memfile.open() as dataset:
            bounds = dataset.bounds
            crs = dataset.crs
            
            # Conversão de coordenadas para WGS84 (EPSG:4326)
            if crs and crs.to_epsg() != 4326:
                transformer = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
                lon1, lat1 = transformer.transform(bounds.left, bounds.bottom)
                lon2, lat2 = transformer.transform(bounds.right, bounds.top)
                
                lat_min, lat_max = min(lat1, lat2), max(lat1, lat2)
                lon_min, lon_max = min(lon1, lon2), max(lon1, lon2)
            else:
                lat_min, lat_max = min(bounds.bottom, bounds.top), max(bounds.bottom, bounds.top)
                lon_min, lon_max = min(bounds.left, bounds.right), max(bounds.left, bounds.right)
                
            bounds_folium = [[lat_min, lon_min], [lat_max, lon_max]]
            
            # Leitura dos canais de imagem (RGB / RGBA / Grayscale)
            count = dataset.count
            if count >= 3:
                bands = [1, 2, 3] if count == 3 else [1, 2, 3, 4]
                arr = dataset.read(bands)
                arr = np.transpose(arr, (1, 2, 0))
            elif count == 1:
                arr = dataset.read(1)
                arr_min, arr_max = np.nanmin(arr), np.nanmax(arr)
                if arr_max > arr_min:
                    norm = ((arr - arr_min) / (arr_max - arr_min) * 255).astype(np.uint8)
                else:
                    norm = np.zeros_like(arr, dtype=np.uint8)
                arr = np.stack([norm, norm, norm], axis=-1)
            else:
                arr = dataset.read(1)
                arr = np.stack([arr, arr, arr], axis=-1)
                
            if arr.dtype != np.uint8:
                arr = np.clip(arr, 0, 255).astype(np.uint8)
                
            img = Image.fromarray(arr)
            
            # Converte a imagem PIL para string Base64 Data URI
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            image_data_url = f"data:image/png;base64,{img_str}"
            
            return image_data_url, bounds_folium

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calcula o Azimute em graus entre dois pontos geográficos."""
    d_lon = math.radians(lon2 - lon1)
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    
    x = math.sin(d_lon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - (math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(d_lon))
    
    initial_bearing = math.atan2(x, y)
    compass_bearing = (math.degrees(initial_bearing) + 360) % 360
    return round(compass_bearing, 2)

def calculate_survey_parameters(method, **kwargs):
    """Calcula o espaçamento das linhas considerando MBES (com montagem de bordo) ou Sonar de Varredura Lateral."""
    if method == "Batimetria (NORMAM-501 / IHO S-44)":
        depth = kwargs.get("depth", 10.0)
        norm = kwargs.get("norm", "NORMAM-501 Cat A")
        beam_angle = kwargs.get("beam_angle", 120.0)
        overlap = kwargs.get("overlap", 20.0)
        
        # Consideração da Posição de Instalação do Transdutor
        transducer_pos = kwargs.get("transducer_pos", "Centro / Quilha")
        
        # Abertura efetiva expandida para Dual-Head
        effective_beam = beam_angle * 1.25 if "Dual Head" in transducer_pos else beam_angle
        
        swath = 2 * depth * math.tan(math.radians(effective_beam / 2.0))
        spacing = swath * (1 - (overlap / 100.0))
        
        return max(round(spacing, 1), 2.0)
        
    elif method == "Geofísica Rasa (EdgeTech 2000-DSS SSS/SBP)":
        range_m = kwargs.get("range_m", 75.0)
        coverage_pct = kwargs.get("coverage_pct", 200)
        spacing = (2 * range_m) / (coverage_pct / 100.0)
        return round(spacing, 1)

def _get_utm_epsg(lon, lat):
    """Retorna o código EPSG UTM para a coordenada dada."""
    zone = int((lon + 180) / 6) + 1
    hemisphere = 32700 if lat < 0 else 32600
    return hemisphere + zone

def generate_survey_lines(polygon_geojson, azimuth, spacing_m, tie_line_spacing_m=None):
    """Gera linhas de survey cortadas no polígono da área."""
    poly_geom = shape(polygon_geojson)
    centroid = poly_geom.centroid
    
    utm_epsg = _get_utm_epsg(centroid.x, centroid.y)
    transformer_to_utm = pyproj.Transformer.from_crs("EPSG:4326", f"EPSG:{utm_epsg}", always_xy=True)
    transformer_to_wgs = pyproj.Transformer.from_crs(f"EPSG:{utm_epsg}", "EPSG:4326", always_xy=True)
    
    utm_coords = [transformer_to_utm.transform(x, y) for x, y in poly_geom.exterior.coords]
    utm_poly = Polygon(utm_coords)
    utm_centroid = utm_poly.centroid
    
    lines_output = []
    
    def _create_grid(angle_deg, step_m, prefix):
        rotated_poly = rotate(utm_poly, -angle_deg, origin=utm_centroid)
        minx, miny, maxx, maxy = rotated_poly.bounds
        
        y_coords = []
        current_y = miny + (step_m / 2.0)
        while current_y <= maxy:
            y_coords.append(current_y)
            current_y += step_m
            
        line_num = 1
        for y in y_coords:
            raw_line = LineString([(minx - 2000, y), (maxx + 2000, y)])
            unrotated_line = rotate(raw_line, angle_deg, origin=utm_centroid)
            clipped = utm_poly.intersection(unrotated_line)
            
            if clipped.is_empty:
                continue
                
            geoms = [clipped] if isinstance(clipped, LineString) else list(clipped.geoms) if hasattr(clipped, 'geoms') else []
            
            for g in geoms:
                if isinstance(g, LineString) and g.length > 1.0:
                    wgs_coords = [transformer_to_wgs.transform(x, y) for x, y in g.coords]
                    length_m = round(g.length, 1)
                    
                    line_name = f"{prefix}{line_num:03d}"
                    lines_output.append({
                        "id": line_name,
                        "type": "Principal (SSS/Bat)" if prefix == "L" else "Amarração (SBP)",
                        "azimuth": angle_deg % 360,
                        "length_m": length_m,
                        "coords_wgs84": [[lat, lon] for lon, lat in wgs_coords],
                        "coords_xy": list(g.coords)
                    })
                    line_num += 1

    # 1. Linhas Principais
    _create_grid(azimuth, spacing_m, "L")
    
    # 2. Transversais de Amarração (SBP)
    if tie_line_spacing_m and tie_line_spacing_m > 0:
        _create_grid(azimuth + 90, tie_line_spacing_m, "T")
        
    return lines_output