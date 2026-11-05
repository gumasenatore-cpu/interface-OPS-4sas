import io
import math
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.colors as mcolors
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from PIL import Image, ImageDraw

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# --- PALETA DE CORES BRANDBOOK 4SAS ---
COLOR_PRIMARY = colors.HexColor("#0A192F")      # Azul Escuro Corporativo
COLOR_ACCENT = colors.HexColor("#F32735")       # Vermelho 4SAS
COLOR_FAVORAVEL = colors.HexColor("#2E7D32")    # Verde
COLOR_ATENCAO = colors.HexColor("#7F8C8D")      # Cinza (Avaliação Técnica)
COLOR_NOGO = colors.HexColor("#F32735")         # Vermelho
COLOR_BG_LIGHT = colors.HexColor("#F8F9FA")
COLOR_TEXT_DARK = colors.HexColor("#1A202C")
COLOR_BORDER = colors.HexColor("#CBD5E1")


class NumberedCanvas4SAS(canvas.Canvas):
    """Canvas para Portrait A4 com rodapé institucional 4SAS."""

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

        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#7F8C8D"))
        self.drawString(36, 20, "www.4sas.com.br")
        self.drawCentredString(page_w / 2.0, 20, f"Página {self._pageNumber} de {page_count}")

        logo_path = "assets/logo_doc.png" if os.path.exists("assets/logo_doc.png") else (
            "logo2.png" if os.path.exists("logo2.png") else ("logo.png" if os.path.exists("logo.png") else None)
        )
        if logo_path:
            try:
                self.drawImage(logo_path, page_w - 80, 12, width=44, height=14, preserveAspectRatio=True, mask='auto')
            except Exception:
                pass

        self.restoreState()


