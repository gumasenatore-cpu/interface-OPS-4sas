import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# ------------------------------------------------------------------------------
# CONFIGURAÇÃO DE PÁGINA
# ------------------------------------------------------------------------------
st.set_page_config(page_title="Mob & Desmob | 4SAS", page_icon="📋", layout="wide")

SUPABASE_URL = st.secrets.get("SUPABASE_URL") or st.secrets.get("MAP_SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or st.secrets.get("MAP_SUPABASE_KEY")

@st.cache_resource
def init_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Credenciais do Supabase não encontradas no secrets.toml.")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

st.title("📋 Packing List: Mobilização & Desmobilização")

# ------------------------------------------------------------------------------
# GERENCIAMENTO DE CAMPANHAS / PROJETOS (MOB_PROJECTS)
# ------------------------------------------------------------------------------
st.sidebar.header("📁 Operação / Campanha")

try:
    proj_res = supabase.table("mob_projects").select("*").order("created_at", desc=True).execute()
    projects = proj_res.data or []
except Exception as e:
    projects = []
    st.error(f"Erro ao carregar projetos: {e}")

project_options = {f"[{p['project_code']}] {p.get('vessel_name') or 'Sem Embarcação'}": p for p in projects}

selected_proj_label = st.sidebar.selectbox(
    "Selecione a Campanha Ativa:", 
    options=["-- Criar Nova Campanha --"] + list(project_options.keys())
)

# Modal / Formulário de Criação de Novo Projeto na Sidebar
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
                    "client_name": p_client,
                    "vessel_name": p_vessel,
                    "responsible_user": p_user,
                    "status": "in_mobilization"
                }
                supabase.table("mob_projects").insert(payload_p).execute()
                st.success(f"Campanha {p_code} criada!")
                st.rerun()
            except Exception as err:
                err_str = str(err)
                if "23505" in err_str or "project_code_key" in err_str:
                    st.warning(f"⚠️ A campanha **'{p_code}'** já existe no sistema. Selecione-a no menu suspenso acima.")
                else:
                    st.error(f"Erro ao criar campanha: {err}")
    st.stop()

# Acessa o dicionário apenas quando uma campanha existente for selecionada
current_project = project_options[selected_proj_label]
proj_id = current_project["id"]

# Botão de Excluir Campanha na Sidebar
with st.sidebar.expander("⚙️ Gerenciar Campanha Selecionada"):
    st.warning(f"Atenção: Excluir a campanha **{current_project['project_code']}** removerá todos os itens e fotos associadas.")
    if st.button("🗑️ Excluir esta Campanha", type="primary"):
        try:
            supabase.table("mob_projects").delete().eq("id", proj_id).execute()
            st.success("Campanha excluída com sucesso!")
            st.rerun()
        except Exception as e_del:
            st.error(f"Erro ao excluir campanha: {e_del}")

# ------------------------------------------------------------------------------
# CABEÇALHO DA CAMPANHA E MÉTRICAS DA CARGA (PACKING LIST METRICS)
# ------------------------------------------------------------------------------
st.markdown(f"### 🚢 {current_project['project_code']} — {current_project.get('vessel_name', '')}")
st.caption(f"Cliente: **{current_project.get('client_name', 'N/A')}** | Responsável: **{current_project['responsible_user']}** | Status: **{current_project['status'].upper()}**")

# Carregar itens do Packing List
try:
    items_res = supabase.table("mob_packing_list_items").select("*").eq("project_id", proj_id).execute()
    items = items_res.data or []
except Exception as e:
    items = []
    st.error(f"Erro ao carregar itens: {e}")

df_items = pd.DataFrame(items) if items else pd.DataFrame()

# Métricas Totais do Packing List
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
total_weight = df_items["weight_kg"].sum() if not df_items.empty else 0.0
total_val = df_items["declared_value_brl"].sum() if not df_items.empty else 0.0
total_count = len(df_items) if not df_items.empty else 0
desmob_count = len(df_items[df_items["desmob_status"] != "pending"]) if not df_items.empty else 0

col_m1.metric("⚖️ Peso Total (kg)", f"{total_weight:,.2f} kg")
col_m2.metric("💰 Valor Declarado (R$)", f"R$ {total_val:,.2f}")
col_m3.metric("📦 Total de Itens Mobilizados", f"{total_count} itens")
col_m4.metric("🔄 Itens Desmobilizados", f"{desmob_count} / {total_count}")

