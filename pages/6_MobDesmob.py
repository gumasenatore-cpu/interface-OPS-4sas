import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import requests
from supabase import create_client, Client

# Compressão automática de fotos da câmera mobile (com fallback seguro)
try:
    from PIL import Image as PILImage, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

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
    .quick-card {
        background-color: #f8fafc;
        border: 1px solid #cbd5e1;
        border-left: 5px solid #0f2b48;
        border-radius: 8px;
        padding: 12px 14px;
        margin-bottom: 10px;
    }
    .qty-display {
        text-align: center;
        font-size: 20px;
        font-weight: 700;
        color: #0f2b48;
        padding-top: 8px;
    }
    .tree-box-header {
        background-color: #0f2b48;
        color: white;
        padding: 8px 12px;
        border-radius: 6px;
        font-weight: 600;
        margin-top: 10px;
        margin-bottom: 4px;
    }
    .tree-subbox-header {
        background-color: #e2e8f0;
        color: #0f2b48;
        padding: 6px 12px;
        border-left: 4px solid #0f2b48;
        border-radius: 4px;
        font-weight: 600;
        margin-left: 14px;
        margin-top: 6px;
        margin-bottom: 4px;
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
# HELPERS DE COMPRESSÃO, UPLOAD, IMAGENS E ORDENAÇÃO HIERÁRQUICA
# ------------------------------------------------------------------------------
def compress_image_for_mobile(raw_bytes: bytes, original_name: str = "", original_mime: str = "image/jpeg"):
    """
    Redimensiona fotos pesadas da câmera (5MB-12MB) para no máximo 1024px (JPEG ~150KB),
    corrigindo orientação EXIF do celular para upload instantâneo em campo.
    """
    if not HAS_PIL:
        ext = "jpg"
        if original_name and "." in original_name:
            cand = original_name.rsplit(".", 1)[-1].lower()
            if cand in ["jpg", "jpeg", "png", "webp"]:
                ext = cand
        return raw_bytes, ext, (original_mime or "image/jpeg")

    try:
        img = PILImage.open(BytesIO(raw_bytes))
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "P", "LA"):
            background = PILImage.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        img.thumbnail((1024, 1024), PILImage.Resampling.LANCZOS)
        out_buf = BytesIO()
        img.save(out_buf, format="JPEG", quality=80, optimize=True)
        return out_buf.getvalue(), "jpg", "image/jpeg"
    except Exception:
        return raw_bytes, "jpg", (original_mime or "image/jpeg")


def is_uploaded_file_ready(uploaded_file) -> tuple[bool, str]:
    """
    Verifica se o arquivo enviado pelo navegador mobile já concluiu a transferência
    e possui bytes válidos (evita clicar em Salvar enquanto a câmera ainda está subindo).
    """
    if uploaded_file is None:
        return True, ""
    try:
        data = uploaded_file.getvalue()
        if not data or len(data) == 0:
            return False, "⏳ A foto da câmera ainda está sendo transferida pelo celular. Aguarde 2 segundos e tente novamente."
        return True, f"✅ Foto pronta ({round(len(data) / 1024, 1)} KB original)"
    except Exception:
        return False, "⏳ Aguardando conclusão do carregamento da foto no navegador..."


def upload_photo_to_storage(uploaded_file, project_code, tag_serial, prefix="mob", suffix_idx=0):
    """
    Comprime e faz upload da foto para o bucket 'mob-evidences'.
    Retorna (url_publica, mensagem_erro).
    """
    if uploaded_file is None:
        return None, None
    try:
        raw_bytes = uploaded_file.getvalue()
        if not raw_bytes or len(raw_bytes) == 0:
            return None, "A foto não terminou de carregar antes do envio (0 bytes). Aguarde o preview da foto aparecer antes de salvar."

        compressed_bytes, file_ext, mime_type = compress_image_for_mobile(
            raw_bytes,
            original_name=getattr(uploaded_file, "name", ""),
            original_mime=getattr(uploaded_file, "type", "image/jpeg")
        )

        clean_tag = "".join([c for c in str(tag_serial) if c.isalnum() or c in ("-", "_")]).strip() or "item"
        clean_proj = "".join([c for c in str(project_code) if c.isalnum() or c in ("-", "_")]).strip() or "proj"

        ts = int(datetime.now().timestamp() * 1000)
        filename = f"{clean_proj}/{clean_tag}_{prefix}_{ts}_{suffix_idx}.{file_ext}"

        supabase.storage.from_("mob-evidences").upload(
            path=filename,
            file=compressed_bytes,
            file_options={"upsert": "true", "content-type": mime_type}
        )
        public_url = supabase.storage.from_("mob-evidences").get_public_url(filename)
        return public_url, None
    except Exception as e:
        return None, f"Erro no Supabase Storage (verifique Policies de 'mob-evidences'): {e}"


def render_safe_image(url_val, caption=""):
    if isinstance(url_val, str) and url_val.strip().startswith("http"):
        try:
            st.image(url_val.strip(), caption=caption, use_container_width=True)
            return True
        except Exception:
            st.caption(f"📷 {caption} registrada (preview indisponível)")
            return True
    return False


def format_tag_display(tag_val):
    if not tag_val or str(tag_val).strip() in ("", "None", "nan", "S/TAG"):
        return "S/TAG"
    return str(tag_val).strip()


