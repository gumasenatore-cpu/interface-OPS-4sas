import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import requests
from supabase import create_client, Client

# ReportLab para geração de PDF executivo de alta resolução
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage

# ------------------------------------------------------------------------------
# CONFIGURAÇÃO DE PÁGINA E CSS MOBILE-FIRST
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Mob & Desmob | 4SAS",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            padding-top: 0.8rem !important;
        }
        .stButton button {
            width: 100% !important;
            min-height: 48px !important;
            font-size: 16px !important;
            border-radius: 8px !important;
        }
    }
    
    .status-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 12px;
    }
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# INICIALIZAÇÃO SEGURA DO SUPABASE
# ------------------------------------------------------------------------------
SUPABASE_URL = st.secrets.get("SUPABASE_URL") or st.secrets.get("MAP_SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or st.secrets.get("MAP_SUPABASE_KEY")

@st.cache_resource
def init_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("🔒 Credenciais do Supabase não configuradas no secrets.toml.")
        st.stop()
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"❌ Falha ao conectar ao Supabase: {e}")
        st.stop()

supabase: Client = init_supabase()

# ------------------------------------------------------------------------------
# HELPER DE UPLOAD DE FOTOS DIRETO NO STORAGE (PERSISTÊNCIA GARANTIDA)
# ------------------------------------------------------------------------------
def upload_photo_to_storage(uploaded_file, project_code, tag_serial, prefix="mob"):
    if uploaded_file is None:
        return None
    try:
        file_bytes = uploaded_file.getvalue()
        if not file_bytes or len(file_bytes) == 0:
            return None
        
        clean_tag = "".join([c for c in str(tag_serial) if c.isalnum() or c in ("-", "_")]).strip() or "item"
        file_ext = "jpg"
        mime_type = "image/jpeg"
        if uploaded_file.name and uploaded_file.name.lower().endswith(".png"):
            file_ext = "png"
            mime_type = "image/png"

        filename = f"{project_code}/{clean_tag}_{prefix}_{int(datetime.now().timestamp())}.{file_ext}"
        
        supabase.storage.from_("mob-evidences").upload(
            path=filename,
            file=file_bytes,
            file_options={"upsert": "true", "content-type": mime_type}
        )
        return supabase.storage.from_("mob-evidences").get_public_url(filename)
    except Exception as e:
        st.error(f"⚠️ Falha ao salvar foto no Storage: {e}")
        return None

