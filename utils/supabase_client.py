import uuid
from supabase import create_client, Client
import streamlit as st

@st.cache_resource
def init_connection() -> Client:
    # Agora o mapa usa a sua própria chave, sem interferir no login!
    url = st.secrets["MAP_SUPABASE_URL"]
    key = st.secrets["MAP_SUPABASE_KEY"]
    
    return create_client(url, key)

def upload_image_to_storage(file_bytes: bytes, file_name: str, bucket_name: str = "survey_images") -> str:
    supabase = init_connection()
    
    try:
        # Hash único para evitar erro 409
        unique_file_name = f"{uuid.uuid4().hex}_{file_name}"
        
        res = supabase.storage.from_(bucket_name).upload(
            file=file_bytes,
            path=unique_file_name,
            file_options={"content-type": "image/tiff", "x-upsert": "true"}
        )
        
        return supabase.storage.from_(bucket_name).get_public_url(unique_file_name)
        
    except Exception as e:
        st.error(f"Erro ao fazer upload no Supabase: {str(e)}")
        return None