def build_hierarchical_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Ordena os itens em árvore real:
    Caixa Pai -> Sub-caixa -> Itens dentro da Sub-caixa -> Itens diretos da Caixa Pai -> Itens soltos no deck.
    """
    if df_raw.empty:
        return df_raw

    df = df_raw.copy()
    if "quantity" not in df.columns:
        df["quantity"] = 1
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1).astype(int)
    df.loc[df["quantity"] < 1, "quantity"] = 1

    records_by_id = {str(r["id"]): r.to_dict() for _, r in df.iterrows()}

    def get_container_name(pid):
        if pd.isna(pid) or not pid:
            return "Deck / Sem Caixa"
        p_rec = records_by_id.get(str(pid))
        if not p_rec:
            return "Deck / Sem Caixa"
        t = format_tag_display(p_rec.get("tag_or_serial"))
        return f"{t} ({p_rec.get('description', '')})"

    ordered_rows = []
    visited_ids = set()

    parent_boxes = df[df["level_type"] == "parent_box"]
    for _, pb in parent_boxes.iterrows():
        pb_id = str(pb["id"])
        row_pb = pb.to_dict()
        row_pb["tree_depth"] = 0
        row_pb["container_label"] = "Volume Principal"
        ordered_rows.append(row_pb)
        visited_ids.add(pb_id)

        sub_boxes = df[(df["level_type"] == "sub_box") & (df["parent_id"].astype(str) == pb_id)]
        for _, sb in sub_boxes.iterrows():
            sb_id = str(sb["id"])
            row_sb = sb.to_dict()
            row_sb["tree_depth"] = 1
            row_sb["container_label"] = get_container_name(pb_id)
            ordered_rows.append(row_sb)
            visited_ids.add(sb_id)

            sb_items = df[(df["level_type"] == "item") & (df["parent_id"].astype(str) == sb_id)]
            for _, it in sb_items.iterrows():
                row_it = it.to_dict()
                row_it["tree_depth"] = 2
                row_it["container_label"] = get_container_name(sb_id)
                ordered_rows.append(row_it)
                visited_ids.add(str(it["id"]))

        pb_items = df[(df["level_type"] == "item") & (df["parent_id"].astype(str) == pb_id)]
        for _, it in pb_items.iterrows():
            row_it = it.to_dict()
            row_it["tree_depth"] = 1
            row_it["container_label"] = get_container_name(pb_id)
            ordered_rows.append(row_it)
            visited_ids.add(str(it["id"]))

    orphan_subs = df[(df["level_type"] == "sub_box") & (~df["id"].astype(str).isin(visited_ids))]
    for _, sb in orphan_subs.iterrows():
        sb_id = str(sb["id"])
        row_sb = sb.to_dict()
        row_sb["tree_depth"] = 0
        row_sb["container_label"] = "Sub-caixa Avulsa"
        ordered_rows.append(row_sb)
        visited_ids.add(sb_id)

        sb_items = df[(df["level_type"] == "item") & (df["parent_id"].astype(str) == sb_id)]
        for _, it in sb_items.iterrows():
            row_it = it.to_dict()
            row_it["tree_depth"] = 1
            row_it["container_label"] = get_container_name(sb_id)
            ordered_rows.append(row_it)
            visited_ids.add(str(it["id"]))

    remaining = df[~df["id"].astype(str).isin(visited_ids)]
    for _, it in remaining.iterrows():
        row_it = it.to_dict()
        row_it["tree_depth"] = 0
        row_it["container_label"] = get_container_name(it.get("parent_id"))
        ordered_rows.append(row_it)

    return pd.DataFrame(ordered_rows)


def filter_subtree(df_hier: pd.DataFrame, root_box_id: str) -> pd.DataFrame:
    if df_hier.empty or not root_box_id:
        return df_hier

    selected_ids = {str(root_box_id)}
    children_1 = df_hier[df_hier["parent_id"].astype(str) == str(root_box_id)]
    for _, r in children_1.iterrows():
        selected_ids.add(str(r["id"]))
        children_2 = df_hier[df_hier["parent_id"].astype(str) == str(r["id"])]
        for _, r2 in children_2.iterrows():
            selected_ids.add(str(r2["id"]))

    return df_hier[df_hier["id"].astype(str).isin(selected_ids)].copy()

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
            parents_dict[f"[CAIXA PAI] {format_tag_display(b['tag_or_serial'])} - {b['description']}"] = b["id"]

        sub_boxes = df_items[(df_items["level_type"] == "sub_box") & (df_items["id"] != item["id"])]
        for _, sb in sub_boxes.iterrows():
            sub_boxes_dict[f"[SUB-CAIXA] {format_tag_display(sb['tag_or_serial'])} - {sb['description']}"] = sb["id"]

    st.write("📷 **Atualizar / Adicionar Foto de Mobilização**")
    new_img_mob = st.file_uploader(
        "Tirar foto ou escolher da galeria",
        type=["jpg", "png", "jpeg", "webp"],
        key=f"edit_img_mob_{item['id']}"
    )
    img_ready, img_msg = is_uploaded_file_ready(new_img_mob)
    if new_img_mob is not None:
        if img_ready:
            st.success(img_msg)
        else:
            st.warning(img_msg)

    with st.form(f"form_edit_dialog_{item['id']}"):
        curr_tag = "" if item.get("tag_or_serial") == "S/TAG" else (item.get("tag_or_serial") or "")
        new_tag = st.text_input("Tag / Identificador (opcional para item solto)", value=curr_tag)
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

        c_ed1, c_ed2 = st.columns([3, 1])
        with c_ed1:
            new_desc = st.text_input("Descrição *", value=item.get("description", ""))
        with c_ed2:
            new_qty = st.number_input("Qtd", min_value=1, step=1, value=int(item.get("quantity", 1)))

        c_ed3, c_ed4 = st.columns(2)
        with c_ed3:
            new_w = st.number_input("Peso Total do Item (kg)", min_value=0.0, step=0.5, value=float(item.get("weight_kg", 0.0)))
        with c_ed4:
            new_val = st.number_input("Valor Total (R$)", min_value=0.0, step=100.0, value=float(item.get("declared_value_brl", 0.0)))

        new_mob_notes = st.text_area("Obs. Saída Galpão", value=item.get("mob_notes") or "")

        btn_save = st.form_submit_button("💾 Salvar Alterações", type="primary")

        if btn_save:
            if not img_ready:
                st.error(img_msg)
                st.stop()
            if not new_desc.strip():
                st.error("A descrição é obrigatória.")
                st.stop()
            if new_level in ["parent_box", "sub_box"] and not new_tag.strip():
                st.error("Tag / Identificador é obrigatório para Caixa Pai e Sub-caixa.")
                st.stop()

            final_tag = new_tag.strip() if new_tag.strip() else "S/TAG"

            mob_url = item.get("mob_photo_url")
            if not isinstance(mob_url, str) or not mob_url.strip().startswith("http"):
                mob_url = None

            if new_img_mob:
                up_url, up_err = upload_photo_to_storage(new_img_mob, current_project["project_code"], final_tag, prefix="mob")
                if up_err:
                    st.error(up_err)
                    st.stop()
                if up_url:
                    mob_url = up_url

            upd_payload = {
                "tag_or_serial": final_tag,
                "description": new_desc.strip(),
                "quantity": int(new_qty),
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
# GERADOR DE PDF EXECUTIVO (CÓPIA FÍSICA PARA EMPLASTIFICAR - SEM EMOJIS)
# ------------------------------------------------------------------------------
def generate_packing_list_pdf(project_info, df_hier, scope_title="MANIFESTO COMPLETO DE CARGA"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=24,
        leftMargin=24,
        topMargin=24,
        bottomMargin=24
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, leading=19, textColor=colors.HexColor('#0f2b48'), spaceAfter=3)
    subtitle_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontSize=8.5, leading=12, textColor=colors.HexColor('#334155'), spaceAfter=8)
    cell_style = ParagraphStyle('CellText', parent=styles['Normal'], fontSize=8, leading=10)
    cell_bold = ParagraphStyle('CellBold', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold')
    cell_bold_white = ParagraphStyle('CellBoldWhite', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold', textColor=colors.white)
    box_title_style = ParagraphStyle('BoxTitle', parent=styles['Normal'], fontSize=8.5, leading=11, fontName='Helvetica-Bold', textColor=colors.white)
    subbox_title_style = ParagraphStyle('SubBoxTitle', parent=styles['Normal'], fontSize=8.5, leading=11, fontName='Helvetica-Bold', textColor=colors.HexColor('#0f2b48'))

    story = []

    story.append(Paragraph(f"4SAS — {scope_title}", title_style))
    meta_text = (
        f"<b>Campanha / Projeto:</b> {project_info.get('project_code', 'N/A')} | "
        f"<b>Cliente:</b> {project_info.get('client_name') or 'N/A'}<br/>"
        f"<b>Embarcacao / Local:</b> {project_info.get('vessel_name') or 'N/A'} | "
        f"<b>Responsavel Tecnico:</b> {project_info.get('responsible_user', 'N/A')} | "
        f"<b>Emissao:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    story.append(Paragraph(meta_text, subtitle_style))

    total_w = df_hier["weight_kg"].sum() if not df_hier.empty and "weight_kg" in df_hier else 0.0
    total_v = df_hier["declared_value_brl"].sum() if not df_hier.empty and "declared_value_brl" in df_hier else 0.0
    total_lines = len(df_hier) if not df_hier.empty else 0
    total_units = int(df_hier["quantity"].sum()) if not df_hier.empty and "quantity" in df_hier else total_lines

    kpi_data = [
        [
            Paragraph("<b>Peso Total</b>", cell_bold),
            Paragraph("<b>Valor Declarado</b>", cell_bold),
            Paragraph("<b>Linhas / Volumes</b>", cell_bold),
            Paragraph("<b>Total de Pecas (Qtd)</b>", cell_bold)
        ],
        [
            Paragraph(f"{total_w:,.2f} kg", cell_style),
            Paragraph(f"R$ {total_v:,.2f}", cell_style),
            Paragraph(f"{total_lines}", cell_style),
            Paragraph(f"{total_units} un", cell_style)
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[141, 141, 141, 141])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 10))

    # Colunas: Tag (92) | Qtd (32) | Descricao / Conteudo (240) | Peso (55) | Valor (75) | Status (70) = 564pt
    col_widths = [92, 32, 240, 55, 75, 70]
    table_data = [[
        Paragraph("Tag / Serial", cell_bold_white),
        Paragraph("Qtd", cell_bold_white),
        Paragraph("Descricao / Conteudo", cell_bold_white),
        Paragraph("Peso (kg)", cell_bold_white),
        Paragraph("Valor (R$)", cell_bold_white),
        Paragraph("Status", cell_bold_white)
    ]]

    row_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f2b48')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]

    current_row_idx = 1

    for _, row in df_hier.iterrows():
        l_type = row.get("level_type", "item")
        depth = int(row.get("tree_depth", 0))
        tag_str = format_tag_display(row.get("tag_or_serial"))
        qty_val = int(row.get("quantity", 1))
        desc_str = str(row.get("description", ""))
        w_str = f"{float(row.get('weight_kg', 0.0)):,.2f}"
        v_str = f"R$ {float(row.get('declared_value_brl', 0.0)):,.2f}"
        rec_status = "OK (Navio)" if row.get("mob_receipt_ok") else "Pendente"

        if l_type == "parent_box":
            table_data.append([
                Paragraph(f"<b>{tag_str}</b>", box_title_style),
                Paragraph(f"<b>{qty_val}</b>", box_title_style),
                Paragraph(f"<b>[CAIXA PAI] {desc_str}</b>", box_title_style),
                Paragraph(f"<b>{w_str}</b>", box_title_style),
                Paragraph(f"<b>{v_str}</b>", box_title_style),
                Paragraph(f"<b>{rec_status}</b>", box_title_style)
            ])
            row_styles.append(('BACKGROUND', (0, current_row_idx), (-1, current_row_idx), colors.HexColor('#1e3a5f')))
            current_row_idx += 1

        elif l_type == "sub_box":
            indent = "&nbsp;&nbsp;&nbsp;|-- " if depth > 0 else ""
            table_data.append([
                Paragraph(f"<b>{tag_str}</b>", subbox_title_style),
                Paragraph(f"<b>{qty_val}</b>", subbox_title_style),
                Paragraph(f"{indent}<b>[SUB-CAIXA] {desc_str}</b>", subbox_title_style),
                Paragraph(f"<b>{w_str}</b>", subbox_title_style),
                Paragraph(f"<b>{v_str}</b>", subbox_title_style),
                Paragraph(f"<b>{rec_status}</b>", subbox_title_style)
            ])
            row_styles.append(('BACKGROUND', (0, current_row_idx), (-1, current_row_idx), colors.HexColor('#dbeafe')))
            current_row_idx += 1

        else:
            indent = "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|-- " if depth >= 2 else ("&nbsp;&nbsp;&nbsp;|-- " if depth == 1 else "")
            table_data.append([
                Paragraph(tag_str, cell_style),
                Paragraph(f"<b>{qty_val}</b>", cell_style),
                Paragraph(f"{indent}{desc_str}", cell_style),
                Paragraph(w_str, cell_style),
                Paragraph(v_str, cell_style),
                Paragraph(rec_status, cell_style)
            ])
            if depth >= 1:
                row_styles.append(('BACKGROUND', (0, current_row_idx), (-1, current_row_idx), colors.HexColor('#f8fafc')))
            current_row_idx += 1

        # Evidências fotográficas do item
        mob_img_obj = None
        desmob_img_obj = None

        mob_url = row.get("mob_photo_url")
        if isinstance(mob_url, str) and mob_url.strip().startswith("http"):
            try:
                r1 = requests.get(mob_url.strip(), timeout=5)
                if r1.status_code == 200:
                    mob_img_obj = RLImage(BytesIO(r1.content), width=85, height=62)
            except Exception:
                pass

        desmob_url = row.get("desmob_photo_url")
        if isinstance(desmob_url, str) and desmob_url.strip().startswith("http"):
            try:
                r2 = requests.get(desmob_url.strip(), timeout=5)
                if r2.status_code == 200:
                    desmob_img_obj = RLImage(BytesIO(r2.content), width=85, height=62)
            except Exception:
                pass

        if mob_img_obj or desmob_img_obj:
            photo_cells = []
            if mob_img_obj:
                photo_cells.append([Paragraph("<b>Foto Saida (Galpao):</b>", cell_style), mob_img_obj])
            if desmob_img_obj:
                photo_cells.append([Paragraph("<b>Foto Retorno (Desmob):</b>", cell_style), desmob_img_obj])

            sub_t = Table(photo_cells, colWidths=[110, 95])
            sub_t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))

            table_data.append([
                Paragraph("", cell_style),
                Paragraph("", cell_style),
                sub_t,
                Paragraph("", cell_style),
                Paragraph("", cell_style),
                Paragraph("", cell_style)
            ])
            row_styles.append(('SPAN', (2, current_row_idx), (5, current_row_idx)))
            current_row_idx += 1

    items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle(row_styles))
    story.append(items_table)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ------------------------------------------------------------------------------
# INTERFACE PRINCIPAL
# ------------------------------------------------------------------------------
st.title("📋 Packing List & Gestão de Carga")

# Feedback persistente após salvar item rápido no ciclo anterior
if "mob_last_saved_msg" in st.session_state:
    st.success(st.session_state.pop("mob_last_saved_msg"))

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

auth_user = st.session_state.get("portal_authenticated_user") or {}
current_user_email = auth_user.get("email") or st.session_state.get("user_email", "operacoes@4sas.com.br")

if selected_proj_label == "-- Criar Nova Campanha --":
    st.info("👈 Crie ou selecione uma campanha na barra lateral para iniciar o Packing List.")
    with st.sidebar.form("form_new_project"):
        st.subheader("➕ Nova Campanha")
        p_code = st.text_input("Código do Projeto (ex: MOB-2026-BF-01)")
        p_client = st.text_input("Cliente")
        p_vessel = st.text_input("Embarcação / Local")
        p_user = st.text_input("Responsável Técnico", value=current_user_email)
        btn_proj = st.form_submit_button("Criar Campanha")

        if btn_proj and p_code:
            try:
                payload_p = {
                    "project_code": p_code.strip(),
                    "client_name": p_client.strip() if p_client else None,
                    "vessel_name": p_vessel.strip() if p_vessel else None,
                    "responsible_user": p_user.strip() if p_user else current_user_email,
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

# Carregamento Resiliente + Ordenação Hierárquica
try:
    items_res = supabase.table("mob_packing_list_items").select("*").eq("project_id", proj_id).order("created_at", desc=False).execute()
    items = items_res.data or []
except Exception as e:
    items = []
    st.error(f"Erro ao carregar itens da campanha: {e}")

df_raw = pd.DataFrame(items) if items else pd.DataFrame()
df_items = build_hierarchical_dataframe(df_raw) if not df_raw.empty else pd.DataFrame()

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
total_w = df_items["weight_kg"].sum() if not df_items.empty and "weight_kg" in df_items else 0.0
total_v = df_items["declared_value_brl"].sum() if not df_items.empty and "declared_value_brl" in df_items else 0.0
total_c = len(df_items) if not df_items.empty else 0
total_u = int(df_items["quantity"].sum()) if not df_items.empty and "quantity" in df_items else 0

col_m1.metric("⚖️ Peso Total", f"{total_w:,.2f} kg")
col_m2.metric("💰 Valor Declarado", f"R$ {total_v:,.2f}")
col_m3.metric("📦 Linhas / Volumes", f"{total_c}")
col_m4.metric("🔢 Total de Peças", f"{total_u} un")

st.divider()

tab_mob, tab_desmob, tab_report = st.tabs([
    "🚀 1. Mobilização (Cadastro & Conferência)",
    "🔄 2. Desmobilização (Retorno & Galpão)",
    "📊 3. Resumo & PDF Executivo"
])

# ------------------------------------------------------------------------------
# TAB 1: MOBILIZAÇÃO (FLUXO RÁPIDO DE CAMPO + CAIXAS + GALERIA)
# ------------------------------------------------------------------------------
with tab_mob:
    st.subheader("⚡ 1.1 Cadastro Rápido de Campo")

    parents_dict = {}
    sub_boxes_dict = {}
    if not df_items.empty and "level_type" in df_items:
        for _, b in df_items[df_items["level_type"] == "parent_box"].iterrows():
            parents_dict[f"🧰 [CAIXA PAI] {format_tag_display(b['tag_or_serial'])} - {b['description']}"] = b["id"]
        for _, sb in df_items[df_items["level_type"] == "sub_box"].iterrows():
            sub_boxes_dict[f"📦 [SUB-CAIXA] {format_tag_display(sb['tag_or_serial'])} - {sb['description']}"] = sb["id"]

    cad_mode = st.radio(
        "O que você deseja cadastrar agora?",
        options=["quick_item", "create_box", "gallery_batch"],
        format_func=lambda x: {
            "quick_item": "⚡ Item Rápido (1 por vez c/ Câmera)",
            "create_box": "🧰 Criar Caixa Pai / Sub-caixa",
            "gallery_batch": "🖼️ Importar Várias Fotos da Galeria"
        }[x],
        horizontal=True
    )

    # --------------------------------------------------------------------------
    # MODO 1: CARTÃO ÚNICO RÁPIDO (CAIXA TRAVADA + BOTÕES +/- + TRAVA DE FOTO)
    # --------------------------------------------------------------------------
    if cad_mode == "quick_item":
        all_containers = {"-- Item Solto (Direto no Deck) --": None}
        all_containers.update(parents_dict)
        all_containers.update(sub_boxes_dict)

        target_box_label = st.selectbox(
            "📍 Caixa / Local de Destino (fica travada para os próximos itens):",
            list(all_containers.keys()),
            key=f"quick_target_box_{proj_id}"
        )
        quick_parent_id = all_containers[target_box_label]

        # Contador ao vivo de itens já dentro da caixa selecionada
        if not df_items.empty:
            if quick_parent_id is None:
                count_in_box = len(df_items[(df_items["level_type"] == "item") & (df_items["parent_id"].isna())])
            else:
                count_in_box = len(df_items[df_items["parent_id"].astype(str) == str(quick_parent_id)])
            st.caption(f"📊 Já registrados neste destino: **{count_in_box} itens**")

        # Inicializa estado do cartão rápido (com contador de reset limpo)
        reset_counter_key = f"quick_reset_cnt_{proj_id}"
        if reset_counter_key not in st.session_state:
            st.session_state[reset_counter_key] = 0
        rc = st.session_state[reset_counter_key]

        qty_state_key = f"quick_qty_{proj_id}_{rc}"
        if qty_state_key not in st.session_state:
            st.session_state[qty_state_key] = 1

        st.markdown("<div class='quick-card'>", unsafe_allow_html=True)

        # 1) Foto da Câmera / Galeria com validação de integridade
        q_photo = st.file_uploader(
            "📷 1. Foto do Item (Câmera ou Galeria)",
            type=["jpg", "png", "jpeg", "webp"],
            key=f"quick_photo_{proj_id}_{rc}"
        )
        photo_ready, photo_status_msg = is_uploaded_file_ready(q_photo)
        if q_photo is not None:
            if photo_ready:
                st.success(photo_status_msg)
            else:
                st.warning(photo_status_msg)

        # 2) Nome do Item
        q_desc = st.text_input(
            "🏷️ 2. Nome / Descrição do Item *",
            placeholder="ex: Cabo Sensys LAN, Magnetômetro, Adaptador...",
            key=f"quick_desc_{proj_id}_{rc}"
        )

        # 3) Quantidade com botões grandes + e -
        st.markdown("**🔢 3. Quantidade:**")
        c_q1, c_q2, c_q3 = st.columns([1, 1, 1])
        with c_q1:
            if st.button("➖", key=f"btn_minus_{proj_id}_{rc}"):
                if st.session_state[qty_state_key] > 1:
                    st.session_state[qty_state_key] -= 1
                    st.rerun()
        with c_q2:
            st.markdown(f"<div class='qty-display'>{st.session_state[qty_state_key]} un</div>", unsafe_allow_html=True)
        with c_q3:
            if st.button("➕", key=f"btn_plus_{proj_id}_{rc}"):
                st.session_state[qty_state_key] += 1
                st.rerun()

        # Campos avançados opcionais recolhidos para não poluir a tela do celular
        with st.expander("⚙️ Opcionais (Tag / Serial, Peso, Valor, Observação)"):
            q_tag = st.text_input("Tag / Número de Série (deixe vazio para S/TAG)", key=f"quick_tag_{proj_id}_{rc}")
            c_opt1, c_opt2 = st.columns(2)
            with c_opt1:
                q_weight = st.number_input("Peso Total (kg)", min_value=0.0, step=0.5, value=0.0, key=f"quick_w_{proj_id}_{rc}")
            with c_opt2:
                q_val = st.number_input("Valor Total (R$)", min_value=0.0, step=100.0, value=0.0, key=f"quick_v_{proj_id}_{rc}")
            q_notes = st.text_input("Observação de despacho", key=f"quick_notes_{proj_id}_{rc}")

        st.markdown("</div>", unsafe_allow_html=True)

        # Botão principal de salvamento com trava caso a foto ainda esteja transferindo
        save_disabled = (q_photo is not None and not photo_ready)
        if st.button(
            "✅ Salvar e Próximo Item",
            type="primary",
            disabled=save_disabled,
            key=f"btn_quick_save_{proj_id}_{rc}"
        ):
            if not q_desc or not q_desc.strip():
                st.warning("⚠️ Digite o nome do item antes de salvar.")
            else:
                final_tag = q_tag.strip() if (q_tag and q_tag.strip()) else "S/TAG"
                qty_to_save = int(st.session_state[qty_state_key])

                with st.spinner("Comprimindo foto e salvando item..."):
                    photo_url = None
                    if q_photo is not None:
                        photo_url, up_err = upload_photo_to_storage(
                            q_photo,
                            current_project["project_code"],
                            final_tag,
                            prefix="mob"
                        )
                        if up_err:
                            st.error(up_err)
                            st.stop()

                    payload_item = {
                        "project_id": proj_id,
                        "parent_id": quick_parent_id,
                        "level_type": "item",
                        "item_type": "loose_item",
                        "tag_or_serial": final_tag,
                        "description": q_desc.strip(),
                        "quantity": qty_to_save,
                        "weight_kg": float(q_weight),
                        "declared_value_brl": float(q_val),
                        "mob_notes": q_notes.strip() if q_notes else None,
                        "mob_photo_url": photo_url,
                        "mob_dispatch_ok": True,
                        "mob_by": current_user_email,
                        "mob_timestamp": datetime.now().isoformat()
                    }
                    try:
                        supabase.table("mob_packing_list_items").insert(payload_item).execute()
                        # Incrementa o contador de reset para limpar os inputs mantendo a caixa selecionada
                        st.session_state[reset_counter_key] += 1
                        foto_txt = " (com foto)" if photo_url else " (sem foto)"
                        st.session_state["mob_last_saved_msg"] = f"✅ Salvo: {qty_to_save}x {q_desc.strip()}{foto_txt}. Pronto para o próximo!"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar item: {e}")

    # --------------------------------------------------------------------------
    # MODO 2: CRIAR CAIXA PAI OU SUB-CAIXA
    # --------------------------------------------------------------------------
    elif cad_mode == "create_box":
        box_level = st.radio(
            "Tipo de Recipiente:",
            options=["parent_box", "sub_box"],
            format_func=lambda x: "🧰 Caixa Pai / Contêiner Principal" if x == "parent_box" else "📦 Sub-caixa / Maleta Interna",
            horizontal=True
        )

        box_parent_id = None
        if box_level == "sub_box":
            if parents_dict:
                sel_p = st.selectbox("🔗 Esta Sub-caixa está dentro de qual Caixa Pai?", list(parents_dict.keys()))
                box_parent_id = parents_dict[sel_p]
            else:
                st.warning("⚠️ Cadastre uma Caixa Pai primeiro para vincular esta Sub-caixa.")

        box_photo = st.file_uploader(
            "📷 Foto Externa da Caixa (Câmera ou Galeria)",
            type=["jpg", "png", "jpeg", "webp"],
            key="box_img_uploader_direct"
        )
        b_photo_ready, b_photo_msg = is_uploaded_file_ready(box_photo)
        if box_photo is not None:
            if b_photo_ready:
                st.success(b_photo_msg)
            else:
                st.warning(b_photo_msg)

        with st.form("form_create_box_cad", clear_on_submit=True):
            c_bx1, c_bx2 = st.columns(2)
            with c_bx1:
                box_tag = st.text_input("Tag / Código da Caixa *", placeholder="ex: CAIXA-MAG-01")
                box_desc = st.text_input("Descrição da Caixa *", placeholder="ex: Patola laranja / Caixa metálica azul")
            with c_bx2:
                box_weight = st.number_input("Peso Bruto (kg)", min_value=0.0, step=0.5, value=0.0)
                box_val = st.number_input("Valor Declarado (R$)", min_value=0.0, step=100.0, value=0.0)
                box_notes = st.text_input("Obs. da Caixa (lacre, estado físico...)")

            btn_save_box = st.form_submit_button("💾 Cadastrar Caixa", type="primary")
            if btn_save_box:
                if not b_photo_ready:
                    st.error(b_photo_msg)
                    st.stop()
                if not box_tag.strip() or not box_desc.strip():
                    st.warning("⚠️ Tag e Descrição são obrigatórias para cadastrar uma caixa.")
                else:
                    photo_url = None
                    if box_photo is not None:
                        photo_url, up_err = upload_photo_to_storage(box_photo, current_project["project_code"], box_tag.strip(), prefix="mob")
                        if up_err:
                            st.error(up_err)
                            st.stop()

                    payload_box = {
                        "project_id": proj_id,
                        "parent_id": box_parent_id,
                        "level_type": box_level,
                        "item_type": "box",
                        "tag_or_serial": box_tag.strip(),
                        "description": box_desc.strip(),
                        "quantity": 1,
                        "weight_kg": float(box_weight),
                        "declared_value_brl": float(box_val),
                        "mob_notes": box_notes.strip() if box_notes else None,
                        "mob_photo_url": photo_url,
                        "mob_dispatch_ok": True,
                        "mob_by": current_user_email,
                        "mob_timestamp": datetime.now().isoformat()
                    }
                    try:
                        supabase.table("mob_packing_list_items").insert(payload_box).execute()
                        st.session_state["mob_last_saved_msg"] = f"✅ Caixa [{box_tag.strip()}] cadastrada!"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar caixa: {e}")

    # --------------------------------------------------------------------------
    # MODO 3: IMPORTAR VÁRIAS FOTOS DA GALERIA DE UMA VEZ
    # --------------------------------------------------------------------------
    else:
        all_containers = {"-- Itens Soltos (Direto no Deck) --": None}
        all_containers.update(parents_dict)
        all_containers.update(sub_boxes_dict)

        gal_box_label = st.selectbox(
            "📍 Caixa de Destino para as fotos importadas:",
            list(all_containers.keys()),
            key="gal_target_box"
        )
        gal_parent_id = all_containers[gal_box_label]

        multi_photos = st.file_uploader(
            "Selecione várias fotos já tiradas na galeria do celular",
            type=["jpg", "png", "jpeg", "webp"],
            accept_multiple_files=True,
            key=f"gal_multi_photos_{proj_id}"
        )

        if multi_photos:
            st.info(f"📎 {len(multi_photos)} fotos carregadas. Preencha o nome e a quantidade de cada uma abaixo:")
            gal_entries = []
            for idx_p, p_file in enumerate(multi_photos):
                c_g1, c_g2, c_g3 = st.columns([1, 3, 1])
                with c_g1:
                    try:
                        st.image(p_file, width=80)
                    except Exception:
                        st.caption(p_file.name)
                with c_g2:
                    g_desc = st.text_input(
                        f"Nome do Item #{idx_p + 1} *",
                        placeholder="ex: Cabo LAN, Adaptador...",
                        key=f"gal_desc_{proj_id}_{idx_p}"
                    )
                with c_g3:
                    g_qty = st.number_input(
                        "Qtd",
                        min_value=1,
                        step=1,
                        value=1,
                        key=f"gal_qty_{proj_id}_{idx_p}"
                    )
                gal_entries.append({"photo": p_file, "desc": g_desc, "qty": g_qty})

            if st.button("💾 Salvar Todos os Itens da Galeria", type="primary", key="btn_save_gal_all"):
                valid_gal = [e for e in gal_entries if e["desc"] and e["desc"].strip()]
                if not valid_gal:
                    st.warning("⚠️ Preencha o nome de pelo menos 1 item antes de salvar.")
                else:
                    prog = st.progress(0, text="Comprimindo e enviando fotos...")
                    for idx_v, entry in enumerate(valid_gal):
                        photo_url, up_err = upload_photo_to_storage(
                            entry["photo"],
                            current_project["project_code"],
                            "STAG",
                            prefix="mob",
                            suffix_idx=idx_v
                        )
                        if up_err:
                            st.error(up_err)
                            st.stop()

                        payload_g = {
                            "project_id": proj_id,
                            "parent_id": gal_parent_id,
                            "level_type": "item",
                            "item_type": "loose_item",
                            "tag_or_serial": "S/TAG",
                            "description": entry["desc"].strip(),
                            "quantity": int(entry["qty"]),
                            "weight_kg": 0.0,
                            "declared_value_brl": 0.0,
                            "mob_notes": None,
                            "mob_photo_url": photo_url,
                            "mob_dispatch_ok": True,
                            "mob_by": current_user_email,
                            "mob_timestamp": datetime.now().isoformat()
                        }
                        supabase.table("mob_packing_list_items").insert(payload_g).execute()
                        prog.progress((idx_v + 1) / len(valid_gal))

                    st.session_state["mob_last_saved_msg"] = f"✅ {len(valid_gal)} itens importados da galeria com sucesso!"
                    st.rerun()

    # --------------------------------------------------------------------------
    # LISTAGEM HIERÁRQUICA E CHECKLIST DE RECEBIMENTO
    # --------------------------------------------------------------------------
    st.divider()
    st.subheader("🚢 1.2 Árvore de Carga & Checklist de Recebimento")

    if df_items.empty:
        st.info("Nenhum item cadastrado até o momento.")
    else:
        box_filter_opts = {"📋 Mostrar Toda a Carga (Árvore Completa)": None}
        for _, bx in df_items[df_items["level_type"].isin(["parent_box", "sub_box"])].iterrows():
            prefix_b = "🧰" if bx["level_type"] == "parent_box" else "📦"
            box_filter_opts[f"{prefix_b} Apenas conteúdo de: {format_tag_display(bx['tag_or_serial'])} ({bx['description']})"] = bx["id"]

        sel_filter_label = st.selectbox("Filtrar visualização por caixa:", list(box_filter_opts.keys()), key="mob_tree_filter")
        df_view = filter_subtree(df_items, box_filter_opts[sel_filter_label])

        for idx, item in df_view.iterrows():
            is_rec = bool(item.get("mob_receipt_ok", False))
            status_txt = "✅ OK Navio" if is_rec else "⏳ Pendente"
            l_type = item.get("level_type", "item")
            depth = int(item.get("tree_depth", 0))
            tag_disp = format_tag_display(item.get("tag_or_serial"))
            qty_disp = int(item.get("quantity", 1))
            has_photo_icon = "📷" if (isinstance(item.get("mob_photo_url"), str) and item.get("mob_photo_url").startswith("http")) else "⚠️ s/ foto"

            if l_type == "parent_box":
                st.markdown(f"<div class='tree-box-header'>🧰 CAIXA PAI: [{tag_disp}] {item['description']} — {status_txt}</div>", unsafe_allow_html=True)
            elif l_type == "sub_box":
                st.markdown(f"<div class='tree-subbox-header'>↳ 📦 SUB-CAIXA: [{tag_disp}] {item['description']} — {status_txt}</div>", unsafe_allow_html=True)

            indent_prefix = "↳ " if depth >= 1 and l_type == "item" else ""
            tag_badge = f"[{tag_disp}] " if tag_disp != "S/TAG" else ""
            expander_label = f"{indent_prefix}{qty_disp}x {tag_badge}{item['description']} ({has_photo_icon}) — {status_txt}"

            with st.expander(expander_label):
                col_left, col_right = st.columns([3, 2])
                with col_left:
                    st.markdown(f"**Localização / Caixa:** `{item.get('container_label', 'Deck')}`")
                    st.markdown(f"**Tag / Serial:** `{tag_disp}` | **Quantidade:** `{qty_disp} un`")
                    st.markdown(f"**Nível:** `{l_type}` | **Peso:** `{item.get('weight_kg')} kg`")
                    st.markdown(f"**Obs. Despacho Galpão:** {item.get('mob_notes') or 'Nenhuma'}")
                with col_right:
                    if not render_safe_image(item.get("mob_photo_url"), caption="Evidência Fotográfica MOB"):
                        st.warning("Sem foto registrada na saída — toque em 'Editar Registro' abaixo para adicionar.")

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
                    if st.button("✏️ Editar / Adicionar Foto", key=f"btn_ed_{item['id']}"):
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
            tag_disp = format_tag_display(item.get("tag_or_serial"))
            qty_disp = int(item.get("quantity", 1))
            tag_badge = f"[{tag_disp}] " if tag_disp != "S/TAG" else ""
            with st.expander(f"{qty_disp}x {tag_badge}{item['description']} — ({item.get('container_label', '')})", expanded=(item.get('desmob_status') == 'pending')):
                c_d1, c_d2 = st.columns([2, 3])
                with c_d1:
                    st.markdown(f"**Caixa / Origem:** `{item.get('container_label', 'Deck')}`")
                    st.markdown(f"**Tag/Serial:** `{tag_disp}` | **Qtd Saída:** `{qty_disp} un`")
                    st.markdown(f"**Peso:** {item['weight_kg']} kg | **Valor:** R$ {item['declared_value_brl']:,.2f}")

                    render_safe_image(item.get("mob_photo_url"), caption="Foto MOB (Galpão)")
                    render_safe_image(item.get("desmob_photo_url"), caption="Foto Retorno (Desmob)")

                with c_d2:
                    st.caption("🔄 **Check-in de Retorno**")
                    desmob_cam = st.file_uploader(
                        "Foto de Retorno (Estado Físico)",
                        type=["jpg", "png", "jpeg", "webp"],
                        key=f"cam_desmob_{item['id']}"
                    )
                    d_ready, d_msg = is_uploaded_file_ready(desmob_cam)
                    if desmob_cam is not None:
                        if d_ready:
                            st.success(d_msg)
                        else:
                            st.warning(d_msg)

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
                        obs_ret = st.text_area("Observações de Retorno (ex: faltou 1 cabo, etc.)", value=item.get("desmob_notes") or "")
                        btn_ret = st.form_submit_button("Confirmar Chegada", type="primary")

                        if btn_ret:
                            if not d_ready:
                                st.error(d_msg)
                                st.stop()

                            desmob_url = item.get("desmob_photo_url")
                            if not isinstance(desmob_url, str) or not desmob_url.strip().startswith("http"):
                                desmob_url = None

                            if desmob_cam:
                                up_url, up_err = upload_photo_to_storage(desmob_cam, current_project['project_code'], tag_disp, prefix="desmob")
                                if up_err:
                                    st.error(up_err)
                                    st.stop()
                                if up_url:
                                    desmob_url = up_url

                            payload_desmob = {
                                "desmob_status": status_ret,
                                "desmob_notes": obs_ret,
                                "desmob_photo_url": desmob_url,
                                "desmob_dispatch_ok": True,
                                "desmob_receipt_ok": True,
                                "desmob_receipt_by": current_user_email,
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
        pdf_scope_opts = {"📋 Campanha Completa (Todos os Volumes e Itens)": (None, "MANIFESTO DE CARGA / PACKING LIST")}
        for _, bx in df_items[df_items["level_type"].isin(["parent_box", "sub_box"])].iterrows():
            b_tag = format_tag_display(bx["tag_or_serial"])
            lbl = f"📦 Etiqueta Interna da Caixa: {b_tag} — {bx['description']}"
            pdf_scope_opts[lbl] = (bx["id"], f"CONTEUDO DA CAIXA: {b_tag} ({bx['description']})")

        selected_pdf_scope = st.selectbox(
            "Selecione o Escopo do Documento para Impressão:",
            list(pdf_scope_opts.keys()),
            key="pdf_scope_selector"
        )
        scope_box_id, scope_pdf_title = pdf_scope_opts[selected_pdf_scope]
        df_pdf_export = filter_subtree(df_items, scope_box_id) if scope_box_id else df_items

        col_pdf, col_csv = st.columns(2)

        with col_pdf:
            st.markdown("##### 📄 PDF Executivo Emplastificável")
            st.caption("Agrupado por caixa, com quantidades e fotos para fixar na tampa.")
            try:
                pdf_bytes = generate_packing_list_pdf(current_project, df_pdf_export, scope_title=scope_pdf_title)
                suffix_file = f"_{format_tag_display(df_pdf_export.iloc[0]['tag_or_serial'])}" if scope_box_id and not df_pdf_export.empty else ""
                st.download_button(
                    label="📄 Baixar Packing List Executivo (PDF)",
                    data=pdf_bytes,
                    file_name=f"packing_list_{current_project['project_code']}{suffix_file}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
            except Exception as e_pdf:
                st.error(f"Erro ao gerar PDF: {e_pdf}")

        with col_csv:
            st.markdown("##### 📊 Planilha de Carga (CSV / Excel Pt-BR)")
            st.caption("Exportação hierárquica separada por ponto e vírgula (;).")
            csv_bytes = df_pdf_export.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                label="💾 Baixar Dados (CSV / Excel)",
                data=csv_bytes,
                file_name=f"packing_list_{current_project['project_code']}.csv",
                mime="text/csv"
            )

        st.divider()
        st.markdown("##### 🗂️ Visualização Hierárquica Completa")
        valid_cols = [c for c in ["container_label", "tag_or_serial", "quantity", "level_type", "description", "weight_kg", "declared_value_brl", "mob_receipt_ok", "desmob_status"] if c in df_pdf_export.columns]
        st.dataframe(df_pdf_export[valid_cols], use_container_width=True)
    else:
        st.info("Nenhum item cadastrado para esta campanha.")