# ------------------------------------------------------------------------------
# MODAL DE EDIÇÃO DE ITEM
# ------------------------------------------------------------------------------
@st.dialog("✏️ Editar Item do Packing List")
def edit_item_dialog(item, df_items, current_project):
    parents_dict = {}
    sub_boxes_dict = {}
    if not df_items.empty and "level_type" in df_items:
        parent_boxes = df_items[(df_items["level_type"] == "parent_box") & (df_items["id"] != item["id"])]
        for _, b in parent_boxes.iterrows():
            parents_dict[f"🧰 [CAIXA PAI] {b['tag_or_serial']} - {b['description']}"] = b["id"]
        
        sub_boxes = df_items[(df_items["level_type"] == "sub_box") & (df_items["id"] != item["id"])]
        for _, sb in sub_boxes.iterrows():
            sub_boxes_dict[f"📦 [SUB-CAIXA] {sb['tag_or_serial']} - {sb['description']}"] = sb["id"]

    st.write("📷 **Atualizar Foto de Mobilização**")
    new_img_mob = st.file_uploader("Carregar/Substituir foto MOB", type=["jpg", "png", "jpeg"], key=f"edit_img_mob_{item['id']}")

    with st.form(f"form_edit_dialog_{item['id']}"):
        new_tag = st.text_input("Tag / Identificador", value=item.get("tag_or_serial", ""))
        curr_level = item.get("level_type", "item")
        level_opts = ["parent_box", "sub_box", "item"]
        new_level = st.selectbox(
            "Nível Hierárquico",
            level_opts,
            index=level_opts.index(curr_level) if curr_level in level_opts else 2,
            format_func=lambda x: {"parent_box": "🧰 Caixa Pai", "sub_box": "📦 Sub-caixa", "item": "🏷️ Item Solto"}[x]
        )
        
        new_parent_id = item.get("parent_id")
        if new_level == "sub_box":
            if parents_dict:
                p_keys = list(parents_dict.keys())
                curr_idx = 0
                for i, k in enumerate(p_keys):
                    if parents_dict[k] == new_parent_id:
                        curr_idx = i
                        break
                sel_p = st.selectbox("Caixa Pai Vinculada", p_keys, index=curr_idx)
                new_parent_id = parents_dict[sel_p]
        elif new_level == "item":
            containers = {"-- Item Solto (Direto no Deck) --": None}
            containers.update(parents_dict)
            containers.update(sub_boxes_dict)
            c_keys = list(containers.keys())
            curr_idx = 0
            for i, k in enumerate(c_keys):
                if containers[k] == new_parent_id:
                    curr_idx = i
                    break
            sel_c = st.selectbox("Caixa ou Maleta Vinculada", c_keys, index=curr_idx)
            new_parent_id = containers[sel_c]
        else:
            new_parent_id = None

        new_desc = st.text_input("Descrição", value=item.get("description", ""))
        new_w = st.number_input("Peso (kg)", min_value=0.0, step=0.5, value=float(item.get("weight_kg", 0.0)))
        new_val = st.number_input("Valor (R$)", min_value=0.0, step=100.0, value=float(item.get("declared_value_brl", 0.0)))
        new_mob_notes = st.text_area("Obs. Saída Galpão", value=item.get("mob_notes") or "")

        btn_save = st.form_submit_button("💾 Salvar Alterações", type="primary")

        if btn_save:
            mob_url = item.get("mob_photo_url")
            if new_img_mob:
                up_url = upload_photo_to_storage(new_img_mob, current_project["project_code"], new_tag, prefix="mob")
                if up_url:
                    mob_url = up_url

            upd_payload = {
                "tag_or_serial": new_tag.strip(),
                "description": new_desc.strip(),
                "level_type": new_level,
                "parent_id": new_parent_id,
                "weight_kg": new_w,
                "declared_value_brl": new_val,
                "mob_notes": new_mob_notes,
                "mob_photo_url": mob_url
            }
            try:
                supabase.table("mob_packing_list_items").update(upd_payload).eq("id", item["id"]).execute()
                st.success("Item atualizado!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar alterações: {e}")

