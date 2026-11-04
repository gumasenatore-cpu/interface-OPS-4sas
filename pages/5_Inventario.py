import io
import os
import re
import qrcode
import pandas as pd
import streamlit as st
from datetime import datetime, date
from supabase import create_client, Client
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==============================================================================
# CONFIGURAÇÃO DE CONEXÃO SUPABASE
# ==============================================================================
@st.cache_resource
def init_supabase() -> Client:
    try:
        url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
        if not url or not key:
            st.error("🔒 Credenciais do Supabase não configuradas em st.secrets ou variáveis de ambiente.")
            st.stop()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Erro ao inicializar cliente Supabase: {str(e)}")
        st.stop()

supabase = init_supabase()

# ==============================================================================
# FUNÇÕES DE BANCO DE DADOS & UTILS (COM TRATAMENTO DE ERROS)
# ==============================================================================
def load_assets() -> pd.DataFrame:
    try:
        res = supabase.table("assets").select("*").order("asset_tag").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar ativos: {e}")
        return pd.DataFrame()

def load_maintenances(asset_id: str = None) -> pd.DataFrame:
    try:
        query = supabase.table("asset_maintenances").select("*, assets(name, asset_tag)")
        if asset_id:
            query = query.eq("asset_id", asset_id)
        res = query.order("created_at", desc=True).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar histórico de manutenções: {e}")
        return pd.DataFrame()

def generate_qr_code(data_str: str) -> bytes:
    # Sanitiza o texto de entrada do QR Code
    safe_data = re.sub(r'[^\w\-\:]', '', data_str)
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(safe_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f2b48", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def sanitize_filename(filename: str) -> str:
    # Remove caracteres não alfanuméricos para evitar acidentes e falhas de URL
    clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
    return clean_name

def generate_pdf_report(asset_row: pd.Series, maint_df: pd.DataFrame) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor("#0f2b48"),
        spaceAfter=12
    )
    
    elements = []
    elements.append(Paragraph("4SAS Offshore - Relatório de Intervenções & Calibração", title_style))
    elements.append(Spacer(1, 10))
    
    info_data = [
        ["Patrimônio / Tag:", str(asset_row.get("asset_tag", "-")), "Equipamento:", str(asset_row.get("name", "-"))],
        ["Categoria:", str(asset_row.get("category", "-")), "Nº de Série:", str(asset_row.get("serial_number", "-"))],
        ["Marca/Modelo:", str(asset_row.get("model_brand", "-")), "Status Atual:", str(asset_row.get("status", "-"))],
        ["Localização:", str(asset_row.get("location", "-")), "Responsável:", str(asset_row.get("responsible_email", "-"))]
    ]
    
    t_info = Table(info_data, colWidths=[110, 150, 100, 180])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f4f6f8")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#d0d7de")),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 15))
    
    elements.append(Paragraph("Histórico de Manutenções e Calibrações", styles['Heading2']))
    elements.append(Spacer(1, 8))
    
    if not maint_df.empty:
        m_table_data = [["Tipo", "Descrição", "Data Conclusão", "Próxima Calibração/Manut.", "Fornecedor"]]
        for _, m in maint_df.iterrows():
            m_table_data.append([
                str(m.get("type", "")).upper(),
                Paragraph(str(m.get("description", "")), styles['Normal']),
                str(m.get("completion_date", "-")),
                str(m.get("next_due_date", "-")),
                str(m.get("provider_name", "-"))
            ])
        
        t_maint = Table(m_table_data, colWidths=[80, 180, 90, 100, 90])
        t_maint.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f2b48")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#d0d7de")),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        elements.append(t_maint)
    else:
        elements.append(Paragraph("Nenhuma intervenção registrada até o momento.", styles['Italic']))
        
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==============================================================================
# INTERFACE PRINCIPAL STREAMLIT
# ==============================================================================
st.set_page_config(page_title="4SAS - Gestão de Ativos", page_icon="📦", layout="wide")

st.title("📦 Gestão de Ativos & Calibração 4SAS")
st.caption("Controle patrimonial, histórico de manutenção periódica e alertas de calibração")

df_assets = load_assets()

# --- CARDS DE RESUMO & ALERTAS ---
col_m1, col_m2, col_m3, col_m4 = st.columns(4)

total_ativos = len(df_assets) if not df_assets.empty else 0
df_maint_all = load_maintenances()

vencidos_count = 0
proximos_count = 0

