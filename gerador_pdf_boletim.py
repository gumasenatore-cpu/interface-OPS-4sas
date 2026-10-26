import tempfile
import os
import io
import math
import requests
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
)
from reportlab.pdfgen import canvas

# --- PALETA DE CORES BRANDBOOK 4SAS ---
COLOR_PRIMARY = colors.HexColor("#F32735")      # Vermelho 4SAS
COLOR_FAVORAVEL = colors.HexColor("#2E7D32")    # Verde
COLOR_ATENCAO = colors.HexColor("#E5E1E6")      # Cinza (Avaliação Técnica)
COLOR_NOGO = colors.HexColor("#F32735")         # Vermelho
COLOR_BG_LIGHT = colors.HexColor("#F8F9FA")
COLOR_TEXT_DARK = colors.HexColor("#2C3E50")

class NumberedCanvas4SAS(canvas.Canvas):
    """Canvas para Portrait A4 com rodapé discreto e sem cabeçalho no topo."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        page_w, _ = A4
        
        self.setFont("Helvetica-Oblique", 8)
        self.setFillColor(colors.HexColor("#7F8C8D"))
        self.drawString(36, 20, "www.4sas.com.br")
        self.drawCentredString(page_w / 2.0, 20, f"Página {self._pageNumber} de {page_count}")
        
        logo_path = "logo2.png" if os.path.exists("logo2.png") else ("logo.png" if os.path.exists("logo.png") else None)
        if logo_path:
            try:
                self.drawImage(logo_path, page_w - 70, 12, width=40, height=14, preserveAspectRatio=True, mask='auto')
            except Exception:
                pass
                
        self.restoreState()


def gerar_mapa_estatico_quadrado(lat_val, lon_val, zoom=10):
    def deg2num(lat_deg, lon_deg, z):
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** z
        xtile = int((lon_deg + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (xtile, ytile)

    try:
        xtile, ytile = deg2num(lat_val, lon_val, zoom)
        map_img = Image.new('RGB', (768, 768), color='#e5e1e6')
        headers = {'User-Agent': 'BoletimOperacional4SAS/1.0'}
        
        for i in range(-1, 2):
            for j in range(-1, 2):
                x, y = xtile + i, ytile + j
                url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
                try:
                    r = requests.get(url, headers=headers, stream=True, timeout=2)
                    if r.status_code == 200:
                        tile = Image.open(r.raw).convert("RGB")
                        map_img.paste(tile, ((i+1)*256, (j+1)*256))
                except Exception:
                    pass
                    
        n = 2.0 ** zoom
        x_exact = (lon_val + 180.0) / 360.0 * n
        y_exact = (1.0 - math.asinh(math.tan(math.radians(lat_val))) / math.pi) / 2.0 * n
        
        px = int(256 + (x_exact - xtile) * 256)
        py = int(256 + (y_exact - ytile) * 256)
        
        draw = ImageDraw.Draw(map_img)
        r_dot = 10
        draw.ellipse([px - r_dot, py - r_dot, px + r_dot, py + r_dot], fill='#F32735', outline='black', width=2)
        
        crop_box = (px - 200, py - 200, px + 200, py + 200)
        final_img = map_img.crop(crop_box)
        
        f_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
        final_img.save(f_path)
        return f_path
    except Exception:
        img = Image.new('RGB', (400, 400), color='#e5e1e6')
        f_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
        img.save(f_path)
        return f_path


def gerar_pdf_boletim_reportlab(dataframe, local_nome, dias_janela, favoraveis, tecnicas, nogo, df_heatmap, lat, lon, equipamentos, limite_onda, limite_vento, limite_corrente, data_emissao):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4, # RETRATO (PORTRAIT)
        leftMargin=36,
        rightMargin=36,
        topMargin=25,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=13,
        textColor=COLOR_PRIMARY,
        spaceAfter=2
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        textColor=COLOR_TEXT_DARK,
        spaceAfter=3
    )
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=COLOR_PRIMARY,
        spaceBefore=6,
        spaceAfter=4
    )

    story = []

    # Cabeçalho Inicial
    header_data = [
        [
            Paragraph("<b>4SAS INTELIGÊNCIA MARÍTIMA</b>", title_style),
            Paragraph(f"<b>Emissão:</b> {data_emissao}", subtitle_style)
        ],
        [
            Paragraph("<b>BOLETIM METEOCEANOGRÁFICO OPERACIONAL</b>", ParagraphStyle('Sub', fontName='Helvetica-Bold', fontSize=11, textColor=COLOR_PRIMARY)),
            Paragraph(f"<b>Janela:</b> {dias_janela} dias | <b>Local:</b> {local_nome}", subtitle_style)
        ]
    ]
    t_header = Table(header_data, colWidths=[340, 180])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
    ]))
    story.append(t_header)

    eq_txt = ", ".join(equipamentos) if equipamentos else "Nenhum"
    corr_txt = f" | Corrente <= {limite_corrente} kn" if limite_corrente < 10.0 else ""
    info_box = [
        [Paragraph(f"<b>Equipamentos em Operação:</b> {eq_txt}", subtitle_style)],
        [Paragraph(f"<b>Limiares Ativos (Consenso):</b> Onda <= {limite_onda} m | Vento <= {limite_vento} kn{corr_txt}", subtitle_style)]
    ]
    t_info = Table(info_box, colWidths=[520])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 8))

    # Mapa Quadrado Proporcional (Centrado)
    map_img_path = gerar_mapa_estatico_quadrado(lat, lon, zoom=10)
    img_map_rl = RLImage(map_img_path, width=220, height=140)
    
    t_map = Table([[img_map_rl]], colWidths=[520])
    t_map.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    story.append(t_map)
    story.append(Spacer(1, 8))

    # Donut (Rosca) - COM COR CINZA PARA AVALIAÇÃO TÉCNICA
    fig_donut, ax_donut = plt.subplots(figsize=(3.5, 2.5))
    labels = ['FAVORAVEL', 'AVALIACAO TECNICA', 'SEM OPERACAO']
    sizes = [favoraveis, tecnicas, nogo]
    colors_donut = ['#2E7D32', '#E5E1E6', '#F32735'] # Verde, CINZA, Vermelho
    
    plot_labels = [l for s, l in zip(sizes, labels) if s > 0]
    plot_sizes = [s for s in sizes if s > 0]
    plot_colors = [c for s, c in zip(sizes, colors_donut) if s > 0]

    wedges, texts, autotexts = ax_donut.pie(
        plot_sizes, colors=plot_colors, autopct='%1.1f%%', startangle=90,
        wedgeprops=dict(width=0.4, edgecolor='w')
    )
    ax_donut.axis('equal')
    ax_donut.legend(wedges, plot_labels, title="Status", loc="center left", bbox_to_anchor=(0.85, 0.5), frameon=False, fontsize=6)
    
    f_donut = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    plt.savefig(f_donut, bbox_inches='tight', dpi=150)
    plt.close(fig_donut)

    # Matrix Kanban - COM COR CINZA PARA AVALIAÇÃO TÉCNICA
    fig_tl, ax_tl = plt.subplots(figsize=(5.5, 2.5))
    cmap_kanban = mcolors.ListedColormap(['#2E7D32', '#E5E1E6', '#F32735']) # Verde, CINZA, Vermelho
    bounds = [-0.5, 0.5, 1.5, 2.5]
    norm = mcolors.BoundaryNorm(bounds, cmap_kanban.N)

    ax_tl.imshow(df_heatmap.values, cmap=cmap_kanban, norm=norm, aspect='auto')
    ax_tl.set_xticks(np.arange(len(df_heatmap.columns)))
    ax_tl.set_xticklabels([f"{h:02d}h" for h in df_heatmap.columns], fontsize=6, rotation=45)
    ax_tl.set_yticks(np.arange(len(df_heatmap.index)))
    ax_tl.set_yticklabels(df_heatmap.index, fontsize=7)
    ax_tl.set_xticks(np.arange(-.5, len(df_heatmap.columns), 1), minor=True)
    ax_tl.set_yticks(np.arange(-.5, len(df_heatmap.index), 1), minor=True)
    ax_tl.grid(which="minor", color="w", linestyle='-', linewidth=1.0)
    ax_tl.tick_params(which="minor", bottom=False, left=False)
    ax_tl.set_title("Matriz Operacional de Janela (Go / No-Go)", fontsize=8, fontweight='bold')
    for spine in ax_tl.spines.values(): spine.set_visible(False)

    f_timeline = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    plt.savefig(f_timeline, bbox_inches='tight', dpi=150)
    plt.close(fig_tl)

    # Disposição Lado a Lado na Página 1: Donut (Esquerda) + Kanban (Direita)
    t_row_graphics = Table([[RLImage(f_donut, width=210, height=130), RLImage(f_timeline, width=300, height=130)]], colWidths=[215, 305])
    t_row_graphics.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    story.append(t_row_graphics)

    # Página 2: Gráficos de Linha
    story.append(PageBreak())
    story.append(Paragraph("Análise Comparativa de Modelos Numéricos", section_style))
    story.append(Spacer(1, 4))

    fig, ax = plt.subplots(figsize=(7, 2.2))
    ax.plot(dataframe['Data_Hora'], dataframe['Onda_ECMWF(m)'], label='ECMWF', color='#1f77b4', linewidth=1)
    ax.plot(dataframe['Data_Hora'], dataframe['Onda_WW3(m)'], label='WW3', color='#e377c2', linewidth=1)
    ax.plot(dataframe['Data_Hora'], dataframe['Onda_Consenso(m)'], label='Consenso', color='#F32735', linewidth=2.0)
    ax.set_title('Altura Significativa de Onda (m)', fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %Hh'))
    plt.xticks(rotation=30, fontsize=6)
    ax.legend(loc='upper right', fontsize=6)
    f_onda = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    plt.savefig(f_onda, bbox_inches='tight', dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 2.2))
    ax.plot(dataframe['Data_Hora'], dataframe['Vento_ECMWF_Nos'], label='ECMWF', color='#1f77b4', linewidth=1)
    ax.plot(dataframe['Data_Hora'], dataframe['Vento_GFS_Nos'], label='GFS', color='#2ca02c', linewidth=1)
    ax.plot(dataframe['Data_Hora'], dataframe['Vento_ICON_Nos'], label='ICON', color='#FFD700', linewidth=1.2)
    ax.plot(dataframe['Data_Hora'], dataframe['Vento_Consenso_Nos'], label='Consenso', color='#F32735', linewidth=2.0)
    ax.set_title('Velocidade de Vento (kn)', fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %Hh'))
    plt.xticks(rotation=30, fontsize=6)
    ax.legend(loc='upper right', fontsize=6)
    f_vento = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    plt.savefig(f_vento, bbox_inches='tight', dpi=150)
    plt.close(fig)

    story.append(RLImage(f_onda, width=520, height=140))
    story.append(Spacer(1, 6))
    story.append(RLImage(f_vento, width=520, height=140))
    story.append(Spacer(1, 6))

    fig, ax = plt.subplots(figsize=(7, 2.0))
    ax.plot(dataframe['Data_Hora'], dataframe['Mare_Altura(m)'], label='Nível Maré (m)', color='#1BF6E6', linewidth=2)
    ax.plot(dataframe['Data_Hora'], dataframe['Corrente_Vel_Nos'], label='Corrente (kn)', color='#000000', linewidth=1.8)
    ax.set_title('Comportamento de Correntes Estuarinas e Maré', fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %Hh'))
    plt.xticks(rotation=30, fontsize=6)
    ax.legend(loc='upper right', fontsize=6)
    f_corr = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    plt.savefig(f_corr, bbox_inches='tight', dpi=150)
    plt.close(fig)

    story.append(RLImage(f_corr, width=520, height=130))

    # Página 3: Tabela Detalhada
    story.append(PageBreak())
    story.append(Paragraph("Tabela Detalhada de Dados Operacionais", section_style))
    story.append(Spacer(1, 4))

    table_data = [["Data / Hora", "Maré (m)", "Fase", "Onda Cons.", "Vento Cons.", "Corrente", "Status"]]
    for _, row in dataframe.iterrows():
        table_data.append([
            str(row['Data_Hora'])[:-3],
            f"{row['Mare_Altura(m)']:.2f}",
            str(row['Fase_Estuario']),
            f"{row['Onda_Consenso(m)']:.2f} m ({row['Onda_Dir']})",
            f"{row['Vento_Consenso_Nos']:.1f} kn ({row['Vento_Dir']})",
            f"{row['Corrente_Vel_Nos']} kn ({row['Corrente_Dir']})",
            str(row['Status'])
        ])

    t_data = Table(table_data, colWidths=[85, 45, 60, 85, 85, 80, 80], repeatRows=1)
    t_data.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_PRIMARY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 7.5),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, COLOR_BG_LIGHT]),
        ('FONTSIZE', (0,1), (-1,-1), 6.5),
        ('PADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t_data)

    doc.build(story, canvasmaker=NumberedCanvas4SAS)
    buffer.seek(0)
    return buffer.getvalue()