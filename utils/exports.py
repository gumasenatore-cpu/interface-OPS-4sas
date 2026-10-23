import pandas as pd
import math
from shapely.geometry import LineString

def haversine_length(lon1, lat1, lon2, lat2):
    """Calcula a distância real em metros entre duas coordenadas geográficas."""
    R = 6371000  # Raio da Terra em metros
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def generate_csv_report(lines, heading):
    """Gera o relatório operacional em CSV (Nome, Início, Fim, Rumo, Comprimento)."""
    data = []
    for i, line in enumerate(lines):
        # Extrai coordenadas (Shapely usa Lon, Lat)
        lon1, lat1 = line.coords[0]
        lon2, lat2 = line.coords[-1]
        
        length_m = haversine_length(lon1, lat1, lon2, lat2)
        
        data.append({
            "Nome_Linha": f"L_{i+1:03d}",
            "Lat_Inicio": round(lat1, 6),
            "Lon_Inicio": round(lon1, 6),
            "Lat_Fim": round(lat2, 6),
            "Lon_Fim": round(lon2, 6),
            "Rumo_Graus": heading,
            "Comprimento_m": round(length_m, 2)
        })
        
    df = pd.DataFrame(data)
    # Retorna o CSV em formato de bytes para o Streamlit fazer o download
    return df.to_csv(index=False).encode('utf-8')

def generate_hypack_lnw(lines):
    """Gera o arquivo de linhas nativo do Hypack (.lnw)."""
    lnw_content = "LNW 3\n" # Cabeçalho padrão Hypack
    
    for i, line in enumerate(lines):
        lon1, lat1 = line.coords[0]
        lon2, lat2 = line.coords[-1]
        
        lnw_content += f"LIN {i+1}\n"
        lnw_content += f"PTS\n"
        # O Hypack usa X (Easting/Lon) e Y (Northing/Lat)
        lnw_content += f"{lon1:.7f} {lat1:.7f}\n"
        lnw_content += f"{lon2:.7f} {lat2:.7f}\n"
        lnw_content += "LNE\n"
        
    return lnw_content.encode('utf-8')

def generate_qinsy_txt(lines):
    """Gera arquivo ASCII genérico para importação de linhas no Qinsy."""
    # Formato: Nome, X1, Y1, X2, Y2
    qinsy_content = "Name,Lon_Start,Lat_Start,Lon_End,Lat_End\n"
    
    for i, line in enumerate(lines):
        lon1, lat1 = line.coords[0]
        lon2, lat2 = line.coords[-1]
        qinsy_content += f"L_{i+1:03d},{lon1:.7f},{lat1:.7f},{lon2:.7f},{lat2:.7f}\n"
        
    return qinsy_content.encode('utf-8')