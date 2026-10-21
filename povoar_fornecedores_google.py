import os
import sys

import requests
from supabase import create_client


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")
CITY = os.environ.get("FORNECEDORES_CIDADE", "Macaé")
STATE = os.environ.get("FORNECEDORES_UF", "RJ").upper()

SEARCHES = [
    ("loja de materiais elétricos e ferragens", "Elétrica/Ferragens"),
    ("loja de artigos náuticos", "Náutica"),
    ("locação de geradores", "Geradores/Máquinas"),
    ("restaurante e refeições", "Alimentação/Restaurante"),
]


def require_configuration() -> None:
    missing = [
        name
        for name, value in (
            ("SUPABASE_URL", SUPABASE_URL),
            ("SUPABASE_SERVICE_ROLE_KEY", SUPABASE_SERVICE_ROLE_KEY),
            ("GOOGLE_PLACES_API_KEY", GOOGLE_PLACES_API_KEY),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("Defina as variáveis de ambiente: " + ", ".join(missing))


def search_places(term: str) -> list[dict]:
    response = requests.post(
        "https://places.googleapis.com/v1/places:searchText",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.nationalPhoneNumber,places.rating,"
                "places.userRatingCount,places.googleMapsUri"
            ),
        },
        json={
            "textQuery": f"{term} in {CITY}, {STATE}, Brasil",
            "languageCode": "pt-BR",
            "minRating": 4.2,
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json().get("places", [])


def populate() -> int:
    require_configuration()
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    saved = 0

    for term, category in SEARCHES:
        places = search_places(term)
        for place in places:
            rating_count = place.get("userRatingCount", 0)
            place_id = place.get("id")
            if not place_id or rating_count < 15:
                continue

            supabase.table("fornecedores_operacionais").upsert(
                {
                    "google_place_id": place_id,
                    "nome": place.get("displayName", {}).get("text", "Nome indisponível"),
                    "categoria": category,
                    "cidade": CITY,
                    "estado": STATE,
                    "telefone": place.get("nationalPhoneNumber", ""),
                    "endereco_completo": place.get("formattedAddress", ""),
                    "link_google_maps": place.get("googleMapsUri", ""),
                    "nota_google": place.get("rating"),
                    "qtd_avaliacoes": rating_count,
                    "observacoes_4sas": "Importado via Google Places",
                },
                on_conflict="google_place_id",
            ).execute()
            saved += 1

        print(f"{category}: {len(places)} resultados consultados.")

    print(f"Processo concluído para {CITY}/{STATE}; registros importados/atualizados: {saved}.")
    return saved


if __name__ == "__main__":
    try:
        populate()
    except Exception as exc:
        print(f"Falha ao popular fornecedores: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc