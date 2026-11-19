import base64
import os
import streamlit as st

from auth import require_user, sign_out

user = require_user()


def get_image_base64(file_path: str) -> str | None:
    """Busca o arquivo de imagem em caminhos relativos seguros e converte para Base64."""
    possible_paths = [
        file_path,
        os.path.join(os.path.dirname(__file__), "..", file_path),
        os.path.join(os.path.dirname(__file__), file_path),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "rb") as img_file:
                    return base64.b64encode(img_file.read()).decode("utf-8")
            except OSError:
                continue
    return None


def apply_watermark_background() -> None:
    encoded_string = get_image_base64("assets/background_4sas.png")

    if encoded_string:
        st.markdown(
            f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background-color: #0e1117;
                position: relative;
            }}

            [data-testid="stAppViewContainer"]::before {{
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-image: url("data:image/png;base64,{encoded_string}");
                background-size: min(90vw, 825px);
                background-position: center center;
                background-repeat: no-repeat;
                opacity: 0.15;
                pointer-events: none;
                z-index: 0;
            }}

            [data-testid="stHeader"] {{
                background-color: rgba(0, 0, 0, 0);
            }}

            div[data-testid="stVerticalBlockBorderWrapper"] {{
                background-color: rgba(17, 17, 17, 0.78);
                backdrop-filter: blur(4px);
            }}

            div[data-testid="stVerticalBlockBorderWrapper"] p {{
                color: #b0b8c1;
                font-size: 0.9rem;
                line-height: 1.4;
                min-height: 3.6rem;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )


apply_watermark_background()

col_titulo, col_user = st.columns([4, 1], vertical_alignment="center")
with col_titulo:
    st.title("Portal de Operações")
    st.caption("Selecione um módulo abaixo ou utilize o menu superior para navegar.")

with col_user:
    st.caption(f"Sessão: **{user['email']}**")
    if st.button("Sair do portal", key="home_sign_out", use_container_width=True):
        sign_out()
        st.rerun()

st.divider()

pages = st.session_state.get("portal_pages", {})

modulos = [
    {
        "key": "boletim",
        "icone": "🌊",
        "titulo": "1 - Boletim",
        "descricao": "Consulta de condições meteo-oceanográficas, vento, ondas e janelas operacionais.",
    },
    {
        "key": "apr",
        "icone": "⚠️",
        "titulo": "2 - APR",
        "descricao": "Elaboração e consulta de Análise Preliminar de Risco para atividades costeiras e offshore.",
    },
    {
        "key": "fornecedores",
        "icone": "🏢",
        "titulo": "3 - Fornecedores",
        "descricao": "Busca e cadastro de apoio logístico local, embarcações, suprimentos e contatos de campo.",
    },
    {
        "key": "linhas",
        "icone": "🧭",
        "titulo": "4 - Planejador de Linhas",
        "descricao": "Geração, visualização e exportação de linhas de levantamento hidrográfico e geofísico.",
    },
    {
        "key": "inventario",
        "icone": "📦",
        "titulo": "5 - Inventário & Manutenção",
        "descricao": "Controle de sensores acústicos, receptores GNSS, cabos e equipamentos de campanha.",
    },
    {
        "key": "checklist",
        "icone": "📋",
        "titulo": "6 - Checklist Mob/Demob",
        "descricao": "Conferência operacional de mobilização e desmobilização de equipamentos e embarcação.",
    },
]

NUM_COLUNAS = 3

for i in range(0, len(modulos), NUM_COLUNAS):
    linha_modulos = modulos[i : i + NUM_COLUNAS]
    cols = st.columns(NUM_COLUNAS, gap="medium")

    for col, mod in zip(cols, linha_modulos):
        with col:
            with st.container(border=True, height=195):
                st.markdown(f"#### {mod['icone']} {mod['titulo']}")
                st.write(mod["descricao"])

                target_page = pages.get(mod["key"])
                if st.button(
                    "Acessar Módulo",
                    key=f"btn_nav_{mod['key']}",
                    use_container_width=True,
                    type="primary",
                ):
                    if target_page:
                        st.switch_page(target_page)
                    else:
                        st.error("Página não mapeada no roteador principal (app.py).")