# ------------------------------------------------------------------------------
# GERADOR DE PDF EXECUTIVO (COPIA FÍSICA PARA CAIXA)
# ------------------------------------------------------------------------------
def generate_packing_list_pdf(project_info, df_items):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#0f2b48'), spaceAfter=4)
    subtitle_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontSize=9, leading=13, textColor=colors.HexColor('#4a5568'), spaceAfter=10)
    cell_style = ParagraphStyle('CellText', parent=styles['Normal'], fontSize=8, leading=10)
    cell_bold_white = ParagraphStyle('CellBoldWhite', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold', textColor=colors.white)
    cell_bold = ParagraphStyle('CellBold', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold')

    story = []

    story.append(Paragraph("4SAS — MANIFESTO DE CARGA / PACKING LIST", title_style))
    meta_text = (
        f"<b>Campanha / Projeto:</b> {project_info.get('project_code', 'N/A')}<br/>"
        f"<b>Cliente:</b> {project_info.get('client_name') or 'N/A'} | "
        f"<b>Embarcação/Local:</b> {project_info.get('vessel_name') or 'N/A'}<br/>"
        f"<b>Responsável Técnico:</b> {project_info.get('responsible_user', 'N/A')} | "
        f"<b>Data Emissão:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    story.append(Paragraph(meta_text, subtitle_style))
    story.append(Spacer(1, 6))

    total_w = df_items["weight_kg"].sum() if not df_items.empty and "weight_kg" in df_items else 0.0
    total_v = df_items["declared_value_brl"].sum() if not df_items.empty and "declared_value_brl" in df_items else 0.0
    total_i = len(df_items) if not df_items.empty else 0
    
    kpi_data = [
        [Paragraph("<b>Peso Total</b>", cell_bold), Paragraph("<b>Valor Declarado</b>", cell_bold), Paragraph("<b>Total de Itens</b>", cell_bold)],
        [Paragraph(f"{total_w:,.2f} kg", cell_style), Paragraph(f"R$ {total_v:,.2f}", cell_style), Paragraph(f"{total_i} itens", cell_style)]
    ]
    kpi_table = Table(kpi_data, colWidths=[180, 180, 180])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f1f5f9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>RELAÇÃO COMPLETA DE EQUIPAMENTOS E EVIDÊNCIAS</b>", styles['Heading3']))
    story.append(Spacer(1, 4))
    
    table_data = [[
        Paragraph("Tag / Identificador", cell_bold_white),
        Paragraph("Descrição / Conteúdo", cell_bold_white),
        Paragraph("Tipo Nível", cell_bold_white),
        Paragraph("Peso (kg)", cell_bold_white),
        Paragraph("Valor (R$)", cell_bold_white),
        Paragraph("Status", cell_bold_white)
    ]]

    for _, row in df_items.iterrows():
        level_prefix = ""
        l_type = row.get("level_type", "item")
        if l_type == "sub_box":
            level_prefix = "↳ 📦 "
        elif l_type == "item" and pd.notna(row.get("parent_id")):
            level_prefix = "   • 🏷️ "
        elif l_type == "parent_box":
            level_prefix = "🧰 "

        type_label = "Caixa Pai" if l_type == "parent_box" else ("Sub-caixa" if l_type == "sub_box" else "Item Solto")
        rec_status = "OK (Embarcado)" if row.get("mob_receipt_ok") else "Pendente Navio"

        table_data.append([
            Paragraph(str(row.get("tag_or_serial", "")), cell_style),
            Paragraph(f"{level_prefix}{row.get('description', '')}", cell_style),
            Paragraph(type_label, cell_style),
            Paragraph(f"{float(row.get('weight_kg', 0.0)):,.2f}", cell_style),
            Paragraph(f"R$ {float(row.get('declared_value_brl', 0.0)):,.2f}", cell_style),
            Paragraph(rec_status, cell_style)
        ])

        mob_img_obj = None
        desmob_img_obj = None

        if row.get("mob_photo_url"):
            try:
                r1 = requests.get(row["mob_photo_url"], timeout=4)
                if r1.status_code == 200:
                    mob_img_obj = RLImage(BytesIO(r1.content), width=90, height=65)
            except Exception:
                pass

        if row.get("desmob_photo_url"):
            try:
                r2 = requests.get(row["desmob_photo_url"], timeout=4)
                if r2.status_code == 200:
                    desmob_img_obj = RLImage(BytesIO(r2.content), width=90, height=65)
            except Exception:
                pass

        if mob_img_obj or desmob_img_obj:
            img_elements = []
            if mob_img_obj:
                img_elements.append(Paragraph("<b>Foto Saída (Galpão):</b>", cell_style))
                img_elements.append(mob_img_obj)
            if desmob_img_obj:
                img_elements.append(Paragraph("<b>Foto Retorno (Desmob):</b>", cell_style))
                img_elements.append(desmob_img_obj)

            sub_t = Table([[img_elements]], colWidths=[340])
            sub_t.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
            table_data.append([Paragraph("", cell_style), sub_t, Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style)])

    items_table = Table(table_data, colWidths=[90, 180, 70, 55, 75, 70])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f2b48')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(items_table)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ------------------------------------------------------------------------------
# INTERFACE PRINCIPAL
# ------------------------------------------------------------------------------
st.title("📋 Packing List & Gestão de Carga")

st.sidebar.header("📁 Operação / Campanha")

try:
    proj_res = supabase.table("mob_projects").select("*").order("created_at", desc=True).execute()
    projects = proj_res.data or []
except Exception as e:
    projects = []
    st.sidebar.error(f"Erro ao carregar projetos: {e}")

project_options = {f"[{p['project_code']}] {p.get('vessel_name') or 'Sem Embarcação'}": p for p in projects}

selected_proj_label = st.sidebar.selectbox(
    "Selecione a Campanha Ativa:", 
    options=["-- Criar Nova Campanha --"] + list(project_options.keys())
)

if selected_proj_label == "-- Criar Nova Campanha --":
    st.info("👈 Crie ou selecione uma campanha na barra lateral para iniciar o Packing List.")
    with st.sidebar.form("form_new_project"):
        st.subheader("➕ Nova Campanha")
        p_code = st.text_input("Código do Projeto (ex: MOB-2026-BF-01)")
        p_client = st.text_input("Cliente")
        p_vessel = st.text_input("Embarcação / Local")
        p_user = st.text_input("Responsável Técnico", value=st.session_state.get("user_email", "operacoes@4sas.com.br"))
        btn_proj = st.form_submit_button("Criar Campanha")
        
        if btn_proj and p_code:
            try:
                payload_p = {
                    "project_code": p_code.strip(),
                    "client_name": p_client.strip() if p_client else None,
                    "vessel_name": p_vessel.strip() if p_vessel else None,
                    "responsible_user": p_user.strip() if p_user else "operacoes@4sas.com.br",
                    "status": "in_mobilization"
                }
                supabase.table("mob_projects").insert(payload_p).execute()
                st.success(f"Campanha {p_code} criada!")
                st.rerun()
            except Exception as err:
                st.error(f"Erro ao criar campanha: {err}")
    st.stop()

current_project = project_options[selected_proj_label]
proj_id = current_project["id"]

# Gestão de Campanha na Sidebar
with st.sidebar.expander("⚙️ Gerenciar Campanha Selecionada"):
    st.warning(f"Excluir a campanha **{current_project['project_code']}** removerá todos os registros associados.")
    if st.button("🗑️ Excluir esta Campanha", type="primary"):
        try:
            supabase.table("mob_packing_list_items").delete().eq("project_id", proj_id).execute()
            supabase.table("mob_projects").delete().eq("id", proj_id).execute()
            st.success("Campanha excluída!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao excluir: {e}")

st.markdown(f"### 🚢 {current_project['project_code']} — {current_project.get('vessel_name', '')}")
st.caption(f"Cliente: **{current_project.get('client_name', 'N/A')}** | Responsável: **{current_project.get('responsible_user', 'N/A')}**")

# Carregamento Resiliente dos Itens
try:
    items_res = supabase.table("mob_packing_list_items").select("*").eq("project_id", proj_id).order("created_at", desc=False).execute()
    items = items_res.data or []
except Exception as e:
    items = []
    st.error(f"Erro ao carregar itens da campanha: {e}")

df_items = pd.DataFrame(items) if items else pd.DataFrame()

col_m1, col_m2, col_m3 = st.columns(3)
total_w = df_items["weight_kg"].sum() if not df_items.empty and "weight_kg" in df_items else 0.0
total_v = df_items["declared_value_brl"].sum() if not df_items.empty and "declared_value_brl" in df_items else 0.0
total_c = len(df_items) if not df_items.empty else 0

col_m1.metric("⚖️ Peso Total", f"{total_w:,.2f} kg")
col_m2.metric("💰 Valor Declarado", f"R$ {total_v:,.2f}")
col_m3.metric("📦 Total de Itens", f"{total_c}")

st.divider()

tab_mob, tab_desmob, tab_report = st.tabs([
    "🚀 1. Mobilização (Despacho & Recebimento)", 
    "🔄 2. Desmobilização (Retorno & Galpão)", 
    "📊 3. Resumo & PDF Executivo"
])

# ------------------------------------------------------------------------------
# TAB 1: MOBILIZAÇÃO DESCONTINUADA
# ------------------------------------------------------------------------------
with tab_mob:
    st.subheader("➕ 1.1 Cadastro Hierárquico de Carga (Galpão)")
    
    parents_dict = {}
    sub_boxes_dict = {}
    
    if not df_items.empty and "level_type" in df_items:
        parent_boxes = df_items[df_items["level_type"] == "parent_box"]
        for _, b in parent_boxes.iterrows():
            parents_dict[f"🧰 [CAIXA PAI] {b['tag_or_serial']} - {b['description']}"] = b["id"]
        
        sub_boxes = df_items[df_items["level_type"] == "sub_box"]
        for _, sb in sub_boxes.iterrows():
            sub_boxes_dict[f"📦 [SUB-CAIXA] {sb['tag_or_serial']} - {sb['description']}"] = sb["id"]

    level_choice = st.radio(
        "1. Nível do Equipamento / Recipiente:",
        options=["parent_box", "sub_box", "item"],
        format_func=lambda x: {"parent_box": "🧰 1. Caixa Pai / Contêiner Principal", "sub_box": "📦 2. Sub-caixa / Maleta", "item": "🏷️ 3. Item Solto / Equipamento"}[x],
        horizontal=True
    )

    parent_id = None
    if level_choice == "sub_box":
        if parents_dict:
            selected_p = st.selectbox("🔗 Pertence a qual Caixa Pai?", list(parents_dict.keys()))
            parent_id = parents_dict[selected_p]
        else:
            st.warning("⚠️ Cadastre uma Caixa Pai primeiro para vincular esta sub-caixa.")
    elif level_choice == "item":
        all_containers = {"-- Item Solto (Direto no Deck) --": None}
        all_containers.update(parents_dict)
        all_containers.update(sub_boxes_dict)
        selected_c = st.selectbox("🔗 Pertence a qual Caixa Pai ou Sub-caixa?", list(all_containers.keys()))
        parent_id = all_containers[selected_c]

    st.write("📷 **Evidência Fotográfica de Saída (Galpão)**")
    img_file = st.file_uploader("Toque para tirar foto ou pegar da galeria", type=["jpg", "png", "jpeg"], key="mob_img_uploader_direct")

    with st.form("form_mob_cad_item", clear_on_submit=True):
        c_t1, c_t2 = st.columns(2)
        with c_t1:
            tag_serial = st.text_input("Tag / Identificador", placeholder="ex: CX-PRINCIPAL-01, TRIMBLE-BX992")
            description = st.text_input("Descrição Completa", placeholder="ex: Mala Peli contendo receptor RTK")
        with c_t2:
            weight = st.number_input("Peso (kg)", min_value=0.0, step=0.5, value=0.0)
            value_brl = st.number_input("Valor Declarado (R$)", min_value=0.0, step=100.0, value=0.0)
            mob_notes = st.text_area("Obs. Despacho", placeholder="Estado físico na saída do galpão...")

        btn_save_item = st.form_submit_button("💾 Cadastrar Item no Packing List", type="primary")

        if btn_save_item:
            if tag_serial and description:
                photo_url = None
                if img_file is not None:
                    photo_url = upload_photo_to_storage(img_file, current_project['project_code'], tag_serial, prefix="mob")

                payload_item = {
                    "project_id": proj_id,
                    "parent_id": parent_id,
                    "level_type": level_choice,
                    "item_type": "box" if level_choice in ["parent_box", "sub_box"] else "loose_item",
                    "tag_or_serial": tag_serial.strip(),
                    "description": description.strip(),
                    "weight_kg": weight,
                    "declared_value_brl": value_brl,
                    "mob_notes": mob_notes,
                    "mob_photo_url": photo_url,
                    "mob_dispatch_ok": True,
                    "mob_by": st.session_state.get("user_email", "operacoes@4sas.com.br"),
                    "mob_timestamp": datetime.now().isoformat()
                }

                try:
                    supabase.table("mob_packing_list_items").insert(payload_item).execute()
                    st.success(f"✅ Item [{tag_serial}] salvo com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar item: {e}")
            else:
                st.warning("⚠️ Tag e Descrição são obrigatórias.")

    st.divider()
    st.subheader("🚢 1.2 Status de Conferência e Checklist de Recebimento")

    if df_items.empty:
        st.info("Nenhum item cadastrado até o momento.")
    else:
        for idx, item in df_items.iterrows():
            is_rec = item.get("mob_receipt_ok", False)
            status_txt = "✅ Confirmação OK no Navio" if is_rec else "⏳ Em Trânsito / Pendente Navio"
            
            with st.expander(f"[{item['tag_or_serial']}] {item['description']} — {status_txt}"):
                col_left, col_right = st.columns([3, 2])
                with col_left:
                    st.markdown(f"**Identificador:** `{item['tag_or_serial']}`")
                    st.markdown(f"**Nível:** `{item.get('level_type')}` | **Peso:** `{item.get('weight_kg')} kg`")
                    st.markdown(f"**Obs. Despacho Galpão:** {item.get('mob_notes') or 'Nenhuma'}")
                with col_right:
                    photo_url = item.get("mob_photo_url")
                    if photo_url and isinstance(photo_url, str) and photo_url.strip():
                        st.image(photo_url, caption="Evidência Fotográfica MOB", use_container_width=True)
                    else:
                        st.warning("Sem foto registrada na saída")

                st.divider()
                
                if not is_rec:
                    op_name = st.text_input("Nome do Operador Recebedor", value="Operador Navio", key=f"rec_op_{item['id']}")
                    if st.button("👍 Dar Baixa de Recebimento no Navio", key=f"btn_rec_{item['id']}", type="primary"):
                        try:
                            upd_rec = {
                                "mob_receipt_ok": True,
                                "mob_receipt_by": op_name,
                                "mob_receipt_timestamp": datetime.now().isoformat()
                            }
                            supabase.table("mob_packing_list_items").update(upd_rec).eq("id", item["id"]).execute()
                            st.success("Recebimento confirmado!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao confirmar recebimento: {e}")
                else:
                    st.success(f"Conferido por **{item.get('mob_receipt_by')}** em `{str(item.get('mob_receipt_timestamp'))[:16]}`")
                
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("✏️ Editar Registro", key=f"btn_ed_{item['id']}"):
                        edit_item_dialog(item, df_items, current_project)
                with col_b2:
                    if st.button("🗑️ Excluir Item", key=f"btn_del_{item['id']}", type="secondary"):
                        try:
                            supabase.table("mob_packing_list_items").delete().eq("parent_id", item["id"]).execute()
                            supabase.table("mob_packing_list_items").delete().eq("id", item["id"]).execute()
                            st.success("Item removido!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")

# ------------------------------------------------------------------------------
# TAB 2: DESMOBILIZAÇÃO
# ------------------------------------------------------------------------------
with tab_desmob:
    st.subheader("🔍 Check-out de Retorno no Galpão (Desmobilização)")
    if df_items.empty:
        st.info("Nenhum item cadastrado para desmobilização.")
    else:
        for idx, item in df_items.iterrows():
            with st.expander(f"[{item['tag_or_serial']}] {item['description']}", expanded=(item.get('desmob_status') == 'pending')):
                c_d1, c_d2 = st.columns([2, 3])
                with c_d1:
                    st.markdown(f"**Tag/Serial:** `{item['tag_or_serial']}`")
                    st.markdown(f"**Peso:** {item['weight_kg']} kg | **Valor:** R$ {item['declared_value_brl']:,.2f}")
                    
                    p_mob = item.get("mob_photo_url")
                    if p_mob:
                        st.image(p_mob, caption="Foto MOB (Galpão)", use_container_width=True)
                
                with c_d2:
                    st.caption("🔄 **Check-in de Retorno**")
                    desmob_cam = st.file_uploader("Foto de Retorno (Estado Físico)", type=["jpg", "png", "jpeg"], key=f"cam_desmob_{item['id']}")
                    
                    with st.form(f"form_desmob_check_{item['id']}"):
                        curr_st = item.get('desmob_status', 'pending')
                        st_opts = ["ok", "damaged", "lost", "left_on_site"]
                        st_idx = 0 if curr_st not in st_opts else st_opts.index(curr_st)
                        
                        status_ret = st.selectbox(
                            "Condição na Chegada",
                            st_opts,
                            index=st_idx,
                            format_func=lambda x: {"ok": "✅ Retornou OK", "damaged": "⚠️ Danificado", "lost": "❌ Perdido / Ausente", "left_on_site": "📍 Deixado no Cliente"}[x]
                        )
                        obs_ret = st.text_area("Observações de Retorno", value=item.get("desmob_notes") or "")
                        btn_ret = st.form_submit_button("Confirmar Chegada", type="primary")

                        if btn_ret:
                            desmob_url = item.get("desmob_photo_url")
                            if desmob_cam:
                                up_url = upload_photo_to_storage(desmob_cam, current_project['project_code'], item['tag_or_serial'], prefix="desmob")
                                if up_url:
                                    desmob_url = up_url

                            payload_desmob = {
                                "desmob_status": status_ret,
                                "desmob_notes": obs_ret,
                                "desmob_photo_url": desmob_url,
                                "desmob_dispatch_ok": True,
                                "desmob_receipt_ok": True,
                                "desmob_receipt_by": st.session_state.get("user_email", "operacoes@4sas.com.br"),
                                "desmob_receipt_timestamp": datetime.now().isoformat()
                            }
                            try:
                                supabase.table("mob_packing_list_items").update(payload_desmob).eq("id", item["id"]).execute()
                                st.success("Status de retorno salvo!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao atualizar: {e}")

# ------------------------------------------------------------------------------
# TAB 3: RELATÓRIOS & CSV/PDF EXECUTIVO
# ------------------------------------------------------------------------------
with tab_report:
    st.subheader("📊 Relatórios e Documentação Física da Caixa")
    if not df_items.empty:
        col_pdf, col_csv = st.columns(2)
        
        with col_pdf:
            st.markdown("##### 📄 PDF Executivo Emplastificável")
            st.caption("Documento oficial em PDF formatado com fotos e tabela para fixar na caixa.")
            try:
                pdf_bytes = generate_packing_list_pdf(current_project, df_items)
                st.download_button(
                    label="📄 Baixar Packing List Executivo (PDF)",
                    data=pdf_bytes,
                    file_name=f"packing_list_{current_project['project_code']}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
            except Exception as e_pdf:
                st.error(f"Erro ao gerar PDF: {e_pdf}")

        with col_csv:
            st.markdown("##### 📊 Planilha de Carga (CSV / Excel Pt-BR)")
            st.caption("Exportação rápida separada por ponto e vírgula (;).")
            csv_bytes = df_items.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                label="💾 Baixar Dados (CSV / Excel)",
                data=csv_bytes,
                file_name=f"packing_list_{current_project['project_code']}.csv",
                mime="text/csv"
            )

        st.divider()
        st.markdown("##### 🗂️ Relação Completa dos Itens")
        valid_cols = [c for c in ["tag_or_serial", "level_type", "description", "weight_kg", "declared_value_brl", "mob_receipt_ok", "desmob_status"] if c in df_items.columns]
        st.dataframe(df_items[valid_cols], use_container_width=True)
    else:
        st.info("Nenhum item cadastrado para esta campanha.")