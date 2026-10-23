import io
import os
from html import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Image, LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


NAVY = colors.HexColor("#000080")
GRID = colors.HexColor("#A6A6A6")
GREEN = colors.HexColor("#92D050")
YELLOW = colors.HexColor("#FFD966")
ORANGE = colors.HexColor("#F4B183")
RED = colors.HexColor("#FF0000")
MATRIX_COLORS = (
    (YELLOW, ORANGE, ORANGE, RED, RED),
    (GREEN, YELLOW, YELLOW, RED, RED),
    (GREEN, YELLOW, YELLOW, YELLOW, RED),
    (GREEN, GREEN, YELLOW, YELLOW, YELLOW),
    (GREEN, GREEN, GREEN, GREEN, YELLOW),
)


def _text(value, fallback="-"):
    if value is None or not str(value).strip():
        return fallback
    return escape(str(value).strip()).replace("\n", "<br/>")


def _p(value, style, fallback="-"):
    return Paragraph(_text(value, fallback), style)


def _labelled(label, value, style):
    return Paragraph(f"<b>{escape(label)}:</b> {_text(value)}", style)


def _records(value):
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, dict)]
    return []


def _number(value):
    if value is None or value == "":
        return "-"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _matrix_color(severity, probability):
    try:
        return MATRIX_COLORS[5 - int(severity)][int(probability) - 1]
    except (TypeError, ValueError, IndexError):
        return colors.white


def _history_value(row, *keys, default="-"):
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.casefold() not in {"nan", "<na>"}:
            return value
    return default


