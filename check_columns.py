import toml
from supabase import create_client

sec = toml.load(".streamlit/secrets.toml")
supabase = create_client(sec.get("SUPABASE_URL"), sec.get("SUPABASE_KEY"))

print("--- 1. Testando busca irrestrita em asset_maintenances ---")
try:
    res = supabase.table("asset_maintenances").select("*").limit(1).execute()
    print("✅ Sucesso em asset_maintenances!")
    if res.data:
        print("Campos encontrados na tabela asset_maintenances:", list(res.data[0].keys()))
    else:
        print("Tabela asset_maintenances está vazia, mas a estrutura existe.")
except Exception as e:
    print(f"❌ Erro em asset_maintenances: {e}")

print("\n--- 2. Testando busca irrestrita em assets ---")
try:
    res_a = supabase.table("assets").select("*").limit(1).execute()
    print("✅ Sucesso em assets!")
    if res_a.data:
        print("Campos encontrados na tabela assets:", list(res_a.data[0].keys()))
    else:
        print("Tabela assets está vazia, mas a estrutura existe.")
except Exception as e:
    print(f"❌ Erro em assets: {e}")