import base64
import os
import streamlit as st

from auth import require_user, render_user_menu


user = require_user()
render_user_menu(user)


def get_image_base64(file_path: str):
    """Busca o arquivo de imagem em diferentes caminhos relativos e converte para Base64."""
    possible_paths = [
        file_path,
        os.path.join(os.path.dirname(__file__), "..", file_path),
        os.path.join(os.path.dirname(__file__), file_path),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            with open(path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode("utf-8")
    return None


def apply_watermark_background():
    encoded_string = get_image_base64("assets/background_4sas.png")

    if encoded_string:
        st.markdown(
            f"""
            <style>
            /* Cor de fundo base do app */
            [data-testid="stAppViewContainer"] {{
                background-color: #0e1117;
                position: relative;
            }}

            /* Marca d'água ampliada e com transparência ajustada */
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

            /* Cabeçalho transparente */
            [data-testid="stHeader"] {{
                background-color: rgba(0, 0, 0, 0);
            }}

            [data-testid="stMainBlockContainer"] {{
                padding-top: 0rem;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.error("Imagem 'assets/background_4sas.png' não encontrada.")


# Aplica a marca d'água ajustada
apply_watermark_background()