def criar_pdf_apr(*args, **kwargs):
    """Gera a APR no modelo OS-193 e retorna os bytes do PDF."""
    names = ("os_num", "local", "selecao_sensores", "riscos_filtrados", "colaborador", "data_str", "historico_rev")
    values = {
        "os_num": "OS-000", "local": "Campo / Embarcação", "selecao_sensores": None,
        "riscos_filtrados": None, "colaborador": "Equipe Operacional", "data_str": "N/A",
        "historico_rev": None,
    }
    values.update(zip(names, args))
    values.update({name: kwargs[name] for name in names if name in kwargs})

    os_number = str(values["os_num"] or "OS-000")
    local = str(values["local"] or "Embarcação / Campo")
    author = str(values["colaborador"] or "Equipe 4SAS")
    report_date = str(values["data_str"] or "N/A")
    sensors = values["selecao_sensores"]
    sensors_text = ", ".join(map(str, sensors)) if isinstance(sensors, (list, tuple)) and sensors else str(sensors or "-")
    risks = _records(values["riscos_filtrados"])
    if not risks:
        risks = [{"id": "-", "categoria_fase": "Operação Geral", "tarefa": "Operação Geral"}]
    history = _records(values["historico_rev"])
    if not history and isinstance(values["historico_rev"], str):
        history = [{"rev": 0, "data": report_date, "autor": author, "descricao": values["historico_rev"]}]
    if not history:
        history = [{"rev": 0, "data": report_date, "autor": author, "descricao": "Emissão Inicial"}]
    revision = _history_value(history[-1], "Rev", "rev", default=0)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), leftMargin=0.7 * cm, rightMargin=0.7 * cm,
        topMargin=0.8 * cm, bottomMargin=0.9 * cm,
        title="Análise Preliminar de Risco (APR)", author=author,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("OS193Title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=NAVY, alignment=1)
    subtitle = ParagraphStyle("OS193Subtitle", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#626262"), alignment=1)
    body = ParagraphStyle("OS193Body", parent=styles["Normal"], fontName="Helvetica", fontSize=6.5, leading=7.8, wordWrap="CJK")
    center = ParagraphStyle("OS193Center", parent=body, alignment=1)
    header = ParagraphStyle("OS193Header", parent=body, fontName="Helvetica-Bold", fontSize=6.5, leading=7.4, textColor=colors.white, alignment=1)
    group_header = ParagraphStyle("OS193GroupHeader", parent=header, fontSize=7.2, leading=8.2)
    score = ParagraphStyle("OS193Score", parent=center, fontName="Helvetica-Bold", fontSize=7)
    story = []

    logo_path = "assets/logo_4sas_wordmark.png"
    logo = Image(logo_path, width=4.3 * cm, height=0.9 * cm, kind="proportional") if os.path.exists(logo_path) else _p("4SAS", title)
    header_table = Table(
        [[
            logo,
            [
                _p("ANÁLISE PRELIMINAR DE RISCO (APR)", title),
                Spacer(1, 2),
                _p("Sistema de Gestão de SMS", subtitle),
            ],
        ]],
        colWidths=[4.5 * cm, 23.5 * cm],
    )
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (1, 0), "CENTER"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    story.extend([header_table, Spacer(1, 8)])

    metadata = Table([
        [_labelled("Data", report_date, body), _labelled("OS", os_number, body), _labelled("Local", local, body)],
        [_labelled("Sensores/Operações", sensors_text, body)],
    ], colWidths=[9.33 * cm, 9.33 * cm, 9.34 * cm])
    metadata.setStyle(TableStyle([("SPAN", (0, 1), (2, 1)), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F2F2")), ("BOX", (0, 0), (-1, -1), 0.7, GRID), ("INNERGRID", (0, 0), (-1, -1), 0.4, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story.extend([metadata, Spacer(1, 10)])

    probability_labels = ("1. Rara", "2. Baixa", "3. Possível", "4. Alta", "5. Frequente")
    severity_labels = {5: "5. Crítica", 4: "4. Severa", 3: "3. Moderada", 2: "2. Leve", 1: "1. Insignif."}
    matrix_rows = [[_p("Sev \\ Prob", header)] + [_p(label, header) for label in probability_labels]]
    for severity in range(5, 0, -1):
        matrix_rows.append([_p(severity_labels[severity], header)] + [_p(severity * prob, center) for prob in range(1, 6)])
    matrix = Table(matrix_rows, colWidths=[2.6 * cm] + [2 * cm] * 5, rowHeights=[0.58 * cm] * 6, hAlign="CENTER")
    matrix_style = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("BACKGROUND", (0, 1), (0, -1), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("TEXTCOLOR", (0, 1), (0, -1), colors.white), ("GRID", (0, 0), (-1, -1), 0.5, colors.white), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    for row, severity in enumerate(range(5, 0, -1), start=1):
        for probability in range(1, 6):
            matrix_style.append(("BACKGROUND", (probability, row), (probability, row), _matrix_color(severity, probability)))
    matrix.setStyle(TableStyle(matrix_style))
    story.extend([matrix, Spacer(1, 10)])

    revisions = [[_p("Rev.", header), _p("Data", header), _p("Autor", header), _p("Descrição da Alteração", header)]]
    for row in history:
        revisions.append([
            _p(_history_value(row, "Rev", "rev", default=0), center),
            _p(_history_value(row, "Data", "data", default=report_date), center),
            _p(_history_value(row, "Autor", "autor", "Aprovado Por", "aprovador", default=author), center),
            _p(_history_value(row, "Descrição", "descricao", "Descrição da Alteração"), body),
        ])
    revision_table = Table(revisions, colWidths=[1.4 * cm, 2.5 * cm, 6 * cm, 18.1 * cm], repeatRows=1)
    revision_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#595959")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.5, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story.extend([revision_table, PageBreak()])

    groups = ["Nº", "Disciplina", "Identificação dos Riscos", "", "", "Nível Inicial", "", "", "Mitigação dos Riscos", "", "", "Nível Residual", "", ""]
    columns = ["", "", "Processo / Tarefa", "Perigo / Situações", "Consequências", "Sev", "Prob", "Nív", "Medidas de Controle", "Controle Adicional", "Responsável", "Sev", "Prob", "Nív"]
    risk_rows = [[_p(cell, group_header) for cell in groups], [_p(cell, header) for cell in columns]]
    risk_score_colors = []
    for row_index, risk in enumerate(risks, start=2):
        mitigation = risk.get("mitigacao") if isinstance(risk.get("mitigacao"), dict) else {}
        initial = risk.get("risco_inicial") if isinstance(risk.get("risco_inicial"), dict) else {}
        residual = risk.get("risco_residual") if isinstance(risk.get("risco_residual"), dict) else {}
        initial_severity, initial_probability = initial.get("severidade"), initial.get("probabilidade")
        residual_severity, residual_probability = residual.get("severidade"), residual.get("probabilidade")
        phase = str(risk.get("categoria_fase", "")).split(" - ", 1)[-1]
        risk_rows.append([
            _p(risk.get("id"), center), _p(phase, body), _p(risk.get("tarefa"), body),
            _p(risk.get("perigo"), body), _p(risk.get("consequencias"), body),
            _p(_number(initial_severity), center), _p(_number(initial_probability), center),
            _p(_number(initial.get("nivel")), score), _p(mitigation.get("medidas_padrao"), body),
            _p(mitigation.get("controle_adicional", "N/A"), body), _p(mitigation.get("responsavel", author), body),
            _p(_number(residual_severity), center), _p(_number(residual_probability), center),
            _p(_number(residual.get("nivel")), score),
        ])
        risk_score_colors.append((
            _matrix_color(initial_severity, initial_probability),
            _matrix_color(residual_severity, residual_probability),
        ))

    widths_cm = [0.8, 1.6, 3.0, 3.4, 3.0, 0.7, 0.7, 0.8, 5.0, 2.3, 2.5, 0.7, 0.7, 0.8]
    table_style = [
        ("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (1, 1)),
        ("SPAN", (2, 0), (4, 0)), ("SPAN", (5, 0), (7, 0)),
        ("SPAN", (8, 0), (10, 0)), ("SPAN", (11, 0), (13, 0)),
        ("BACKGROUND", (0, 0), (-1, 1), NAVY), ("TEXTCOLOR", (0, 0), (-1, 1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.45, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, 1), "CENTER"), ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.5), ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    rows_per_page = 9
    for start in range(0, len(risk_score_colors), rows_per_page):
        if start:
            story.append(PageBreak())
        chunk = risk_rows[2 + start:2 + start + rows_per_page]
        chunk_data = risk_rows[:2] + chunk
        chunk_style = list(table_style)
        for local_row, (initial_color, residual_color) in enumerate(
            risk_score_colors[start:start + rows_per_page], start=2
        ):
            chunk_style.extend([
                ("BACKGROUND", (7, local_row), (7, local_row), initial_color),
                ("BACKGROUND", (13, local_row), (13, local_row), residual_color),
            ])
        risk_table = LongTable(
            chunk_data,
            colWidths=[width * cm for width in widths_cm],
            repeatRows=2,
            splitByRow=1,
            hAlign="CENTER",
        )
        risk_table.setStyle(TableStyle(chunk_style))
        story.append(risk_table)

    def footer(canvas, current_doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.setFont("Helvetica", 7)
        y = 0.35 * cm
        canvas.drawString(current_doc.leftMargin, y, f"OS-{os_number}-APR-Rev{revision}")
        canvas.drawCentredString(landscape(A4)[0] / 2, y, f"Página {current_doc.page}")
        canvas.drawRightString(landscape(A4)[0] - current_doc.rightMargin, y, f"Autor: {author}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer.getvalue()