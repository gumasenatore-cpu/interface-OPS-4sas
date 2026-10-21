import io
import os
import pandas as pd
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def criar_pdf_apr(*args, **kwargs):
    """
    Gera o PDF da Análise Preliminar de Risco (APR) para a 4SAS.
    Aceita quantidade variável de argumentos; os sete primeiros preenchem os campos conhecidos.
    """
    nomes_parametros = (
        "os_num", "local", "selecao_sensores", "riscos_filtrados",
        "colaborador", "data_str", "historico_rev"
    )
    valores = {
        "os_num": "OS-000",
        "local": "Campo / Embarcação",
        "selecao_sensores": None,
        "riscos_filtrados": None,
        "colaborador": "Equipe Operacional",
        "data_str": "N/A",
        "historico_rev": None,
    }
    valores.update(zip(nomes_parametros, args))
    valores.update({nome: kwargs[nome] for nome in nomes_parametros if nome in kwargs})
    os_num = valores["os_num"]
    local = valores["local"]
    selecao_sensores = valores["selecao_sensores"]
    riscos_filtrados = valores["riscos_filtrados"]
    colaborador = valores["colaborador"]
    data_str = valores["data_str"]
    historico_rev = valores["historico_rev"]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm
    )

    styles = getSampleStyleSheet()

    # Estilos de texto
    title_style = ParagraphStyle(
        'APR_Title',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=16,
        textColor=colors.HexColor('#0A2540')
    )

    subtitle_style = ParagraphStyle(
        'APR_Subtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#636E72')
    )

    style_normal = ParagraphStyle(
        'APR_Normal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#1E293B')
    )

    style_header_cell = ParagraphStyle(
        'APR_HeaderCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1
    )

    story = []

    # Cabeçalho com Logotipo (se existir logo.png na raiz)
    logo_path = "logo.png"
    if os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=3.5*cm, height=1.2*cm)
            header_table = Table([[
                img,
                [
                    Paragraph("<b>4SAS SUBSEA & HYDROGRAPHIC OPERATIONS</b>", title_style),
                    Paragraph("Análise Preliminar de Risco (APR) — Sistema de Gestão de SMS", subtitle_style)
                ]
            ]], colWidths=[4*cm, 23.3*cm])
        except Exception:
            header_table = Table([[
                Paragraph("<b>4SAS SUBSEA & HYDROGRAPHIC OPERATIONS</b>", title_style),
                Paragraph("Análise Preliminar de Risco (APR) — Sistema de Gestão de SMS", subtitle_style)
            ]], colWidths=[27.3*cm])
    else:
        header_table = Table([[
            Paragraph("<b>4SAS SUBSEA & HYDROGRAPHIC OPERATIONS</b>", title_style),
            Paragraph("Análise Preliminar de Risco (APR) — Sistema de Gestão de SMS", subtitle_style)
        ]], colWidths=[27.3*cm])

    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    # Tratamento dos dados de entrada
    os_str = str(os_num) if os_num else "OS-000"
    local_str = str(local) if local else "Embarcação / Campo"
    colaborador_str = str(colaborador) if colaborador else "Equipe 4SAS"
    data_texto = str(data_str) if data_str else "N/A"

    if isinstance(selecao_sensores, (list, tuple)):
        sensores_texto = ", ".join([str(s) for s in selecao_sensores])
    else:
        sensores_texto = str(selecao_sensores) if selecao_sensores else "Multifeixe / Sonar / Magnetômetro"

    # Tabela de Metadados
    meta_data = [
        [
            Paragraph(f"<b>Ordem de Serviço (OS):</b> {os_str}", style_normal),
            Paragraph(f"<b>Local / Embarcação:</b> {local_str}", style_normal),
            Paragraph(f"<b>Data da APR:</b> {data_texto}", style_normal)
        ],
        [
            Paragraph(f"<b>Responsável / Elaborador:</b> {colaborador_str}", style_normal),
            Paragraph(f"<b>Sensores / Equipamentos:</b> {sensores_texto}", style_normal),
            Paragraph("<b>Status:</b> Aprovado para Operação", style_normal)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[9.1*cm, 9.1*cm, 9.1*cm])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # Tabela Principal de Riscos
    headers = ["Subtarefa / Etapa", "Perigos / Ameaças", "Riscos & Danos", "Controles & Defesas", "Risco Residual", "Ações Complementares", "Responsável"]
    data_rows = [[Paragraph(h, style_header_cell) for h in headers]]

    itens = []
    if isinstance(riscos_filtrados, pd.DataFrame):
        itens = riscos_filtrados.to_dict(orient='records')
    elif isinstance(riscos_filtrados, (list, tuple)):
        itens = list(riscos_filtrados)

    if not itens:
        itens = [{
            "subtarefa": "Operação Geral",
            "perigo": "Prensamento / Queda de carga / Intempéries",
            "risco": "Lesão corporal / Danos aos equipamentos",
            "controles": "EPI completo, isolamento de área e monitoramento meteoceanográfico",
            "risco_residual": "Baixo",
            "complementares": "DDS diário e checklist pré-operação",
            "responsavel": colaborador_str
        }]

    for item in itens:
        if isinstance(item, dict):
            sub = item.get('subtarefa') or item.get('etapa') or item.get('tarefa') or '-'
            per = item.get('perigo') or item.get('perigos') or '-'
            ris = item.get('risco') or item.get('riscos') or item.get('dano') or '-'
            con = item.get('controles') or item.get('defesas') or item.get('medidas') or '-'
            res = item.get('risco_residual') or item.get('nivel') or item.get('gravidade') or 'Baixo'
            com = item.get('complementares') or item.get('controles_complementares') or '-'
            resp = item.get('responsavel') or item.get('resp') or colaborador_str

            cor = colors.HexColor('#10B981') if 'Baixo' in str(res) else (
                colors.HexColor('#EF4444') if 'Alto' in str(res) or 'Crítico' in str(res) else colors.HexColor('#F59E0B')
            )
            style_res = ParagraphStyle('ResStyle', parent=style_normal, fontName='Helvetica-Bold', textColor=cor, alignment=1)

            data_rows.append([
                Paragraph(str(sub), style_normal),
                Paragraph(str(per), style_normal),
                Paragraph(str(ris), style_normal),
                Paragraph(str(con), style_normal),
                Paragraph(str(res), style_res),
                Paragraph(str(com), style_normal),
                Paragraph(str(resp), style_normal)
            ])
        elif isinstance(item, (list, tuple)):
            data_rows.append([Paragraph(str(cell), style_normal) for cell in item])

    col_widths = [4.2*cm, 4.2*cm, 4.2*cm, 5.5*cm, 2.2*cm, 4.2*cm, 2.8*cm]
    tabela_riscos = Table(data_rows, colWidths=col_widths)
    tabela_riscos.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0A2540')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(tabela_riscos)

    # Tabela de Histórico de Revisões (opcional)
    if historico_rev:
        story.append(Spacer(1, 8))
        story.append(Paragraph("<b>Histórico de Revisões:</b>", style_normal))
        rev_rows = [[Paragraph("<b>Rev.</b>", style_normal), Paragraph("<b>Data</b>", style_normal), Paragraph("<b>Descrição / Alteração</b>", style_normal), Paragraph("<b>Aprovado Por</b>", style_normal)]]
        
        if isinstance(historico_rev, list):
            for r in historico_rev:
                if isinstance(r, dict):
                    rev_rows.append([
                        Paragraph(str(r.get('rev', '00')), style_normal),
                        Paragraph(str(r.get('data', '-')), style_normal),
                        Paragraph(str(r.get('descricao', '-')), style_normal),
                        Paragraph(str(r.get('aprovador', '-')), style_normal)
                    ])
                elif isinstance(r, (list, tuple)):
                    rev_rows.append([Paragraph(str(c), style_normal) for c in r])
        elif isinstance(historico_rev, str):
            rev_rows.append([Paragraph("Rev. 00", style_normal), Paragraph(data_texto, style_normal), Paragraph(historico_rev, style_normal), Paragraph(colaborador_str, style_normal)])

        rev_table = Table(rev_rows, colWidths=[2*cm, 3*cm, 16.3*cm, 6*cm])
        rev_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('PADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(rev_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()