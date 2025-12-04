# authentication_module.py

import streamlit as st
from typing import Optional
import jwt
from supabase import create_client, Client
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.oauth2 import OAuth2Token
import asyncio

# ============================================================
# A. CONFIGURACIÓN Y CLIENTES
# ============================================================

# Modo testing
testing_mode = st.secrets.get("testing_mode", False)

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

# Cliente de Google
client_id = st.secrets["client_id"]
client_secret = st.secrets["client_secret"]
redirect_url = (
    st.secrets["redirect_url_test"] if testing_mode else st.secrets["redirect_url"]
)
google_client = GoogleOAuth2(client_id=client_id, client_secret=client_secret)

# ============================================================
# B. FUNCIONES AUXILIARES DE GOOGLE OAUTH
# ============================================================

def _decode_google_token(token: str):
    """Decodifica el token JWT de Google."""
    return jwt.decode(jwt=token, options={"verify_signature": False})

async def _get_authorization_url(client: GoogleOAuth2, redirect_url: str) -> str:
    return await client.get_authorization_url(
        redirect_url,
        scope=["email"],
        extras_params={"access_type": "offline"},
    )

async def _get_access_token(client: GoogleOAuth2, redirect_url: str, code: str) -> OAuth2Token:
    return await client.get_access_token(code, redirect_url)

def get_google_user_email() -> Optional[str]:
    """Obtiene el email del usuario vía Google OAuth"""
    if "google_email" in st.session_state:
        return st.session_state.google_email

    try:
        code = st.query_params.get("code")
        if not code:
            return None
        # Manejo de asyncio seguro en Streamlit
        loop = asyncio.get_event_loop()
        if loop.is_running():
            token = asyncio.run_coroutine_threadsafe(
                _get_access_token(google_client, redirect_url, code), loop
            ).result()
        else:
            token = asyncio.run(_get_access_token(google_client, redirect_url, code))

        # Limpiar query params para evitar loops
        st.experimental_set_query_params()

        user_info = _decode_google_token(token["id_token"])
        st.session_state["google_email"] = user_info["email"]
        return user_info["email"]

    except Exception as e:
        st.error(f"Error al procesar Google OAuth: {e}")
        return None

# ============================================================
# C. FUNCIONES DE SUPABASE / ROLES
# ============================================================

def _get_user_role_from_db(user_id: Optional[str] = None, email: Optional[str] = None):
    """Obtiene rol desde la tabla profiles"""
    st.session_state["user_role"] = "guest"
    st.session_state["user_id"] = None

    if user_id:
        query = supabase.from("profiles").select("role").eq("id", user_id).single()
    elif email:
        query = supabase.from("profiles").select("role").eq("email", email).single()
    else:
        return

    try:
        profile = query.execute()
        if profile.data:
            st.session_state["user_role"] = profile.data.get("role", "guest")
            st.session_state["user_id"] = user_id or None
    except Exception:
        st.session_state["user_role"] = "guest"
        st.session_state["user_id"] = None

# ============================================================
# D. FUNCIONES PRINCIPALES
# ============================================================

def check_session_state_hybrid() -> bool:
    """Verifica sesión activa (Google o Supabase)"""
    if "authenticated" not in st.session_state:
        st.session_state.update({
            "authenticated": False,
            "user_role": "guest",
            "user_id": None,
            "user_email": None
        })

    # Google OAuth
    email_google = get_google_user_email()
    if email_google:
        st.session_state["authenticated"] = True
        st.session_state["user_email"] = email_google
        _get_user_role_from_db(email=email_google)
        return True

    # Supabase
    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        if user:
            st.session_state["authenticated"] = True
            st.session_state["user_email"] = user.email
            if st.session_state.get("user_id") != user.id:
                _get_user_role_from_db(user_id=user.id)
            return True
    except Exception:
        pass

    # No autenticado
    st.session_state.update({
        "authenticated": False,
        "user_role": "guest",
        "user_id": None,
        "user_email": None
    })
    return False

def sign_in_manual(email, password):
    try:
        supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.success("Inicio de sesión exitoso")
        st.experimental_rerun()
    except Exception as e:
        st.error(f"Error al iniciar sesión: {e}")

def sign_up(email, password, name):
    try:
        supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"full_name": name, "role": "supervisor", "email": email}}
        })
        st.success("Registro exitoso. Revisa tu correo.")
    except Exception as e:
        st.error(f"Error al registrar: {e}")

def request_password_reset(email):
    try:
        supabase.auth.reset_password_for_email(email)
        st.success("Correo de recuperación enviado.")
    except Exception as e:
        st.error(f"Error al solicitar recuperación: {e}")

def handle_logout():
    try:
        supabase.auth.sign_out()
    except Exception as e:
        print(f"Error logout Supabase: {e}")
    st.session_state.clear()
    st.experimental_rerun()