if not df_maint_all.empty and 'next_due_date' in df_maint_all.columns:
    today = date.today()
    df_maint_valid = df_maint_all.dropna(subset=['next_due_date']).copy()
    df_maint_valid['next_due_date'] = pd.to_datetime(df_maint_valid['next_due_date']).dt.date
    
    vencidos_count = len(df_maint_valid[df_maint_valid['next_due_date'] < today])
    proximos_count = len(df_maint_valid[
        (df_maint_valid['next_due_date'] >= today) & 
        (df_maint_valid['next_due_date'] <= today + pd.Timedelta(days=30))
    ])

col_m1.metric("Total de Ativos", total_ativos)
col_m2.metric("Calibrações Vencidas", vencidos_count, delta_color="inverse")
col_m3.metric("A Vencer (30 dias)", proximos_count)
col_m4.metric("Status do Sistema", "Operacional", delta="Supabase OK")

st.divider()

tabs = st.tabs(["🔎 Painel & Buscador QR", "➕ Novo Cadastro", "🛠️ Registrar Intervenção", "📜 Histórico & PDF"])

# ------------------------------------------------------------------------------
# ABA 1: PAINEL & BUSCADOR
# ------------------------------------------------------------------------------
with tabs[0]:
    st.subheader("Consulta Rápida por Placa Patrimonial (001 a 200)")
    
    col_search1, col_search2 = st.columns([1, 2])
    with col_search1:
        raw_input = st.text_input("Digite o Número da Placa Patrimonial (ex: 001):", placeholder="001").strip()
        tag_search = re.sub(r'[^a-zA-Z0-9]', '', raw_input)
    
    if tag_search and not df_assets.empty:
        filtered = df_assets[df_assets['asset_tag'].astype(str) == tag_search]
        if not filtered.empty:
            asset = filtered.iloc[0]
            st.success(f"Ativo Encontrado: **{asset['name']}** (Tag: {asset['asset_tag']})")
            
            c_info1, c_info2, c_qr = st.columns([2, 2, 1])
            with c_info1:
                st.write(f"**Categoria:** {asset.get('category', '-')}")
                st.write(f"**Marca/Modelo:** {asset.get('model_brand', '-')}")
                st.write(f"**Nº de Série:** {asset.get('serial_number', '-')}")
            with c_info2:
                st.write(f"**Status:** {asset.get('status', '-')}")
                st.write(f"**Localização:** {asset.get('location', '-')}")
                st.write(f"**Responsável:** {asset.get('responsible_email', '-')}")
            with c_qr:
                qr_bytes = generate_qr_code(f"4SAS-TAG:{asset['asset_tag']}")
                st.image(qr_bytes, caption=f"QR Code Tag {asset['asset_tag']}", width=120)
        else:
            st.warning(f"Nenhum ativo localizado com a placa '{tag_search}'.")
            
    st.markdown("### Todos os Ativos Cadastrados")
    if not df_assets.empty:
        st.dataframe(
            df_assets[['asset_tag', 'name', 'category', 'model_brand', 'serial_number', 'status', 'location', 'responsible_email']],
            use_container_width=True
        )
    else:
        st.info("Nenhum ativo cadastrado até o momento.")

# ------------------------------------------------------------------------------
# ABA 2: NOVO CADASTRO
# ------------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Cadastrar Novo Ativo na 4SAS")
    
    with st.form("form_novo_ativo"):
        c1, c2 = st.columns(2)
        with c1:
            asset_tag = st.text_input("Placa Patrimonial (Tag ID)*", placeholder="ex: 001, 042").strip()
            name = st.text_input("Nome / Descrição do Equipamento*", placeholder="ex: Ecosonda Multifeixe").strip()
            category = st.selectbox("Categoria*", ["Multibeam", "Singlebeam", "GNSS / DGPS", "INS / Applanix", "Side Scan Sonar", "Sub-bottom Profiler", "Gerador / Energia", "Outros"])
            serial_number = st.text_input("Número de Série")
        with c2:
            model_brand = st.text_input("Marca / Modelo", placeholder="ex: Applanix WaveMaster")
            status = st.selectbox("Status Inicial", ["disponivel", "em_uso", "em_manutencao", "descomissionado"])
            location = st.text_input("Localização Inicial", placeholder="ex: Base Macaé, Embarcação X")
            responsible_email = st.text_input("E-mail do Responsável", placeholder="operacoes@4sas.com.br")
            
        submitted = st.form_submit_button("Salvar Ativo")
        if submitted:
            clean_tag = re.sub(r'[^a-zA-Z0-9]', '', asset_tag)
            if not clean_tag or not name:
                st.error("Por favor, preencha a Placa Patrimonial e o Nome do Equipamento.")
            else:
                try:
                    payload = {
                        "asset_tag": clean_tag,
                        "name": name,
                        "category": category,
                        "serial_number": serial_number,
                        "model_brand": model_brand,
                        "status": status,
                        "location": location,
                        "responsible_email": responsible_email
                    }
                    supabase.table("assets").insert(payload).execute()
                    st.success(f"Ativo Tag {clean_tag} cadastrado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar ativo no banco: {e}")

