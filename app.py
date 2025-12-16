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

# Cliente de Google OAuth
try:
    client_id = st.secrets["client_id"]
    client_secret = st.secrets["client_secret"]
    redirect_url = st.secrets["REDIRECT_URL"]
    google_client = GoogleOAuth2(client_id, client_secret)
except KeyError:
    google_client = None
    # st.warning("Google OAuth no configurado") # Comentado para evitar spam de warnings
    redirect_url = None

REDIRECT_URL = redirect_url # Usar la variable local o None

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
# 1. FUNCIONES AUXILIARES DE GOOGLE OAUTH
# ============================================================

def _decode_google_token(token: str):
    return jwt.decode(token, options={"verify_signature": False})

def _ensure_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

async def _auth_url():
    if not google_client or not REDIRECT_URL: return "#" # Fallback de seguridad
    url = await google_client.get_authorization_url(
        REDIRECT_URL,
        scope=["email", "profile"]
    )
    return url

async def _access_token(code: str):
    if not google_client or not REDIRECT_URL: return None
    return await google_client.get_access_token(code, REDIRECT_URL)

def get_google_user() -> Optional[dict]:
    if "google_user" in st.session_state:
        # Ya autenticado en la sesión actual
        return st.session_state["google_user"]

    if not google_client:
        return None

    code = st.query_params.get("code")
    if not code:
        return None

    try:
        loop = _ensure_loop()
        token = loop.run_until_complete(_access_token(code))
        
        # Si la URL tenía parámetros de autenticación, limpiarlos
        st.experimental_set_query_params() 

        # Si no hay token o id_token (error de Google)
        if not token or "id_token" not in token:
            return None
            
        decoded = _decode_google_token(token["id_token"])


        # Almacenar el usuario de Google para el paso de sincronización
        st.session_state["google_user"] = {
            "email": decoded.get("email"),
            "name": decoded.get("name"),
            "avatar": decoded.get("picture"),
            "sub": decoded.get("sub") # El ID de Google, útil para Supabase
        }
        return st.session_state["google_user"]
    except Exception as e:
        # st.error(f"Error en Google OAuth: {e}")
        st.experimental_set_query_params() 
        return None

# Mantenemos esta función de sincronización, pero la simplificaremos al final
# para que se use el mismo cargador de perfil que Supabase, usando el ID de Supabase.
def sync_google_profile(user):
    """
    Sincroniza el perfil de Google con la tabla 'profiles' de Supabase.
    Si el usuario existe, lo actualiza. Si no, lo crea con rol 'guest'.
    """
    email = user["email"]
    name = user["name"]
    avatar = user["avatar"]

    profile = (
        supabase.table("profiles")
        .select("*")
        .eq("email", email)
        .limit(1)
        .execute()
    )
    
    # 1. Si el perfil existe, lo actualiza
    if profile.data:
        # Actualiza solo nombre y avatar (si cambian)
        supabase.table("profiles").update({
            "full_name": name,
            "avatar_url": avatar
        }).eq("email", email).execute()

        p = profile.data[0]
        # Establece la sesión con el ID y ROL de Supabase
        st.session_state.update({
            "authenticated": True,
            "user_email": email,
            "user_id": p["id"],
            "user_role": p.get("role", "guest"),
            "full_name": name,
            "avatar_url": avatar
        })
    # 2. Si el perfil no existe, lo crea
    else:
        new = supabase.table("profiles").insert({
            "email": email,
            "full_name": name,
            "avatar_url": avatar,
            "role": "guest" # Rol por defecto para nuevos
        }).execute()
        
        # Establece la sesión con el ID y ROL de Supabase
        st.session_state.update({
            "authenticated": True,
            "user_email": email,
            "user_id": new.data[0]["id"],
            "user_role": "guest",
            "full_name": name,
            "avatar_url": avatar
        })
    
    # Asegurar que se cargue la página inicial después de una autenticación exitosa
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"
    
    # Usar un rerun para asegurar que la UI cambie inmediatamente después de la sincronización
    st.rerun() 
    # NOTA: Este rerun es crítico para la transición de la página de login a la app principal.

