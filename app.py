import streamlit as st
from typing import Optional
import jwt
from supabase import create_client, Client
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.oauth2 import OAuth2Token
import asyncio
import httpx
import datetime
import pandas as pd

# ============================================================
# 0. CONFIGURACIÓN E INICIALIZACIÓN
# ============================================================

st.set_page_config(
    page_title="App Deserción Laboral",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modo testing (para usar localhost o la URL de despliegue)
testing_mode = st.secrets.get("testing_mode", False)

@st.cache_resource
def get_supabase() -> Client:
    """Inicializa y cachea el cliente de Supabase."""
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("ERROR: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml. La autenticación fallará.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

# Cliente de Google OAuth
try:
    client_id = st.secrets["client_id"]
    client_secret = st.secrets["client_secret"]
    redirect_url = (
        st.secrets["redirect_url_test"] if testing_mode else st.secrets["redirect_url"]
    )
    google_client = GoogleOAuth2(client_id=client_id, client_secret=client_secret)
except KeyError:
    # Este bloque maneja si las secrets de Google no están configuradas
    st.warning("Advertencia: Faltan secretos de Google (client_id, etc.). Google OAuth no funcionará.")
    google_client = None

# Definición de todas las páginas disponibles
PAGES = [
    "Mi Perfil",
    "Dashboard", 
    "Gestión de Empleados", 
    "Predicción desde Archivo", 
    "Predicción Manual",
    "Reconocimiento" 
]

# ============================================================
# 1. FUNCIONES AUXILIARES DE GOOGLE OAUTH
# ============================================================

def _decode_google_token(token: str):
    """Decodifica el token JWT de Google sin verificar firma."""
    return jwt.decode(jwt=token, options={"verify_signature": False})

async def _get_authorization_url(client: GoogleOAuth2, redirect_url: str) -> str:
    """Genera la URL para iniciar el flujo OAuth de Google."""
    return await client.get_authorization_url(
        redirect_url,
        scope=["email"],
        extras_params={"access_type": "offline"},
    )

async def _get_access_token(client: GoogleOAuth2, redirect_url: str, code: str) -> OAuth2Token:
    """Obtiene el token de acceso usando el código de la URL."""
    return await client.get_access_token(code, redirect_url)

def _ensure_async_loop():
    """Asegura que haya un loop de asyncio en ejecución o crea uno nuevo."""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

def get_google_user_email() -> Optional[str]:
    """Maneja la respuesta de Google y obtiene el email del usuario."""
    if "google_email" in st.session_state:
        return st.session_state.google_email

    if google_client is None:
        return None

    try:
        code = st.query_params.get("code")
        if not code:
            return None

        loop = _ensure_async_loop()
        
        if loop.is_running():
            token = asyncio.run_coroutine_threadsafe(
                _get_access_token(google_client, redirect_url, code), loop
            ).result()
        else:
            token = loop.run_until_complete(_get_access_token(google_client, redirect_url, code))

        st.experimental_set_query_params()
        st.session_state["google_email"] = _decode_google_token(token["id_token"])["email"]
        return st.session_state["google_email"]

    except Exception:
        return None

# ============================================================
# 2. FUNCIONES DE SUPABASE / ROLES (Autorización y Perfil)
# ============================================================

def _fetch_user_profile(user_id: str):
    """Obtiene el perfil completo (nombre, fecha de nacimiento y URL del avatar) del usuario."""
    # Inicialización de fallback local
    st.session_state["user_role"] = "guest"
    st.session_state["full_name"] = "Usuario"
    st.session_state["date_of_birth"] = None
    st.session_state["avatar_url"] = None 
    st.session_state["user_id"] = None

    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        
        if response.data:
            profile = response.data[0]
            st.session_state["user_role"] = profile.get("role", "guest")
            st.session_state["full_name"] = profile.get("full_name", "Usuario") 
            st.session_state["user_id"] = user_id
            st.session_state["avatar_url"] = profile.get("avatar_url", None)
            
            # Manejar la fecha de nacimiento: convertir la cadena de Supabase a objeto date
            dob_str = profile.get("date_of_birth")
            if dob_str:
                st.session_state["date_of_birth"] = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date()
            else:
                 st.session_state["date_of_birth"] = None
            
            # Fallback si el nombre está vacío
            if not st.session_state["full_name"] or st.session_state["full_name"] == "Usuario":
                 st.session_state["full_name"] = st.session_state.get("user_email", "Usuario").split('@')[0]
        else:
            st.session_state["full_name"] = st.session_state.get("user_email", "Usuario").split('@')[0]
            st.session_state["user_id"] = user_id
            
    except Exception as e:
        st.session_state["user_id"] = None

# ============================================================
# 3. FUNCIONES PRINCIPALES DE AUTENTICACIÓN HÍBRIDA
# ============================================================

def set_page(page_name):
    """
    Callback para establecer la nueva página. 
    Se elimina st.experimental_rerun() para evitar conflictos de ciclo de vida.
    Streamlit detectará el cambio en st.session_state y hará el rerun automáticamente.
    """
    st.session_state.current_page = page_name
    # st.experimental_rerun() <-- LÍNEA ELIMINADA para estabilidad

def check_session_state_hybrid() -> bool:
    """Verifica sesión activa e inicializa el perfil si es necesario."""
    
    # 0. CRÍTICO: Garantizar que la variable de navegación (current_page) siempre exista.
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Dashboard"

    # Inicializar el resto del estado de sesión si falta el flag de autenticación.
    if "authenticated" not in st.session_state:
        st.session_state.update({
            "authenticated": False,
            "user_role": "guest",
            "user_id": None,
            "user_email": None,
            "full_name": "Usuario",
            "date_of_birth": None,
            "avatar_url": None,
            # 'current_page' ya no se inicializa aquí
        })

    # 1. Manejo de tokens de Supabase desde la URL (Verificación/Reset)
    query_params = st.query_params
    access_token = query_params.get("access_token")
    refresh_token = query_params.get("refresh_token")
    
    if access_token and refresh_token:
        try:
            supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
            st.experimental_set_query_params()
            st.experimental_rerun()
            return True
        except Exception:
            pass

    # 2. Intento de Google OAuth
    email_google = get_google_user_email()
    if email_google:
        user_response = supabase.auth.get_user()
        user_id = user_response.user.id if user_response and user_response.user else None
        
        st.session_state["authenticated"] = True
        st.session_state["user_email"] = email_google
        if user_id and st.session_state.get("user_id") != user_id:
             _fetch_user_profile(user_id=user_id)
        return True

    # 3. Intento de Supabase (Email/Contraseña o Sesión existente)
    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        if user:
            st.session_state["authenticated"] = True
            st.session_state["user_email"] = user.email
            if st.session_state.get("user_id") != user.id:
                _fetch_user_profile(user_id=user.id)
            return True
    except Exception:
        pass

    # 4. No autenticado (Fall-back de seguridad, garantiza que todos los valores son Nones)
    st.session_state.update({
        "authenticated": False,
        "user_role": "guest",
        "user_id": None,
        "user_email": None,
        "full_name": "Usuario",
        "date_of_birth": None,
        "avatar_url": None,
        # 'current_page' no se toca aquí para mantener el estado de navegación si no hay logout
    })
    return False

def sign_in_manual(email, password):
    """Inicia sesión con Email/Contraseña."""
    try:
        supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.success("Inicio de sesión exitoso. Recargando...")
        st.experimental_rerun()
    except Exception as e:
        st.error(f"Error al iniciar sesión: {e}")

def sign_up(email, password, name):
    """
    Registra un nuevo usuario en Supabase y crea su perfil inicial.
    """
    try:
        # 1. Registrar usuario
        user_info = supabase.auth.sign_up({
            "email": email,
            "password": password,
        })
        
        # 2. Crear entrada en la tabla 'profiles' para el nombre y rol
        user_id = user_info.user.id
        supabase.table("profiles").insert({
            "id": user_id, 
            "email": email,
            "full_name": name, 
            "role": "supervisor",
            "date_of_birth": None,
            "avatar_url": None
        }).execute()

        st.success("Registro exitoso. Revisa tu correo electrónico para verificar tu cuenta.")
        st.info("⚠️ Si no recibes el correo, verifica la configuración SMTP en el panel de Supabase.")
    except Exception as e:
        st.error(f"Error al registrar: {e}")

def request_password_reset(email):
    """
    Solicita un enlace para restablecer la contraseña.
    """
    try:
        supabase.auth.reset_password_for_email(email)
        st.success("Correo de recuperación enviado.")
        st.info("⚠️ Si no recibes el correo, verifica la configuración SMTP en el panel de Supabase.")
    except Exception as e:
        st.error(f"Error al solicitar recuperación: {e}")

def handle_logout():
    """Cierra la sesión de Supabase y limpia el estado local (incluyendo Google)."""
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    st.experimental_rerun()        



