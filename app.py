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
from profile import render_profile_page
from employees_crud import render_employee_management_page
from app_reconocimiento import render_recognition_page
from dashboard_rotacion import render_rotacion_dashboard
from survey_control_logic import render_survey_control_panel

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
        st.session_state["current_page"] = "Mi Perfil"

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
            st.rerun()
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
        st.rerun()
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
    st.rerun()        

# ============================================================
# 5. FUNCIONES DE UI (Interfaz de Usuario) - Renderizado
# ============================================================

def render_login_form():
    with st.form("login_form", clear_on_submit=False):
        st.text_input("Correo", key="login_email")
        st.text_input("Contraseña", type="password", key="login_password")
        if st.form_submit_button("Iniciar Sesión"):
            sign_in_manual(st.session_state.login_email, st.session_state.login_password)

def render_signup_form():
    with st.form("signup_form", clear_on_submit=True):
        st.text_input("Nombre completo", key="signup_name")
        st.text_input("Correo", key="signup_email")
        st.text_input("Contraseña (mín. 6 caracteres)", type="password", key="signup_password")
        if st.form_submit_button("Registrarse"):
            if st.session_state.signup_name and st.session_state.signup_email and st.session_state.signup_password:
                sign_up(st.session_state.signup_email, st.session_state.signup_password, st.session_state.signup_name)
            else:
                st.error("Completa todos los campos.")

def render_password_reset_form():
    with st.form("reset_form", clear_on_submit=True):
        st.text_input("Correo registrado", key="reset_email_input")
        if st.form_submit_button("Solicitar Enlace"):
            if st.session_state.reset_email_input:
                request_password_reset(st.session_state.reset_email_input)
            else:
                st.warning("Debes ingresar un correo.")

def render_auth_page():
    """Renderiza la página de autenticación híbrida (Google + Email/Pass)."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        st.markdown("---")

        # --- Botón de Google Rediseñado ---
        if google_client is not None:
            try:
                loop = _ensure_async_loop()
                authorization_url = loop.run_until_complete(
                    _get_authorization_url(client=google_client, redirect_url=redirect_url)
                )
            except Exception as e:
                authorization_url = "#"
                st.error(f"Error al inicializar Google OAuth. Revisa secrets.toml. ({e})")
            
            # Estilo minimalista para el botón de Google (usando HTML/CSS simple)
            st.markdown(
                f"""
                <a href="{authorization_url}" target="_self" style="text-decoration: none;">
                    <button style="
                        width: 100%; 
                        height: 40px; 
                        background-color: white; 
                        color: #333; 
                        border: 1px solid #ccc;
                        border-radius: 0.5rem; 
                        font-weight: 500; 
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 10px;
                        margin-bottom: 20px;">
                        <img src="https://upload.wikimedia.org/wikipedia/commons/4/4a/Logo_2013_Google.png" 
                             style="width: 18px; height: 18px;">
                        Continuar con Google
                    </button>
                </a>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<p style='text-align: center; font-style: italic; color: #666;'>o usa tus credenciales</p>", unsafe_allow_html=True)
        st.markdown("---")

        # Pestañas para los formularios de Supabase
        tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"])
        with tabs[0]:
            st.subheader("Ingreso Manual")
            render_login_form()
        with tabs[1]:
            st.subheader("Crear Cuenta")
            render_signup_form()
        with tabs[2]:
            st.subheader("Restablecer")
            render_password_reset_form()

def render_sidebar():
    """Renderiza la barra lateral con información de la sesión y navegación."""
    
    # Acceder a current_page de forma segura con .get() y un valor por defecto.
    current_page = st.session_state.get("current_page", "Mi Perfil") 
    
    with st.sidebar:
        # Mini perfil en la barra lateral
        col1, col2 = st.columns([1, 3])
        with col1:
            avatar_url = st.session_state.get("avatar_url")
            # Usar un placeholder si no hay URL válida
            if not avatar_url:
                avatar_url = "https://placehold.co/100x100/A0A0A0/ffffff?text=U"
            
            # CSS para hacer la imagen redonda
            st.markdown(f"""
                <style>
                    .sidebar-img {{
                        border-radius: 50%;
                        width: 60px;
                        height: 60px;
                        object-fit: cover;
                        border: 2px solid #007ACC;
                    }}
                </style>
                <img src="{avatar_url}" class="sidebar-img">
            """, unsafe_allow_html=True)

        with col2:
            # Mostrar el nombre del usuario autenticado
            st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
            st.caption(f"Rol: **{st.session_state.get('user_role', 'guest').capitalize()}**")

        st.markdown("---")
        
        # Menú de Navegación
        st.markdown("### Navegación")
        
        # Botones de navegación (FIX: Usando on_click para estabilidad)
        for page in PAGES:
            # Asignar iconos
            icon_map = {
                "Mi Perfil": "👤",
                "Dashboard": "📊",
                "Gestión de Empleados": "👥",
                "Predicción desde Archivo": "📁",
                "Predicción Manual": "✏️",
                "Reconocimiento": "⭐"
            }
            icon = icon_map.get(page, "➡️")
            
            # Resaltar el botón de la página actual, usando la variable segura current_page
            button_style = "primary" if current_page == page else "secondary"
            
            # Uso de on_click para manejar la navegación de forma segura
            st.button(
                f"{icon} {page}", 
                key=f"nav_{page}", 
                use_container_width=True, 
                type=button_style,
                on_click=set_page, # Función callback
                args=(page,)      # Argumento de la función callback
            )
            
        st.markdown("---")
        # Sección de la cuenta (Cerrar Sesión)
        st.markdown(f"**Cuenta:** `{st.session_state.get('user_email', 'Desconocido')}`")
        
        if st.button("Cerrar Sesión", use_container_width=True):
            handle_logout()

def render_placeholder_page(page_title):
    """Función de marcador de posición para páginas futuras (sin la gestión de empleados)."""
    st.title(page_title)
    st.info(f"Esta es la página de **{page_title}**. El contenido detallado se desarrollará en el siguiente paso.")
    st.markdown("---")
    if page_title == "Predicción desde Archivo 📁":
        st.warning("Se incluirá una sección para subir un archivo CSV y obtener predicciones de deserción masiva.")
    elif page_title == "Predicción Manual ✏️":
        st.warning("Se mostrará un formulario para ingresar manualmente las características de un empleado y obtener la probabilidad de deserción.")
    elif page_title == "Reconocimiento ⭐":
        st.warning("Esta sección será para gestionar y visualizar reconocimientos o premios a empleados.")

# ============================================================
# 6. CONTROL DE FLUJO PRINCIPAL
# ============================================================

# 1. Se ejecuta al inicio para determinar el estado de la sesión
session_is_active = check_session_state_hybrid()



# 2. Control de Acceso
if session_is_active:
    render_sidebar()
    # 3. Renderizar la página actual
    page_map = {
        "Mi Perfil": lambda: render_profile_page(supabase, request_password_reset),
        "Dashboard": render_rotacion_dashboard,
        "Gestión de Empleados":lambda: render_employee_management_page() , # Función CRUD dedicada
        "Predicción desde Archivo": lambda: render_placeholder_page("Predicción desde Archivo 📁"),
        "Predicción Manual": lambda: render_placeholder_page("Predicción Manual ✏️"),
        "Reconocimiento": render_recognition_page
    }
    
    # Ejecutar la función de renderizado para la página actual
    page_map.get(st.session_state.get("current_page", "Mi Perfil"), render_profile_page)()

else:
    # Si NO está autenticado
    render_auth_page()                    

