import streamlit as st
from typing import Optional
from supabase import create_client, Client
# Se eliminan los imports de jwt, httpx_oauth, asyncio, y httpx
import datetime
import pandas as pd
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

# Modo testing (para usar localhost o la URL de despliegue)
#testing_mode = st.secrets.get("testing_mode", False)

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

# Cliente de Google OAuth ELIMINADO

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
# 1. FUNCIONES AUXILIARES DE GOOGLE OAUTH ELIMINADAS
# ============================================================
# Se eliminan todas las funciones _decode_google_token, _ensure_loop, 
# _auth_url, _access_token, get_google_user, y sync_google_profile.
# Se mantiene la lógica de Supabase/Perfiles en la sección 2.

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
# 3. FUNCIONES PRINCIPALES DE AUTENTICACIÓN HÍBRIDA (REDUCIDA A SUPABASE)
# ============================================================

def set_page(page_name):
    """Callback para establecer la nueva página."""
    st.session_state.current_page = page_name

def check_session() -> bool:
    """Verifica la sesión de Supabase y actualiza el estado local."""
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"

    # La lógica de Google ha sido ELIMINADA.
    
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
         })

    # 1. Manejo de tokens de Supabase desde la URL (Verificación/Reset)
    query_params = st.query_params
    access_token = query_params.get("access_token")
    refresh_token = query_params.get("refresh_token")
    
    if access_token and refresh_token:
        try:
            # FIX: Asegurarse de que el usuario se obtenga después de set_session
            supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
            st.experimental_set_query_params()
            st.rerun()
            return True
        except Exception:
             # Si falla el set_session (token expirado/inválido)
             pass


    # 2. Intento de Supabase (Sesión existente)
    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        if user:
            st.session_state["authenticated"] = True
            st.session_state["user_email"] = user.email
            # Obtener perfil si es el primer inicio de sesión o si el ID es diferente
            if st.session_state.get("user_id") != user.id:
                 _fetch_user_profile(user_id=user.id)
            return True
    except Exception:
        # Falla al obtener usuario, lo que implica que no hay sesión activa.
        pass

    # 3. No autenticado (Fall-back de seguridad)
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
        # El enlace de reset se enviará al correo electrónico.
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
    # Limpia el estado de sesión para forzar la visualización de la página de login
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
    """Renderiza la página de autenticación, SOLO con Email/Pass de Supabase."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        st.markdown("---")
        
        # El botón de Google ELIMINADO

        # st.markdown("<p style='text-align: center; font-style: italic; color: #666;'>o usa tus credenciales</p>", unsafe_allow_html=True)
        # st.markdown("---") # Se elimina el separador si no hay botón de Google
        
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
                "Reconocimiento": "⭐",
                "Historial de Encuesta": "📜"
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

        # -----------------------------------------------------------------
        # <--- AÑADIR ESTE BLOQUE DE CONTROL DE ENCUESTAS (ADMIN) --->
        # -----------------------------------------------------------------
        
        # El panel ya usa st.sidebar internamente, solo lo llamamos.
        render_survey_control_panel(supabase)


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
    elif page_title == "Historial de Encuestas 📜":
        st.success("Esta es la página que hemos desarrollado. Aquí se permite la **consulta individual por empleado**, mostrando su **trayectoria de riesgo**, el **perfil de satisfacción (Radar)** y la **tabla histórica de respuestas**.")

# ============================================================
# 6. CONTROL DE FLUJO PRINCIPAL
# ============================================================

# 1. Se ejecuta al inicio para determinar el estado de la sesión
session_is_active = check_session()


# 2. Control de Acceso
if session_is_active:
    # Si está autenticado, renderiza la barra lateral y la página principal
    render_sidebar()
    
    # 3. Renderizar la página actual
    page_map = {
        "Mi Perfil": lambda: render_profile_page(supabase, request_password_reset),
        "Dashboard": render_rotacion_dashboard,
        "Gestión de Empleados":lambda: render_employee_management_page() , # Función CRUD dedicada
        "Predicción desde Archivo": render_predictor_page,
        "Predicción Manual":render_manual_prediction_tab,
        "Reconocimiento": render_recognition_page,
        "Historial de Encuesta": historial_encuestas_module
    }
    
    # Ejecutar la función de renderizado para la página actual
    page_map.get(st.session_state.get("current_page", "Mi Perfil"), render_profile_page)()

else:
    # Si NO está autenticado, renderiza la página de login manual
    render_auth_page()            