# ============================================================
# 2. FUNCIONES DE SUPABASE / ROLES (Autorización y Perfil) - UNIFICADO
# ============================================================

def _fetch_and_set_user_profile(user_id: str, email: str):
    """
    CORRECCIÓN: Obtiene el perfil completo y establece TODO el estado de sesión
    basado en el ID de Supabase.
    """
    # Inicialización de fallback local
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
            
            # 1. Manejar la fecha de nacimiento: convertir la cadena de Supabase a objeto date
            dob_str = profile.get("date_of_birth")
            date_of_birth = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None

            # 2. Fallback si el nombre está vacío
            full_name = profile.get("full_name")
            if not full_name or full_name == "Usuario":
                full_name = email.split('@')[0]
                
            # Actualizar el estado con datos de la DB
            st.session_state.update({
                "authenticated": True,
                "user_email": email,
                "user_id": user_id,
                "user_role": profile.get("role", "guest"),
                "full_name": full_name, 
                "avatar_url": profile.get("avatar_url"),
                "date_of_birth": date_of_birth,
            })
            return True # Perfil cargado
        else:
            # Si el usuario existe en auth pero no en 'profiles' (raro/error), usar defaults
            st.session_state.update(default_state)
            return True
            
    except Exception as e:
        # Fallback de seguridad si falla la DB o el parseo de fecha
        # st.warning(f"Error al cargar perfil de DB: {e}")
        st.session_state.update(default_state)
        return True # Asumir que está logueado, pero con rol 'guest'


# ============================================================
# 3. FUNCIONES PRINCIPALES DE AUTENTICACIÓN HÍBRIDA (CORREGIDO)
# ============================================================

def check_session() -> bool:
    """
    Verifica la sesión activa en el siguiente orden:
    1. Google OAuth (código en URL)
    2. Tokens de Supabase (access/refresh en URL)
    3. Sesión activa de Supabase (cookies/storage)
    """
    # Siempre asegurar la página inicial para evitar errores de navegación al inicio
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"

    # 1. Intento de Google OAuth
    google_user = get_google_user()
    if google_user:
        # La función sync_google_profile maneja la BD, setea el estado y fuerza el st.rerun().
        # Si llega aquí, significa que hay un código en la URL y se está procesando.
        # Es CRÍTICO que sync_google_profile haga un rerun para saltar a la app.
        sync_google_profile(google_user) 
        return True # Aunque sync_google_profile hace un rerun, retornamos True para no continuar.

    # 2. Manejo de tokens de Supabase desde la URL (Verificación/Reset)
    query_params = st.query_params
    access_token = query_params.get("access_token")
    refresh_token = query_params.get("refresh_token")
    
    if access_token and refresh_token:
        try:
            # Establece la sesión en el cliente de Supabase
            supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
            st.experimental_set_query_params() # Limpia la URL
            st.rerun() # Fuerza la recarga con la sesión activa
            return True
        except Exception:
            # Fallo en la sesión URL
            st.experimental_set_query_params()
            pass 

    # 3. Intento de Supabase (Email/Contraseña o Sesión existente)
    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        
        if user:
            # Si hay sesión de Supabase, cargar el perfil y el rol de DB
            return _fetch_and_set_user_profile(user_id=user.id, email=user.email)

    except Exception:
        pass # No hay sesión Supabase activa

    # 4. No autenticado (Fallback de seguridad, si todos los métodos fallaron)
    st.session_state.update({
        "authenticated": False,
        "user_role": "guest",
        "user_id": None,
        "user_email": None,
        "full_name": "Usuario",
        "date_of_birth": None,
        "avatar_url": None,
        # 'current_page' ya está seteado o lo dejamos como está
    })
    return False

