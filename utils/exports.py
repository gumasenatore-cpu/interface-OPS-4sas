import io
import csv

def generate_hypack_lnw(lines):
    """
    Gera o conteúdo de linhas de navegação no formato HYPACK (.lnw).
    """
    output = []
    output.append("LNW 1.0")
    output.append(f"TPL {len(lines)}")
    
    for line in lines:
        coords = line.get("coords_wgs84", [])
        output.append(f"LINE {line['id']}")
        output.append(f"PTS {len(coords)}")
        for lat, lon in coords:
            output.append(f"  {lat:.8f} {lon:.8f}")
        output.append("ENDLINE")
        
    return "\n".join(output)

def generate_qinsy_txt(lines):
    """
    Gera o conteúdo de linhas de navegação no formato Qinsy (.txt).
    """
    output = []
    output.append("# Qinsy Line File")
    output.append("# Line_ID, Latitude, Longitude")
    
    for line in lines:
        coords = line.get("coords_wgs84", [])
        output.append(f"LINE {line['id']}")
        for lat, lon in coords:
            output.append(f"{lat:.8f}, {lon:.8f}")
        output.append("END")
        
    return "\n".join(output)

def generate_csv(lines):
    """
    Gera arquivo CSV com a lista de pontos, azimutes e comprimentos de cada linha de survey.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Cabeçalho do arquivo
    writer.writerow(["line_id", "type", "azimuth_deg", "length_m", "point_index", "latitude_wgs84", "longitude_wgs84"])
    
    for line in lines:
        line_id = line.get("id", "")
        line_type = line.get("type", "Principal")
        azimuth = line.get("azimuth", 0)
        length_m = line.get("length_m", 0)
        
        for pt_idx, (lat, lon) in enumerate(line.get("coords_wgs84", []), 1):
            writer.writerow([line_id, line_type, azimuth, length_m, pt_idx, lat, lon])
            
    return output.getvalue()