st.divider()

# ------------------------------------------------------------------------------
# ABAS DE OPERAÇÃO: MOBILIZAÇÃO E DESMOBILIZAÇÃO
# ------------------------------------------------------------------------------
tab_mob, tab_desmob, tab_report = st.tabs(["🚀 1. Mobilização (Saída)", "🔍 2. Desmobilização (Retorno)", "📊 3. Resumo & Packing List"])

# ------------------------------------------------------------------------------
# TAB 1: MOBILIZAÇÃO
# ------------------------------------------------------------------------------
with tab_mob:
    st.subheader("➕ Registrar Item / Caixa no Packing List")
    
    # Mapear Caixas PAI existentes no projeto para vínculo
    boxes_dict = {}
    if not df_items.empty:
        boxes = df_items[df_items["item_type"] == "box"]
        for _, b in boxes.iterrows():
            boxes_dict[f"📦 [CAIXA] {b['tag_or_serial']} - {b['description']}"] = b["id"]

    with st.form("form_mob_item", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            item_type = st.radio("Tipo de Registro", ["box", "loose_item"], format_func=lambda x: "📦 Caixa / Contêiner PAI" if x == "box" else "🏷️ Item / Equipamento (Solto ou em Caixa)")
            tag_serial = st.text_input("Tag / Nº Patrimônio / Identificador da Caixa", placeholder="ex: CX-MBES-01 ou 4SAS-TRIMBLE-02")
            description = st.text_input("Descrição do Item / Conteúdo", placeholder="ex: Receptor GNSS Trimble BX992 + Antenas")
            
            parent_box_id = None
            if item_type == "loose_item" and boxes_dict:
                selected_box = st.selectbox("Pertence a alguma Caixa PAI? (Opcional)", ["-- Item Solto (Sem Caixa) --"] + list(boxes_dict.keys()))
                if selected_box != "-- Item Solto (Sem Caixa) --":
                    parent_box_id = boxes_dict[selected_box]

        with col2:
            weight = st.number_input("Peso Estimado / Medido (kg)", min_value=0.0, step=0.5, value=0.0)
            value_brl = st.number_input("Valor Declarado R$", min_value=0.0, step=100.0, value=0.0)
            mob_notes = st.text_area("Observações de Integridade Física", placeholder="Estado da maleta, lacres, conectores...")

        st.write("📷 **Foto de Mobilização (Câmera do Celular ou Upload)**")
        img_camera = st.camera_input("Tirar foto do item / caixa aberta")
        img_file = st.file_uploader("Ou carregar arquivo de foto", type=["jpg", "png", "jpeg"], key="mob_upload")

        btn_save_item = st.form_submit_button("💾 Salvar Item no Packing List")

        if btn_save_item:
            if tag_serial and description:
                photo_url = None
                
                # Upload para Supabase Storage se houver imagem
                img_to_upload = img_camera or img_file
                if img_to_upload:
                    try:
                        file_bytes = img_to_upload.getvalue()
                        filename = f"{current_project['project_code']}/{tag_serial}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        
                        supabase.storage.from_("mob-evidences").upload(filename, file_bytes)
                        photo_url = supabase.storage.from_("mob-evidences").get_public_url(filename)
                    except Exception as err_img:
                        st.warning(f"Item salvo, mas falhou ao enviar foto: {err_img}")

                payload_item = {
                    "project_id": proj_id,
                    "parent_id": parent_box_id,
                    "item_type": item_type,
                    "tag_or_serial": tag_serial,
                    "description": description,
                    "weight_kg": weight,
                    "declared_value_brl": value_brl,
                    "mob_notes": mob_notes,
                    "mob_photo_url": photo_url,
                    "mob_by": st.session_state.get("user_email", "operacoes@4sas.com.br"),
                    "mob_timestamp": datetime.now().isoformat()
                }

                try:
                    supabase.table("mob_packing_list_items").insert(payload_item).execute()
                    st.success(f"Item [{tag_serial}] adicionado com sucesso ao Packing List!")
                    st.rerun()
                except Exception as e_ins:
                    st.error(f"Erro ao salvar item: {e_ins}")
            else:
                st.warning("Preencha a Tag/Identificador e a Descrição do item.")

# ------------------------------------------------------------------------------
# TAB 2: DESMOBILIZAÇÃO (CONFRONTO LADO A LADO)
# ------------------------------------------------------------------------------
with tab_desmob:
    st.subheader("🔍 Conferência e Check-out de Retorno (Desmobilização)")
    
    if df_items.empty:
        st.info("Nenhum item cadastrado na mobilização para ser conferido.")
    else:
        for idx, item in df_items.iterrows():
            with st.expander(f"[{'📦 CAIXA' if item['item_type']=='box' else '🏷️ ITEM'}] {item['tag_or_serial']} - {item['description']}", expanded=(item['desmob_status'] == 'pending')):
                col_info, col_mob_photo, col_desmob_action = st.columns([2, 2, 3])
                
                with col_info:
                    st.markdown(f"**Tag/Serial:** `{item['tag_or_serial']}`")
                    st.markdown(f"**Peso:** {item['weight_kg']} kg | **Valor:** R$ {item['declared_value_brl']:,.2f}")
                    st.markdown(f"**Obs. Saída (MOB):** {item.get('mob_notes') or 'Nenhuma'}")
                    st.markdown(f"**Status Atual:** `{item['desmob_status'].upper()}`")

                with col_mob_photo:
                    st.caption("📷 **Foto na Mobilização (Saída)**")
                    if item.get("mob_photo_url"):
                        st.image(item["mob_photo_url"], use_container_width=True)
                    else:
                        st.info("Sem foto registrada na saída.")

                with col_desmob_action:
                    st.caption("🔄 **Check-in de Retorno**")
                    with st.form(f"form_desmob_{item['id']}"):
                        status_ret = st.selectbox(
                            "Status na Desmobilização", 
                            ["ok", "damaged", "lost", "left_on_site"],
                            index=0 if item['desmob_status']=='pending' else ["ok", "damaged", "lost", "left_on_site"].index(item['desmob_status']),
                            format_func=lambda x: {"ok": "✅ Retornou OK", "damaged": "⚠️ Danificado", "lost": "❌ Perdido / Ausente", "left_on_site": "📍 Deixado no Cliente/Embarcação"}[x]
                        )
                        obs_desmob = st.text_area("Observações de Retorno", value=item.get("desmob_notes") or "")
                        desmob_cam = st.camera_input("Foto do estado no retorno", key=f"cam_{item['id']}")
                        
                        btn_update = st.form_submit_button("Confirmar Retorno do Item")
                        
                        if btn_update:
                            desmob_photo_url = item.get("desmob_photo_url")
                            if desmob_cam:
                                try:
                                    f_bytes = desmob_cam.getvalue()
                                    f_name = f"{current_project['project_code']}/{item['tag_or_serial']}_desmob.jpg"
                                    supabase.storage.from_("mob-evidences").upload(f_name, f_bytes, file_options={"upsert": "true"})
                                    desmob_photo_url = supabase.storage.from_("mob-evidences").get_public_url(f_name)
                                except Exception as e_up:
                                    st.error(f"Erro no envio da foto de retorno: {e_up}")

                            upd_payload = {
                                "desmob_status": status_ret,
                                "desmob_notes": obs_desmob,
                                "desmob_photo_url": desmob_photo_url,
                                "desmob_by": st.session_state.get("user_email", "operacoes@4sas.com.br"),
                                "desmob_timestamp": datetime.now().isoformat()
                            }
                            supabase.table("mob_packing_list_items").update(upd_payload).eq("id", item["id"]).execute()
                            st.success(f"Item [{item['tag_or_serial']}] atualizado!")
                            st.rerun()

# ------------------------------------------------------------------------------
# TAB 3: RESUMO DA CARGA & EXPORTAÇÃO DE PACKING LIST
# ------------------------------------------------------------------------------
with tab_report:
    st.subheader("📊 Tabela Consolidada do Packing List")
    if not df_items.empty:
        display_cols = ["tag_or_serial", "description", "item_type", "weight_kg", "declared_value_brl", "desmob_status", "mob_notes", "desmob_notes"]
        st.dataframe(df_items[display_cols], use_container_width=True)
        
        # Download rápido em CSV para manifesto de carga
        csv = df_items.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="💾 Baixar Manifest / Packing List (CSV)",
            data=csv,
            file_name=f"packing_list_{current_project['project_code']}.csv",
            mime="text/csv"
        )
    else:
        st.info("Nenhum item cadastrado para esta campanha.")