def sign_in_manual(email, password):
    """Inicia sesión con Email/Contraseña."""
    try:
        # La función sign_in_with_password establece la sesión en el cliente
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
        user_response = supabase.auth.sign_up({
            "email": email,
            "password": password,
        })
        user = getattr(user_response, "user", None)
        
        if user:
            # 2. Crear entrada en la tabla 'profiles' para el nombre y rol
            user_id = user.id
            supabase.table("profiles").insert({
                "id": user_id, 
                "email": email,
                "full_name": name, 
                "role": "supervisor", # Rol inicial por defecto
                "date_of_birth": None,
                "avatar_url": None
            }).execute()

            st.success("Registro exitoso. Revisa tu correo electrónico para verificar tu cuenta. Recargando...")
            st.info("⚠️ Si no recibes el correo, verifica la configuración SMTP en el panel de Supabase.")
            # st.rerun() # No es necesario el rerun aquí, la verificación es asíncrona.
        else:
            # Manejar el caso donde SupabaseAuthError no lanza excepción pero user es None
             st.error("Error al registrar: No se pudo crear el usuario en el servicio de autenticación.")

    except Exception as e:
        st.error(f"Error al registrar: {e}")

def request_password_reset(email):
    """Solicita un enlace para restablecer la contraseña."""
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

# Las funciones render_login_form, render_signup_form, render_password_reset_form 
# y render_auth_page se mantienen sin cambios, ya que su lógica de UI es correcta.

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
        authorization_url = "#"
        if google_client is not None and REDIRECT_URL:
            try:
                loop = _ensure_loop()
                authorization_url = loop.run_until_complete(_auth_url())

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
    """Callback para establecer la nueva página."""
    st.session_state.current_page = page_name

def render_sidebar():
    """Renderiza la barra lateral con información de la sesión y navegación."""
    
    current_page = st.session_state.get("current_page", "Mi Perfil") 
    user_role = st.session_state.get('user_role', 'guest')
    
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
            st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
            st.caption(f"Rol: **{user_role.capitalize()}**")

        st.markdown("---")
        
        # Menú de Navegación
        st.markdown("### Navegación")
        
        # Filtrar o asignar iconos
        icon_map = {
            "Mi Perfil": "👤",
            "Dashboard": "📊",
            "Gestión de Empleados": "👥",
            "Predicción desde Archivo": "📁",
            "Predicción Manual": "✏️",
            "Reconocimiento": "⭐",
            "Historial de Encuesta": "📜"
        }
        
        # Lógica de Permisos (Ejemplo: Solo Admins/Supervisores ven Gestión)
        # Puedes adaptar esta lógica según tus roles:
        PAGES_FILTRADAS = []
        for page in PAGES:
            # Ejemplo de restricción
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
                on_click=set_page, # Función callback
                args=(page,)      # Argumento de la función callback
            )
            
        st.markdown("---")
        # Sección de la cuenta (Cerrar Sesión)
        st.markdown(f"**Cuenta:** `{st.session_state.get('user_email', 'Desconocido')}`")
        
        if st.button("Cerrar Sesión", use_container_width=True):
            handle_logout()

        # -----------------------------------------------------------------
        # <--- BLOQUE DE CONTROL DE ENCUESTAS (ADMIN/SUPERVISOR) --->
        # -----------------------------------------------------------------
        
        if user_role in ["admin", "supervisor"]: 
             st.markdown("---")
             st.markdown("### ⚙️ Control de Encuestas")
             # El panel ya usa st.sidebar internamente.
             render_survey_control_panel(supabase)


def render_placeholder_page(page_title):
    """Función de marcador de posición para páginas futuras (sin la gestión de empleados)."""
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
    # 2.1 Asegurar que la sesión se haya cargado correctamente antes de renderizar
    if "user_id" not in st.session_state or st.session_state["user_id"] is None:
        # Esto puede ocurrir si check_session falla justo después de Google
        # Forzamos la carga del perfil por si acaso (aunque check_session debería hacerlo)
        if st.session_state.get("user_email"):
             # Forzar la obtención de la info completa, asumiendo que el ID vendrá del get_user()
             pass # El flujo de check_session ya debería haber llamado a _fetch_and_set_user_profile o sync_google_profile

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
    
    # Ejecutar la función de renderizado para la página actual
    # Usar get() para tener un fallback en caso de error
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

