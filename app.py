import streamlit as st
from typing import Optional
from supabase import create_client, Client
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

# Lógica y configuración de Google OAuth ELIMINADAS COMPLETAMENTE

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
# 1. FUNCIONES AUXILIARES DE GOOGLE OAUTH (ELIMINADAS)
# ============================================================
# Todas las funciones de Google OAuth (get_google_user, sync_google_profile, etc.) han sido eliminadas.


# ============================================================
# 2. FUNCIONES DE SUPABASE / ROLES (Autorización y Perfil) - UNIFICADO
# ============================================================

def _fetch_and_set_user_profile(user_id: str, email: str):
    """
    Obtiene el perfil completo de la tabla 'profiles' y establece TODO el estado de sesión
    basado en el ID de Supabase. Retorna True si la carga fue exitosa (parcial o completa).
    """
    # Inicialización de fallback local (si falla la DB, aún está logueado por Supabase Auth)
    default_state = {
        "user_role": "guest",
        "full_name": email.split('@')[0],
        "date_of_birth": None,
        "avatar_url": None,
        "user_id": user_id,
        "authenticated": True,
        "user_email": email,
    }
    st.session_state.update(default_state) # Establecer valores por defecto/Auth

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
                "user_role": profile.get("role", "guest"),
                "full_name": full_name, 
                "avatar_url": profile.get("avatar_url"),
                "date_of_birth": date_of_birth,
            })
            return True # Perfil cargado
        else:
             # Si el usuario existe en auth pero no en 'profiles', se queda con los valores default_state
             return True
            
    except Exception:
        # Fallback de seguridad si falla la DB o el parseo de fecha
        return True # Asumir que está logueado, pero con rol 'guest'

# ============================================================
# 3. FUNCIONES PRINCIPALES DE AUTENTICACIÓN (SOLO SUPABASE)
# ============================================================

def set_page(page_name):
    """Callback para establecer la nueva página."""
    st.session_state.current_page = page_name

def check_session() -> bool:
    """
    Verifica la sesión activa en el siguiente orden:
    1. Tokens de Supabase (access/refresh en URL)
    2. Sesión activa de Supabase (cookies/storage)
    """
    # Siempre asegurar la página inicial para evitar errores de navegación al inicio
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"

    # La lógica de Google ha sido ELIMINADA

    # 1. Manejo de tokens de Supabase desde la URL (Verificación/Reset)
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

    # 2. Intento de Supabase (Email/Contraseña o Sesión existente)
    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        
        if user:
            # Si hay sesión de Supabase, cargar el perfil y el rol de DB
            return _fetch_and_set_user_profile(user_id=user.id, email=user.email)

    except Exception:
        pass # No hay sesión Supabase activa

    # 3. No autenticado (Fallback de seguridad)
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
        else:
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
    """Cierra la sesión de Supabase y limpia el estado local."""
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
    """Renderiza la página de autenticación (SOLO Email/Pass de Supabase)."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        st.markdown("---")

        # Bloque de Google ELIMINADO

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
        
        icon_map = {
            "Mi Perfil": "👤",
            "Dashboard": "📊",
            "Gestión de Empleados": "👥",
            "Predicción desde Archivo": "📁",
            "Predicción Manual": "✏️",
            "Reconocimiento": "⭐",
            "Historial de Encuesta": "📜"
        }
        
        # Lógica de Permisos (Solo Admins/Supervisores ven Gestión)
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
            render_survey_control_panel(supabase)


# ============================================================
# 6. CONTROL DE FLUJO PRINCIPAL
# ============================================================

# 1. Se ejecuta al inicio para determinar el estado de la sesión
session_is_active = check_session()

# 2. Control de Acceso
if session_is_active:
    # 3. Renderizar la barra lateral y la página actual
    render_sidebar()
    
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
        # Fallback de seguridad: si la página actual no está permitida o no existe
        st.session_state["current_page"] = "Mi Perfil"
        st.rerun()

else:
    # Si NO está autenticado
    render_auth_page()
          

