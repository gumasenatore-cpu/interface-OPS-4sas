import streamlit as st
import pandas as pd
import qrcode
from io import BytesIO
from datetime import date
from supabase import create_client, Client

# Configuração de página
st.set_page_config(page_title="Inventário & Calibrações | 4SAS", page_icon="📦", layout="wide")

# Conexão Supabase
SUPABASE_URL = st.secrets.get("SUPABASE_URL") or st.secrets.get("MAP_SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or st.secrets.get("MAP_SUPABASE_KEY")

@st.cache_resource
def init_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Credenciais do Supabase não encontradas no secrets.toml.")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

st.title("📦 Gestão de Ativos & Calibrações - 4SAS")

# ------------------------------------------------------------------------------
# LEITURA DE QR CODE VIA URL (QUANDO ABERTO PELO CELULAR)
# ------------------------------------------------------------------------------
query_asset_id = st.query_params.get("asset_id")

if query_asset_id:
    st.info(f"🔍 Equipamento identificado via QR Code (ID: {query_asset_id})")
    try:
        res = supabase.table("assets").select("*").eq("id", query_asset_id).execute()
        if res.data:
            item = res.data[0]
            st.success(f"**Equipamento:** [{item.get('asset_tag')}] {item.get('name')}")
            st.write(f"**Status:** {item.get('status')} | **Local:** {item.get('location')}")
        else:
            st.warning("Equipamento não encontrado no banco de dados.")
    except Exception as e:
        st.error(f"Erro ao buscar ativo: {e}")
    st.divider()

# ------------------------------------------------------------------------------
# ABAS DA INTERFACE
# ------------------------------------------------------------------------------
tab_list, tab_cad, tab_maint = st.tabs(["📋 Lista de Ativos", "➕ Novo Ativo", "🔧 Calibrações & Fotos"])

# ABA 1: CONSULTA & QR CODE GENERATOR
with tab_list:
    st.subheader("Ativos Cadastrados")
    try:
        res = supabase.table("assets").select("*").order("asset_tag").execute()
        assets = res.data
        if assets:
            df = pd.DataFrame(assets)
            st.dataframe(df[["asset_tag", "name", "category", "status", "responsible_email"]], use_container_width=True)
            
            st.divider()
            st.subheader("🔲 Gerador de Etiqueta QR Code")
            selected_tag = st.selectbox("Selecione o equipamento para gerar a etiqueta:", df["asset_tag"].tolist())
            if selected_tag:
                selected_asset = df[df["asset_tag"] == selected_tag].iloc[0]
                
                # Link que a câmera do celular vai abrir
                app_url = "https://interface-ops-4sas.streamlit.app"  # Altere para a URL oficial do app se necessário
                qr_link = f"{app_url}/?page=Inventario&asset_id={selected_asset['id']}"
                
                qr = qrcode.QRCode(version=1, box_size=8, border=2)
                qr.add_data(qr_link)
                qr.make(fit=True)
                img = qr.make_image(fill_color="#0f2b48", back_color="white")
                
                buf = BytesIO()
                img.save(buf, format="PNG")
                byte_im = buf.getvalue()
                
                col_qr1, col_qr2 = st.columns([1, 3])
                with col_qr1:
                    st.image(byte_im, caption=f"QR Code: {selected_tag}")
                with col_qr2:
                    st.markdown(f"**Link embutido no QR Code:**\n`{qr_link}`")
                    st.download_button(
                        label="💾 Baixar Etiqueta QR Code (PNG)",
                        data=byte_im,
                        file_name=f"qrcode_{selected_tag}.png",
                        mime="image/png"
                    )
        else:
            st.info("Nenhum equipamento cadastrado ainda.")
    except Exception as e:
        st.error(f"Erro ao carregar lista: {e}")

# ABA 2: NOVO ATIVO COM SUPORTE À CÂMERA DO CELULAR
with tab_cad:
    st.subheader("Cadastrar Novo Equipamento")
    with st.form("form_new_asset"):
        col1, col2 = st.columns(2)
        with col1:
            tag = st.text_input("Tag / Número de Patrimônio (ex: 4SAS-MULT-001)")
            name = st.text_input("Nome do Equipamento (ex: POS MV WaveMaster)")
            category = st.selectbox("Categoria", ["Multifeixe", "Mapeamento GNSS", "Monofeixe", "Sonda/Sonar", "Telecom/Rede", "Outro"])
        with col2:
            status = st.selectbox("Status Operacional", ["Disponível", "Em Operação", "Em Calibração", "Manutenção", "Inoperante"])
            resp_email = st.text_input("E-mail do Responsável", value="operacoes@4sas.com.br")
            serial_no = st.text_input("Número de Série")

        # CÂMERA MOBILE / FOTO DA PLACA
        st.write("📷 **Foto da Placa / Equipamento (Opcional)**")
        img_camera = st.camera_input("Tirar foto pelo celular")
        img_upload = st.file_uploader("Ou carregar imagem do arquivo", type=["jpg", "png", "jpeg"])

        btn_save = st.form_submit_button("Salvar Equipamento")
        
        if btn_save:
            if tag and name:
                try:
                    payload = {
                        "asset_tag": tag,
                        "name": name,
                        "category": category,
                        "status": status,
                        "responsible_email": resp_email,
                        "serial_number": serial_no
                    }
                    supabase.table("assets").insert(payload).execute()
                    st.success(f"Equipamento {name} [{tag}] cadastrado com sucesso!")
                    st.rerun()
                except Exception as err:
                    st.error(f"Erro ao cadastrar: {err}")
            else:
                st.warning("Preencha pelo menos a Tag e o Nome do equipamento.")

# ABA 3: MANUTENÇÕES E CALIBRAÇÕES
with tab_maint:
    st.subheader("Registrar Calibração / Manutenção")
    try:
        res = supabase.table("assets").select("id, asset_tag, name").execute()
        asset_options = {f"[{a['asset_tag']}] {a['name']}": a['id'] for a in res.data} if res.data else {}
        
        if asset_options:
            with st.form("form_maint"):
                selected_asset_label = st.selectbox("Equipamento", list(asset_options.keys()))
                maint_type = st.selectbox("Tipo de Intervenção", ["Calibração", "Manutenção Preventiva", "Manutenção Corretiva", "Inspeção"])
                due_date = st.date_input("Data do Próximo Vencimento", value=date.today() + pd.Timedelta(days=365))
                desc = st.text_area("Observações / Nº do Laudo")
                
                btn_maint = st.form_submit_button("Registrar Calibração")
                if btn_maint:
                    asset_id = asset_options[selected_asset_label]
                    payload_maint = {
                        "asset_id": asset_id,
                        "type": maint_type.lower(),
                        "next_due_date": str(due_date),
                        "description": desc
                    }
                    supabase.table("asset_maintenances").insert(payload_maint).execute()
                    st.success("Registro de calibração salvo com sucesso!")
        else:
            st.info("Cadastre pelo menos um equipamento na aba 'Novo Ativo' antes de registrar calibrações.")
    except Exception as e:
        st.error(f"Erro ao carregar equipamentos: {e}")