def gerar_mapa_estatico_quadrado(lat_val, lon_val, zoom=10) -> io.BytesIO:
    """Gera o mapa estático tile-based e retorna o buffer BytesIO em memória."""
    def deg2num(lat_deg, lon_deg, z):
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** z
        xtile = int((lon_deg + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (xtile, ytile)

    buf = io.BytesIO()
    try:
        xtile, ytile = deg2num(lat_val, lon_val, zoom)
        map_img = Image.new('RGB', (768, 768), color='#E5E1E6')
        headers = {'User-Agent': 'BoletimOperacional4SAS/1.0'}

        for i in range(-1, 2):
            for j in range(-1, 2):
                x, y = xtile + i, ytile + j
                url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
                try:
                    r = requests.get(url, headers=headers, stream=True, timeout=3)
                    if r.status_code == 200:
                        tile = Image.open(r.raw).convert("RGB")
                        map_img.paste(tile, ((i + 1) * 256, (j + 1) * 256))
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
        final_img.save(buf, format='PNG')
    except Exception:
        img = Image.new('RGB', (400, 400), color='#E5E1E6')
        img.save(buf, format='PNG')

    buf.seek(0)
    return buf


def gerar_pdf_boletim_reportlab(dataframe, local_nome, dias_janela, favoraveis, tecnicas, nogo, df_heatmap, lat, lon, equipamentos, limite_onda, limite_vento, limite_corrente, data_emissao):
    """Gera o boletim PDF operacional 4SAS sem imagem no topo e com título em fonte vermelha limpa."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=25,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Estilo do Título Principal (Sem fundo, fonte vermelha)
    title_style = ParagraphStyle(
        'DocTitleClean',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=COLOR_ACCENT,
        alignment=0,
        spaceAfter=0
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=COLOR_TEXT_DARK
    )
    meta_label_style = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=COLOR_PRIMARY
    )
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=COLOR_PRIMARY,
        spaceBefore=8,
        spaceAfter=4
    )

    story = []

    # 1. Cabeçalho Inicial Limpo (Título em Texto Vermelho)
    story.append(Paragraph("<b>BOLETIM METEOCEANOGRÁFICO OPERACIONAL</b>", title_style))
    story.append(Spacer(1, 10))

    # 2. Quadro de Metadados da Operação
    eq_txt = ", ".join(equipamentos) if equipamentos else "Nenhum"
    corr_txt = f" | Corrente ≤ {limite_corrente} kn" if limite_corrente < 10.0 else ""

    meta_grid = [
        [
            Paragraph("CÓDIGO PROJETO:", meta_label_style), Paragraph(f"4SAS-{local_nome.upper()}", subtitle_style),
            Paragraph("EMISSÃO:", meta_label_style), Paragraph(str(data_emissao), subtitle_style)
        ],
        [
            Paragraph("LOCAL:", meta_label_style), Paragraph(str(local_nome), subtitle_style),
            Paragraph("JANELA:", meta_label_style), Paragraph(f"{dias_janela} Dias", subtitle_style)
        ],
        [
            Paragraph("EQUIPAMENTOS:", meta_label_style), Paragraph(eq_txt, subtitle_style),
            Paragraph("LIMIARES ATIVOS:", meta_label_style), Paragraph(f"Onda ≤ {limite_onda}m | Vento ≤ {limite_vento}kn{corr_txt}", subtitle_style)
        ]
    ]
    t_info = Table(meta_grid, colWidths=[90, 171, 90, 172])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 8))

    # 3. Mapa de Localização
    map_buf = gerar_mapa_estatico_quadrado(lat, lon, zoom=10)
    img_map_rl = RLImage(map_buf, width=220, height=130)
    t_map = Table([[img_map_rl]], colWidths=[523])
    t_map.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
    story.append(t_map)
    story.append(Spacer(1, 8))

    # 4. Gráfico Donut (Distribuição de Status)
    fig_donut, ax_donut = plt.subplots(figsize=(3.2, 2.2), dpi=200)
    labels = ['FAVORAVEL', 'AVALIACAO TECNICA', 'SEM OPERACAO']
    sizes = [favoraveis, tecnicas, nogo]
    colors_donut = ['#2E7D32', '#7F8C8D', '#F32735']

    plot_labels = [l for s, l in zip(sizes, labels) if s > 0]
    plot_sizes = [s for s in sizes if s > 0]
    plot_colors = [c for s, c in zip(sizes, colors_donut) if s > 0]

    wedges, texts, autotexts = ax_donut.pie(
        plot_sizes, colors=plot_colors, autopct='%1.1f%%', startangle=90,
        pctdistance=0.75, wedgeprops=dict(width=0.4, edgecolor='w')
    )
    plt.setp(autotexts, size=6, weight="bold", color="white")
    ax_donut.axis('equal')
    ax_donut.legend(wedges, plot_labels, title="Status", loc="center left", bbox_to_anchor=(0.85, 0.5), frameon=False, fontsize=5.5)

    buf_donut = io.BytesIO()
    plt.savefig(buf_donut, format='png', bbox_inches='tight', dpi=200)
    plt.close(fig_donut)
    buf_donut.seek(0)

    # 5. Gráfico Matrix Kanban
    fig_tl, ax_tl = plt.subplots(figsize=(5.5, 2.2), dpi=200)
    cmap_kanban = mcolors.ListedColormap(['#2E7D32', '#7F8C8D', '#F32735'])
    bounds = [-0.5, 0.5, 1.5, 2.5]
    norm = mcolors.BoundaryNorm(bounds, cmap_kanban.N)

    ax_tl.imshow(df_heatmap.values, cmap=cmap_kanban, norm=norm, aspect='auto')
    ax_tl.set_xticks(np.arange(len(df_heatmap.columns)))
    ax_tl.set_xticklabels([f"{h:02d}h" for h in df_heatmap.columns], fontsize=5.5, rotation=45)
    ax_tl.set_yticks(np.arange(len(df_heatmap.index)))
    ax_tl.set_yticklabels(df_heatmap.index, fontsize=6.5)
    ax_tl.set_xticks(np.arange(-.5, len(df_heatmap.columns), 1), minor=True)
    ax_tl.set_yticks(np.arange(-.5, len(df_heatmap.index), 1), minor=True)
    ax_tl.grid(which="minor", color="w", linestyle='-', linewidth=1.0)
    ax_tl.tick_params(which="minor", bottom=False, left=False)
    ax_tl.set_title("Matriz Operacional de Janela", fontsize=7.5, fontweight='bold', color='#0A192F')
    for spine in ax_tl.spines.values():
        spine.set_visible(False)

    buf_timeline = io.BytesIO()
    plt.savefig(buf_timeline, format='png', bbox_inches='tight', dpi=200)
    plt.close(fig_tl)
    buf_timeline.seek(0)

    # Posicionamento Lado a Lado: Donut + Kanban
    t_row_graphics = Table([[RLImage(buf_donut, width=205, height=125), RLImage(buf_timeline, width=310, height=125)]], colWidths=[210, 313])
    t_row_graphics.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    story.append(t_row_graphics)

    # ---------------------------------------------------------
    # PÁGINA 2: Gráficos de Tendência Temporal dos Modelos
    # ---------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("<b>Análise Comparativa de Modelos Numéricos</b>", section_style))
    story.append(Spacer(1, 4))

    # Gráfico 1: Onda
    fig, ax = plt.subplots(figsize=(7.2, 2.1), dpi=200)
    ax.plot(dataframe['Data_Hora'], dataframe['Onda_ECMWF(m)'], label='ECMWF', color='#1f77b4', linewidth=1)
    ax.plot(dataframe['Data_Hora'], dataframe['Onda_WW3(m)'], label='WW3', color='#e377c2', linewidth=1)
    ax.plot(dataframe['Data_Hora'], dataframe['Onda_Consenso(m)'], label='Consenso', color='#F32735', linewidth=2.0)
    ax.axhline(y=limite_onda, color='#7F8C8D', linestyle='--', linewidth=0.8, label=f'Limite ({limite_onda}m)')
    ax.set_title('Altura Significativa de Onda (m)', fontsize=7.5, fontweight='bold', color='#0A192F')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %Hh'))
    plt.xticks(rotation=0, fontsize=5.5)
    ax.legend(loc='upper right', fontsize=5.5, frameon=True)
    ax.grid(True, linestyle=':', alpha=0.6)

    buf_onda = io.BytesIO()
    plt.savefig(buf_onda, format='png', bbox_inches='tight', dpi=200)
    plt.close(fig)
    buf_onda.seek(0)

    # Gráfico 2: Vento
    fig, ax = plt.subplots(figsize=(7.2, 2.1), dpi=200)
    ax.plot(dataframe['Data_Hora'], dataframe['Vento_ECMWF_Nos'], label='ECMWF', color='#1f77b4', linewidth=1)
    ax.plot(dataframe['Data_Hora'], dataframe['Vento_GFS_Nos'], label='GFS', color='#2ca02c', linewidth=1)
    ax.plot(dataframe['Data_Hora'], dataframe['Vento_ICON_Nos'], label='ICON', color='#FFD700', linewidth=1.1)
    ax.plot(dataframe['Data_Hora'], dataframe['Vento_Consenso_Nos'], label='Consenso', color='#F32735', linewidth=2.0)
    ax.axhline(y=limite_vento, color='#7F8C8D', linestyle='--', linewidth=0.8, label=f'Limite ({limite_vento}kn)')
    ax.set_title('Velocidade de Vento (kn)', fontsize=7.5, fontweight='bold', color='#0A192F')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %Hh'))
    plt.xticks(rotation=0, fontsize=5.5)
    ax.legend(loc='upper right', fontsize=5.5, frameon=True)
    ax.grid(True, linestyle=':', alpha=0.6)

    buf_vento = io.BytesIO()
    plt.savefig(buf_vento, format='png', bbox_inches='tight', dpi=200)
    plt.close(fig)
    buf_vento.seek(0)

    # Gráfico 3: Maré e Correntes
    fig, ax = plt.subplots(figsize=(7.2, 1.9), dpi=200)
    ax.plot(dataframe['Data_Hora'], dataframe['Mare_Altura(m)'], label='Nível Maré (m)', color='#00838F', linewidth=1.8)
    ax.plot(dataframe['Data_Hora'], dataframe['Corrente_Vel_Nos'], label='Corrente (kn)', color='#2C3E50', linewidth=1.5, linestyle='-.')
    ax.set_title('Comportamento de Correntes Estuarinas e Maré', fontsize=7.5, fontweight='bold', color='#0A192F')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %Hh'))
    plt.xticks(rotation=0, fontsize=5.5)
    ax.legend(loc='upper right', fontsize=5.5, frameon=True)
    ax.grid(True, linestyle=':', alpha=0.6)

    buf_corr = io.BytesIO()
    plt.savefig(buf_corr, format='png', bbox_inches='tight', dpi=200)
    plt.close(fig)
    buf_corr.seek(0)

    story.append(RLImage(buf_onda, width=523, height=135))
    story.append(Spacer(1, 4))
    story.append(RLImage(buf_vento, width=523, height=135))
    story.append(Spacer(1, 4))
    story.append(RLImage(buf_corr, width=523, height=125))

    # ---------------------------------------------------------
    # PÁGINA 3: Tabela de Dados Tabulares Operacionais
    # ---------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("<b>Tabela Detalhada de Dados Operacionais</b>", section_style))
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

    t_data = Table(table_data, colWidths=[85, 45, 60, 85, 85, 83, 80], repeatRows=1)
    t_data.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7.5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
        ('FONTSIZE', (0, 1), (-1, -1), 6.5),
        ('PADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t_data)

    doc.build(story, canvasmaker=NumberedCanvas4SAS)
    buffer.seek(0)
    return buffer.getvalue()