# ------------------------------------------------------------------------------
# ABA 3: REGISTRAR INTERVENÇÃO / CALIBRAÇÃO
# ------------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Registro de Manutenção, Calibração ou Inspeção")
    
    if df_assets.empty:
        st.warning("Cadastre um ativo primeiro para registrar intervenções.")
    else:
        asset_options = {f"{row['asset_tag']} - {row['name']}": row['id'] for _, row in df_assets.iterrows()}
        selected_asset_label = st.selectbox("Selecione o Ativo*", list(asset_options.keys()))
        selected_asset_id = asset_options[selected_asset_label]
        
        with st.form("form_intervencao"):
            col_i1, col_i2 = st.columns(2)
            with col_i1:
                m_type = st.selectbox("Tipo de Intervenção*", ["calibracao", "preventiva", "corretiva", "inspecao"])
                provider_name = st.text_input("Fornecedor / Laboratório Executante", placeholder="ex: Kongsberg Brasil")
                description = st.text_area("Descrição dos Serviços Realizados*", placeholder="Detalhes dos ensaios, troca de peças ou aferição...")
            with col_i2:
                completion_date = st.date_input("Data da Conclusão", date.today())
                next_due_date = st.date_input("Data da Próxima Calibração/Manutenção", date.today() + pd.Timedelta(days=365))
                cost = st.number_input("Custo da Intervenção (R$)", min_value=0.0, step=50.0)
                cert_file = st.file_uploader("Upload do Certificado / Laudo (PDF)", type=["pdf", "png", "jpg"])
                
            btn_salvar_interv = st.form_submit_button("Registrar Intervenção")
            
            if btn_salvar_interv:
                if not description:
                    st.error("Preencha a descrição do serviço.")
                else:
                    cert_url = None
                    if cert_file:
                        try:
                            clean_fname = sanitize_filename(cert_file.name)
                            file_path = f"{selected_asset_id}/{int(datetime.now().timestamp())}_{clean_fname}"
                            supabase.storage.from_("asset-certificates").upload(file_path, cert_file.getvalue())
                            cert_url = supabase.storage.from_("asset-certificates").get_public_url(file_path)
                        except Exception as st_err:
                            st.error(f"Erro ao realizar upload do arquivo: {st_err}")
                            
                    try:
                        m_payload = {
                            "asset_id": selected_asset_id,
                            "type": m_type,
                            "description": description,
                            "provider_name": provider_name,
                            "completion_date": str(completion_date),
                            "next_due_date": str(next_due_date),
                            "cost": cost,
                            "certificate_path": cert_url,
                            "status": "concluida"
                        }
                        supabase.table("asset_maintenances").insert(m_payload).execute()
                        st.success("Intervenção registrada com sucesso!")
                        st.rerun()
                    except Exception as db_err:
                        st.error(f"Erro ao salvar intervenção no banco: {db_err}")

# ------------------------------------------------------------------------------
# ABA 4: HISTÓRICO & EMISSÃO DE PDF
# ------------------------------------------------------------------------------
with tabs[3]:
    st.subheader("Histórico do Equipamento & Exportação de Comprovantes")
    
    if not df_assets.empty:
        asset_options_hist = {f"{row['asset_tag']} - {row['name']}": row for _, row in df_assets.iterrows()}
        sel_label_hist = st.selectbox("Selecione o Equipamento para Relatório:", list(asset_options_hist.keys()))
        selected_asset_row = asset_options_hist[sel_label_hist]
        
        df_history = load_maintenances(asset_id=selected_asset_row['id'])
        
        if not df_history.empty:
            st.markdown("### Intervenções Registradas")
            st.dataframe(
                df_history[['type', 'description', 'provider_name', 'completion_date', 'next_due_date', 'cost', 'certificate_path']],
                use_container_width=True
            )
        else:
            st.info("Sem histórico de manutenção para este equipamento.")
            
        st.divider()
        try:
            pdf_buf = generate_pdf_report(selected_asset_row, df_history)
            st.download_button(
                label="📄 Baixar Comprovante de Intervenção em PDF",
                data=pdf_buf,
                file_name=f"Relatorio_Ativo_{selected_asset_row['asset_tag']}.pdf",
                mime="application/pdf"
            )
        except Exception as pdf_err:
            st.error(f"Erro ao gerar relatório em PDF: {pdf_err}")