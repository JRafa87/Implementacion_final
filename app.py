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
# Importaciones de módulos locales (deben existir en tu proyecto)
# Asegúrate de que estos archivos existan y contengan las funciones de renderizado
from profile import render_profile_page
from employees_crud import render_employee_management_page
from app_reconocimiento import render_recognition_page
from dashboard_rotacion import render_rotacion_dashboard
from survey_control_logic import render_survey_control_panel
from prediccion_manual_module import render_manual_prediction_tab
from attrition_predictor import render_predictor_page
from encuestas_historial import historial_encuestas_module


# ============================================================
# 0. CONFIGURACIÓN E INICIALIZACIÓN
# ============================================================

st.set_page_config(
    page_title="App Deserción Laboral",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# Cliente de Google OAuth y variables
try:
    client_id = st.secrets["client_id"]
    client_secret = st.secrets["client_secret"]
    REDIRECT_URL = st.secrets["REDIRECT_URL"] # Usamos esta como la URL de callback
    google_client = GoogleOAuth2(client_id, client_secret)
except KeyError:
    google_client = None
    REDIRECT_URL = None
    # st.warning("Google OAuth no configurado en secrets.toml.")

# Definición de todas las páginas disponibles
PAGES = [
    "Mi Perfil",
    "Dashboard", 
    "Gestión de Empleados", 
    "Predicción desde Archivo", 
    "Predicción Manual",
    "Reconocimiento" ,
    "Historial de Encuesta" 
]

# ============================================================
# 1. FUNCIONES AUXILIARES DE GOOGLE OAUTH SIMPLIFICADAS
# ============================================================

def _decode_google_token(token: str):
    """Decodifica el JWT sin verificar la firma (solo para Streamlit/Testing)"""
    return jwt.decode(token, options={"verify_signature": False})

def _ensure_loop():
    """Asegura que haya un loop de asyncio activo."""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

async def _auth_url(client: GoogleOAuth2, redirect_url: str):
    """Genera la URL de autorización de Google."""
    return await client.get_authorization_url(
        redirect_url,
        scope=["email", "profile"]
    )

async def _access_token(client: GoogleOAuth2, redirect_url: str, code: str):
    """Intercambia el código por el token de acceso."""
    return await client.get_access_token(code, redirect_url)

def handle_google_login_flow() -> bool:
    """
    Gestiona el flujo de autenticación de Google OAuth, desde el callback hasta
    la sincronización con Supabase.
    Retorna True si la sesión se estableció exitosamente, False si no.
    """
    if not google_client or not REDIRECT_URL:
        return False
        
    code = st.query_params.get("code")
    if not code:
        # No hay código, no hay flujo de Google en curso.
        return False
    
    # 1. Procesar el código y obtener el token de Google
    try:
        loop = _ensure_loop()
        token = loop.run_until_complete(_access_token(google_client, REDIRECT_URL, code))

        st.experimental_set_query_params() # Limpia la URL (CRÍTICO)

        if not token or "id_token" not in token:
            return False
            
        decoded_user = _decode_google_token(token["id_token"])
        
        email = decoded_user.get("email")
        name = decoded_user.get("name")
        avatar = decoded_user.get("picture")

        # 2. Sincronizar con Supabase (Reutilizando la lógica de la función _fetch_and_set_user_profile/sync)
        profile_response = (
            supabase.table("profiles")
            .select("*")
            .eq("email", email)
            .limit(1)
            .execute()
        )
        
        user_id = None
        
        # Sincronización: Actualizar o Crear Perfil
        if profile_response.data:
            # Existe: Actualizar y obtener ID
            user_id = profile_response.data[0]["id"]
            supabase.table("profiles").update({
                "full_name": name,
                "avatar_url": avatar
            }).eq("email", email).execute()
        else:
            # No existe: Crear un nuevo perfil de Supabase (y Supabase Auth si no existe)
            
            # --- Aquí podrías necesitar registrar al usuario en Supabase Auth ---
            # Si quieres que el usuario de Google también tenga una entrada en Supabase Auth
            # Esto depende de cómo tengas configurada la autenticación en Supabase (si usas solo OAuth o Auth + OAuth)
            # Para la mayoría, basta con que Supabase Auth lo maneje automáticamente si tienes Google provider activo.
            
            # Asumimos que la autenticación ya fue manejada por Google y necesitamos la fila en 'profiles'
            new_profile = supabase.table("profiles").insert({
                "email": email,
                "full_name": name,
                "avatar_url": avatar,
                "role": "guest" # Rol por defecto para nuevos usuarios de Google
            }).execute()
            user_id = new_profile.data[0]["id"]
            
        # 3. Establecer la sesión completa en Streamlit
        if user_id:
             # Cargar el perfil completo, incluyendo el rol real
             _fetch_and_set_user_profile(user_id=user_id, email=email)
             st.session_state["google_user"] = decoded_user # Guardar el dict para referencia
             
             # CLAVE: Forzar la recarga para que el Streamlit ya autenticado se renderice
             st.rerun() 
             return True

    except Exception as e:
        # En caso de error, limpiar parámetros de consulta y registrar
        st.experimental_set_query_params()
        # st.error(f"Error en Google OAuth Flow: {e}")
        return False
        
    return False

# ============================================================
# 2. FUNCIONES DE SUPABASE / ROLES (Autorización y Perfil) - UNIFICADO
# (Se mantiene sin cambios, es robusto)
# ============================================================

def _fetch_and_set_user_profile(user_id: str, email: str):
    # (Tu función _fetch_and_set_user_profile sin cambios)
    # ... (código para obtener perfil, parsear fecha y setear st.session_state)
    default_state = {
        "user_role": "guest",
        "full_name": email.split('@')[0],
        "date_of_birth": None,
        "avatar_url": None,
        "user_id": user_id,
        "authenticated": True,
        "user_email": email,
    }

    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        
        if response.data:
            profile = response.data[0]
            
            dob_str = profile.get("date_of_birth")
            date_of_birth = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None

            full_name = profile.get("full_name")
            if not full_name or full_name == "Usuario":
                full_name = email.split('@')[0]
                
            st.session_state.update({
                "authenticated": True,
                "user_email": email,
                "user_id": user_id,
                "user_role": profile.get("role", "guest"),
                "full_name": full_name, 
                "avatar_url": profile.get("avatar_url"),
                "date_of_birth": date_of_birth,
            })
            return True 
        else:
            st.session_state.update(default_state)
            return True
            
    except Exception as e:
        # st.warning(f"Error al cargar perfil de DB: {e}")
        st.session_state.update(default_state)
        return True 


# ============================================================
# 3. FUNCIONES PRINCIPALES DE AUTENTICACIÓN HÍBRIDA (CORREGIDO)
# ============================================================

def check_session() -> bool:
    """
    Verifica la sesión activa en el siguiente orden:
    1. Google OAuth (código en URL) -> Flujo de callback
    2. Tokens de Supabase (access/refresh en URL) -> Reset/Verificación de email
    3. Sesión activa de Supabase (cookies/storage) -> Sesión normal
    """
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"

    # 1. MANEJAR FLUJO DE GOOGLE CALLBACK
    # Si esta función retorna True, significa que se autenticó y forzó un st.rerun().
    # NO es necesario un 'if' aquí, simplemente se ejecuta.
    handle_google_login_flow() 
    # Si 'handle_google_login_flow' tuvo éxito, ya hizo un rerun y el código de abajo no se ejecuta en ese ciclo.

    # 2. MANEJO DE TOKENS DE SUPABASE (Reset o Verificación)
    query_params = st.query_params
    access_token = query_params.get("access_token")
    refresh_token = query_params.get("refresh_token")
    
    if access_token and refresh_token:
        try:
            supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
            st.experimental_set_query_params() # Limpia la URL
            st.rerun() 
            return True
        except Exception:
            st.experimental_set_query_params()
            pass 

    # 3. INTENTO DE SESIÓN ACTIVA (Supabase, ya sea por Email/Pass o por Google/Auth Provider)
    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        
        if user:
            # Si hay sesión de Supabase, cargar el perfil completo y el rol de DB
            return _fetch_and_set_user_profile(user_id=user.id, email=user.email)

    except Exception:
        pass # No hay sesión Supabase activa

    # 4. NO AUTENTICADO (Fallback)
    st.session_state.update({
        "authenticated": False,
        "user_role": "guest",
        "user_id": None,
        "user_email": None,
        "full_name": "Usuario",
        "date_of_birth": None,
        "avatar_url": None,
    })
    return False

# Funciones sign_in_manual, sign_up, request_password_reset, handle_logout...
# (Se mantienen sin cambios, son robustas)

def sign_in_manual(email, password):
    """Inicia sesión con Email/Contraseña."""
    try:
        supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.success("Inicio de sesión exitoso. Recargando...")
        st.rerun()
    except Exception as e:
        st.error(f"Error al iniciar sesión: {e}")

def sign_up(email, password, name):
    # ... (Tu código de sign_up sin cambios)
    try:
        user_response = supabase.auth.sign_up({
            "email": email,
            "password": password,
        })
        user = getattr(user_response, "user", None)
        
        if user:
            user_id = user.id
            supabase.table("profiles").insert({
                "id": user_id, 
                "email": email,
                "full_name": name, 
                "role": "supervisor",
                "date_of_birth": None,
                "avatar_url": None
            }).execute()

            st.success("Registro exitoso. Revisa tu correo electrónico para verificar tu cuenta. Recargando...")
            st.info("⚠️ Si no recibes el correo, verifica la configuración SMTP en el panel de Supabase.")
        else:
             st.error("Error al registrar: No se pudo crear el usuario en el servicio de autenticación.")

    except Exception as e:
        st.error(f"Error al registrar: {e}")

def request_password_reset(email):
    # ... (Tu código de request_password_reset sin cambios)
    try:
        supabase.auth.reset_password_for_email(email)
        st.success("Correo de recuperación enviado.")
        st.info("⚠️ Si no recibes el correo, verifica la configuración SMTP en el panel de Supabase.")
    except Exception as e:
        st.error(f"Error al solicitar recuperación: {e}")

def handle_logout():
    # ... (Tu código de handle_logout sin cambios)
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
    # ... (Tu código de render_login_form sin cambios)
    with st.form("login_form", clear_on_submit=False):
        st.text_input("Correo", key="login_email")
        st.text_input("Contraseña", type="password", key="login_password")
        if st.form_submit_button("Iniciar Sesión"):
            sign_in_manual(st.session_state.login_email, st.session_state.login_password)

def render_signup_form():
    # ... (Tu código de render_signup_form sin cambios)
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
    # ... (Tu código de render_password_reset_form sin cambios)
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

        # --- Botón de Google Rediseñado (Simplificado y usa la función asíncrona) ---
        authorization_url = "#"
        if google_client is not None and REDIRECT_URL:
            try:
                loop = _ensure_loop()
                authorization_url = loop.run_until_complete(_auth_url(google_client, REDIRECT_URL))

            except Exception as e:
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

def set_page(page_name):
    # ... (Tu código de set_page sin cambios)
    st.session_state.current_page = page_name

def render_sidebar():
    # ... (Tu código de render_sidebar sin cambios)
    current_page = st.session_state.get("current_page", "Mi Perfil") 
    user_role = st.session_state.get('user_role', 'guest')
    
    with st.sidebar:
        col1, col2 = st.columns([1, 3])
        with col1:
            avatar_url = st.session_state.get("avatar_url")
            if not avatar_url:
                avatar_url = "https://placehold.co/100x100/A0A0A0/ffffff?text=U"
            
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
            st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
            st.caption(f"Rol: **{user_role.capitalize()}**")

        st.markdown("---")
        
        st.markdown("### Navegación")
        
        icon_map = {
            "Mi Perfil": "👤",
            "Dashboard": "📊",
            "Gestión de Empleados": "👥",
            "Predicción desde Archivo": "📁",
            "Predicción Manual": "✏️",
            "Reconocimiento": "⭐",
            "Historial de Encuesta": "📜"
        }
        
        PAGES_FILTRADAS = []
        for page in PAGES:
            if page == "Gestión de Empleados" and user_role not in ["admin", "supervisor"]:
                 continue
            PAGES_FILTRADAS.append(page)

        for page in PAGES_FILTRADAS:
            icon = icon_map.get(page, "➡️")
            button_style = "primary" if current_page == page else "secondary"
            
            st.button(
                f"{icon} {page}", 
                key=f"nav_{page}", 
                use_container_width=True, 
                type=button_style,
                on_click=set_page, 
                args=(page,)      
            )
            
        st.markdown("---")
        st.markdown(f"**Cuenta:** `{st.session_state.get('user_email', 'Desconocido')}`")
        
        if st.button("Cerrar Sesión", use_container_width=True):
            handle_logout()

        if user_role in ["admin", "supervisor"]: 
             st.markdown("---")
             st.markdown("### ⚙️ Control de Encuestas")
             render_survey_control_panel(supabase)


def render_placeholder_page(page_title):
    # ... (Tu código de render_placeholder_page sin cambios)
    st.title(page_title)
    st.info(f"Esta es la página de **{page_title}**. El contenido detallado se desarrollará en el siguiente paso.")
    st.markdown("---")


# ============================================================
# 6. CONTROL DE FLUJO PRINCIPAL
# ============================================================

# 1. Se ejecuta al inicio para determinar el estado de la sesión
session_is_active = check_session()

# 2. Control de Acceso
if session_is_active:
    
    # 2.1 La sesión está activa, los datos de usuario deben estar en st.session_state
    
    render_sidebar()
    
    # 3. Renderizar la página actual
    page_map = {
        "Mi Perfil": lambda: render_profile_page(supabase, request_password_reset),
        "Dashboard": render_rotacion_dashboard,
        "Gestión de Empleados":lambda: render_employee_management_page(), 
        "Predicción desde Archivo": render_predictor_page,
        "Predicción Manual":render_manual_prediction_tab,
        "Reconocimiento": render_recognition_page,
        "Historial de Encuesta": historial_encuestas_module
    }
    
    current_page = st.session_state.get("current_page", "Mi Perfil")
    
    render_func = page_map.get(current_page)
    
    if render_func:
        render_func()
    else:
        st.error(f"Página '{current_page}' no encontrada. Volviendo a Mi Perfil.")
        set_page("Mi Perfil")
        st.rerun()

else:
    # Si NO está autenticado
    render_auth_page()             

