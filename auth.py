# auth.py

import streamlit as st
import asyncio
from typing import Optional
import jwt
from supabase import create_client, Client
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.oauth2 import OAuth2Token

# ============================================================
# A. CONFIGURACIÓN Y CLIENTES
# ============================================================

# Inicialización de clientes de Supabase y Google
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
    """Genera la URL de redirección a Google."""
    return await client.get_authorization_url(
        redirect_url,
        scope=["email"],
        extras_params={"access_type": "offline"},
    )

async def _get_access_token(client: GoogleOAuth2, redirect_url: str, code: str) -> OAuth2Token:
    """Obtiene el token de acceso usando el código de la URL."""
    return await client.get_access_token(code, redirect_url)

def get_google_user_email() -> Optional[str]:
    """Maneja la respuesta de Google y obtiene el email del usuario."""
    if "google_email" in st.session_state:
        return st.session_state.google_email

    try:
        code = st.query_params["code"]
        # Obtener token
        token = asyncio.run(_get_access_token(client=google_client, redirect_url=redirect_url, code=code))
        # Limpiar query params inmediatamente para evitar loops
        st.query_params.clear() 
        
        user_info = _decode_google_token(token=token["id_token"])
        st.session_state["google_email"] = user_info["email"]
        return user_info["email"]

    except KeyError:
        return None
    except Exception as e:
        st.error(f"Error al procesar Google OAuth: {e}")
        return None

# ============================================================
# C. LÓGICA DE ROLES DE SUPABASE (Funciones de Soporte)
# ============================================================

def _get_user_role_from_db(user_id: Optional[str] = None, email: Optional[str] = None):
    """Lee el rol del usuario de la tabla 'profiles' de Supabase."""
    
    if user_id:
        query = supabase.from("profiles").select("role").eq("id", user_id).single()
    elif email:
        # Esto es para usuarios de Google que aún no han sido sincronizados o no tienen el user_id
        query = supabase.from("profiles").select("role").eq("email", email).single()
    else:
        st.session_state["user_role"] = "guest"
        st.session_state["user_id"] = None
        return

    try:
        profile = query.execute()
        st.session_state["user_role"] = profile.data.get("role", "guest")
        st.session_state["user_id"] = user_id if user_id else None
    except Exception:
        # Usuario no encontrado en la tabla 'profiles' (ej. nuevo usuario de Google)
        st.session_state["user_role"] = "guest"
        st.session_state["user_id"] = None

# ============================================================
# D. FUNCIONES PRINCIPALES DE AUTENTICACIÓN
# ============================================================

def check_session_state_hybrid():
    """Verifica si la sesión está activa usando Google o Supabase, y establece el estado."""
    
    # 1. Limpieza inicial de estado de seguridad
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["user_role"] = "guest"
        st.session_state["user_id"] = None
        st.session_state["user_email"] = None

    # --- Intento de Autenticación Híbrida ---
    
    # A. Intento de Google OAuth
    email_google = get_google_user_email() 
    if email_google:
        st.session_state["authenticated"] = True
        st.session_state["user_email"] = email_google
        # Mapea el email de Google a tu base de datos de perfiles (obtiene el rol)
        _get_user_role_from_db(email=email_google) 
        return True

    # B. Intento de Supabase (Email/Contraseña)
    try:
        user_response = supabase.auth.get_user()
        user = user_response.user
        
        if user:
            # Sesión activa con Supabase. Lee el rol y el email.
            st.session_state["authenticated"] = True
            st.session_state["user_email"] = user.email
            
            # Lee el rol solo si no está cargado o si el ID cambió
            if st.session_state.get("user_id") != user.id:
                _get_user_role_from_db(user_id=user.id)
            return True
        
    except Exception:
        pass 

    # C. No Autenticado
    st.session_state["authenticated"] = False
    st.session_state["user_role"] = "guest"
    st.session_state["user_id"] = None
    st.session_state["user_email"] = None
    return False

# Funciones de acción
def sign_in_manual(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.success("Inicio de sesión exitoso. Recargando...")
        st.rerun() # Forzar la recarga para que check_session_state_hybrid capture el estado
    except Exception as e:
        st.error(f"Error al iniciar sesión: {e}")

def sign_up(email, password, name):
    try:
        # Se asume que Supabase tiene un trigger para crear el perfil
        supabase.auth.sign_up({"email": email, "password": password,
                               "options": {"data": {"full_name": name, "role": "supervisor", "email": email}}})
        st.success("Registro exitoso. Revisa tu correo para verificar tu cuenta.")
    except Exception as e:
        st.error(f"Error al registrar: {e}")

def request_password_reset(email):
    try:
        supabase.auth.reset_password_for_email(email)
        st.success("Se ha enviado un correo electrónico para restablecer tu contraseña.")
    except Exception as e:
        st.error(f"Error al solicitar recuperación: {e}")

def handle_logout():
    try:
        supabase.auth.sign_out()
    except Exception as e:
        print(f"Error al cerrar sesión de Supabase: {e}")

    # Limpia el estado de Streamlit (incluyendo la variable de Google)
    if "google_email" in st.session_state:
        del st.session_state["google_email"]

    st.rerun() 

# ============================================================
# E. FUNCIONES DE UI Y BOTONES
# ============================================================

def render_login_form():
    st.subheader("Acceso con Email")
    email = st.text_input("Correo", key="login_email")
    password = st.text_input("Contraseña", type="password", key="login_password")
    if st.button("Iniciar Sesión", key="login_btn"):
        sign_in_manual(email, password)

def render_signup_form():
    st.subheader("Crear Cuenta")
    name = st.text_input("Nombre completo", key="signup_name")
    email = st.text_input("Correo", key="signup_email")
    password = st.text_input("Contraseña", type="password", key="signup_password")
    if st.button("Registrarse", key="signup_btn"):
        if name and email and password:
            sign_up(email, password, name)
        else:
            st.error("Completa todos los campos")

def render_password_reset_form():
    st.subheader("Recuperar Contraseña")
    st.info("Ingresa tu correo. Recibirás un enlace por email para cambiar tu contraseña.")
    email = st.text_input("Correo registrado", key="reset_email")
    if st.button("Solicitar Enlace", key="reset_btn"):
        if email:
            request_password_reset(email)
        else:
            st.warning("Debes ingresar un correo.")

def render_auth_page():
    # Botón de Google siempre visible en la parte superior para Social Login
    authorization_url = asyncio.run(_get_authorization_url(client=google_client, redirect_url=redirect_url))
    
    st.markdown("## Elegir Método de Acceso")
    
    # Estiliza el botón de Google para que sea prominente
    st.markdown(
        f"""
        <a href="{authorization_url}" target="_self" style="text-decoration: none;">
            <div style="
                display: inline-flex; justify-content: center; align-items: center;
                font-weight: 600; padding: 0.5rem 1rem; border-radius: 0.5rem;
                background-color: #4285F4; color: white; border: none;
                width: 100%; text-align: center; margin-bottom: 20px;">
                <img src="https://upload.wikimedia.org/wikipedia/commons/4/4a/Logo_2013_Google.png" style="width: 20px; margin-right: 10px; background-color: white; border-radius: 50%;">
                Continuar con Google
            </div>
        </a>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("### O usar Email y Contraseña")

    # Pestañas para los formularios de Supabase
    tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"]) 
    with tabs[0]:
        render_login_form()
    with tabs[1]:
        render_signup_form()
    with tabs[2]:
        render_password_reset_form()