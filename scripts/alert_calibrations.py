import os
import toml
import requests
import resend
from datetime import date, timedelta

# ==============================================================================
# AUDITORIA E CARREGAMENTO DE CREDENCIAIS
# ==============================================================================
sec = {}
secrets_path = os.path.join(".streamlit", "secrets.toml")

if os.path.exists(secrets_path):
    try:
        sec = toml.load(secrets_path)
    except Exception as e:
        print(f"⚠️ Erro ao ler {secrets_path}: {e}")

# Busca credenciais no secrets.toml ou nas variáveis do sistema/GitHub Actions
SUPABASE_URL = sec.get("SUPABASE_URL") or sec.get("MAP_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
SUPABASE_KEY = sec.get("SUPABASE_KEY") or sec.get("MAP_SUPABASE_KEY") or sec.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
RESEND_API_KEY = sec.get("RESEND_API_KEY") or os.environ.get("RESEND_API_KEY")

if not (SUPABASE_URL and SUPABASE_KEY and RESEND_API_KEY):
    print("❌ Erro: Credenciais incompletas no secrets.toml ou nas variáveis de ambiente.")
    print(f"   - SUPABASE_URL: {'OK' if SUPABASE_URL else 'FALTANDO'}")
    print(f"   - SUPABASE_KEY: {'OK' if SUPABASE_KEY else 'FALTANDO'}")
    print(f"   - RESEND_API_KEY: {'OK' if RESEND_API_KEY else 'FALTANDO'}")
    exit(1)

print(f"🔗 Conectando ao Supabase na URL: {SUPABASE_URL}")

resend.api_key = RESEND_API_KEY

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Accept-Profile": "public",
    "Content-Profile": "public"
}

def run_calibration_alerts():
    today = date.today()
    limit_date = today + timedelta(days=30)

    print(f"🔎 Verificando calibrações a vencer entre {today} e {limit_date}...")

    try:
        base_url = SUPABASE_URL.rstrip('/')
        url_maint = f"{base_url}/rest/v1/asset_maintenances?select=asset_id,type,description,next_due_date"
        
        res_maint = requests.get(url_maint, headers=HEADERS)
        
        if res_maint.status_code != 200:
            print(f"❌ Erro na consulta ao Supabase (HTTP {res_maint.status_code}): {res_maint.text}")
            return

        all_maintenances = res_maint.json()

        if not all_maintenances:
            print("✅ Nenhuma manutenção ou calibração cadastrada no banco.")
            return

        maintenances = []
        for m in all_maintenances:
            due_str = m.get("next_due_date")
            if due_str:
                try:
                    due_d = date.fromisoformat(str(due_str).split("T")[0])
                    if today <= due_d <= limit_date:
                        maintenances.append(m)
                except ValueError:
                    continue

        if not maintenances:
            print("✅ Nenhuma calibração a vencer nos próximos 30 dias.")
            return

        # Coleta os IDs dos ativos envolvidos
        asset_ids = list(set([m["asset_id"] for m in maintenances if m.get("asset_id")]))
        assets_dict = {}
        
        if asset_ids:
            ids_str = ",".join(f'"{aid}"' for aid in asset_ids)
            url_assets = f"{base_url}/rest/v1/assets?id=in.({ids_str})&select=id,asset_tag,name,responsible_email"
            res_assets = requests.get(url_assets, headers=HEADERS)
            
            if res_assets.status_code == 200:
                assets_dict = {a["id"]: a for a in res_assets.json()}

        # Agrupa os alertas por e-mail de responsável
        alerts_by_email = {}
        for m in maintenances:
            asset = assets_dict.get(m.get("asset_id"), {})
            email = asset.get("responsible_email") or "operacoes@4sas.com.br"
            
            if email not in alerts_by_email:
                alerts_by_email[email] = []
                
            alerts_by_email[email].append({
                "tag": asset.get("asset_tag", "N/A"),
                "name": asset.get("name", "Equipamento não especificado"),
                "due_date": m.get("next_due_date"),
                "type": str(m.get("type", "Calibração")).capitalize()
            })

        for email, items in alerts_by_email.items():
            html_list = "".join([
                f"<li><b>[{item['tag']}] {item['name']}</b> - Vencimento da {item['type']}: <span style='color: #d9534f; font-weight: bold;'>{item['due_date']}</span></li>"
                for item in items
            ])

            html_content = f"""
            <div style="font-family: Arial, sans-serif; color: #333; max-width: 600px;">
                <h2 style="color: #0f2b48;">⚠️ Alerta de Calibração / Manutenção - 4SAS Offshore</h2>
                <p>Olá,</p>
                <p>Os seguintes ativos sob sua responsabilidade possuem vencimento de calibração/manutenção agendado para os próximos 30 dias:</p>
                <ul style="background-color: #f4f6f8; padding: 15px 25px; border-radius: 5px; line-height: 1.6;">
                    {html_list}
                </ul>
                <p>Por favor, providencie o agendamento da intervenção e registre o novo laudo no <b>Portal 4SAS</b>.</p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;" />
                <p style="font-size: 12px; color: #777;">Este é um e-mail automático gerado pelo sistema de gestão de ativos da 4SAS.</p>
            </div>
            """

            try:
                sender_email = sec.get("SENDER_EMAIL") or os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
                response = resend.Emails.send({
                    "from": f"4SAS Assets <{sender_email}>",
                    "to": [email],
                    "subject": f"⚠️ [4SAS] {len(items)} Equipamento(s) com Calibração/Manutenção a Vencer",
                    "html": html_content
                })
                print(f"📧 E-mail enviado com sucesso para {email}. ID: {response.get('id')}")
            except Exception as mail_err:
                print(f"❌ Erro ao enviar e-mail para {email}: {mail_err}")

    except Exception as err:
        print(f"❌ Erro de execução: {err}")

if __name__ == "__main__":
    print("🚀 Iniciando verificação de alertas de calibração...")
    run_calibration_alerts()
    print("🏁 Verificação concluída!")