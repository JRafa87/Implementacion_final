import streamlit as st
from typing import Optional
from supabase import create_client, Client
import datetime
import pandas as pd
import re
import time

# Importaciones de módulos locales (Asegúrate que estos archivos existan en tu directorio)
from profile import render_profile_page 
from employees_crud import render_employee_management_page
from app_reconocimiento import render_recognition_page
from dashboard_rotacion import render_rotacion_dashboard
from survey_control_logic import render_survey_control_panel
from prediccion_manual_module import render_manual_prediction_tab
from attrition_predictor import render_predictor_page
from encuestas_historial import historial_encuestas_module

DIRECT_URL_1 = "https://desercion-predictor.streamlit.app/?type=recovery"

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
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("ERROR: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

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
# 2. FUNCIONES DE APOYO Y OPTIMIZACIÓN
# ============================================================

def check_email_exists(email: str) -> bool:
    """Valida si el correo ya existe en la base de datos de perfiles."""
    if not email or "@" not in email:
        return False
    try:
        # Consulta ligera: solo pedimos el campo email para minimizar transferencia de datos
        res = supabase.table("profiles").select("email").eq("email", email.strip().lower()).execute()
        return len(res.data) > 0
    except:
        return False

def _fetch_and_set_user_profile(user_id: str, email: str):
    """Carga los datos del perfil en la sesión."""
    st.session_state["authenticated"] = True
    st.session_state["user_id"] = user_id
    st.session_state["user_email"] = email
    st.session_state["user_role"] = "guest"
    st.session_state["full_name"] = email.split('@')[0]

    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        if response.data and len(response.data) > 0:
            profile = response.data[0]
            st.session_state.update({
                "user_role": profile.get("role", "guest"),
                "full_name": profile.get("full_name") or email.split('@')[0],
            })
            return True
        return True
    except Exception as e:
        st.error(f"Error crítico al cargar perfil: {e}")
        return False

# ============================================================
# 3. LOGICA DE AUTENTICACIÓN
# ============================================================

def check_session() -> bool:
    """Verifica la sesión de forma eficiente."""
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"

    # OPTIMIZACIÓN: Si ya está marcado como autenticado en memoria, evitar llamada de red
    if st.session_state.get("authenticated"):
        return True

    # Manejo de tokens de recuperación/verificación
    query_params = st.query_params
    if "access_token" in query_params:
        try:
            supabase.auth.set_session(
                access_token=query_params["access_token"], 
                refresh_token=query_params.get("refresh_token", "")
            )
            st.query_params.clear()
            st.rerun()
        except: pass 

    # Validación con el servidor (Solo ocurre al recargar la pestaña)
    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        if user:
            return _fetch_and_set_user_profile(user_id=user.id, email=user.email)
    except: pass

    return False

def sign_in_manual(email, password):
    try:
        supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": password})
        st.success("Cargando entorno...")
        # Al loguear, limpiamos el estado previo para asegurar carga limpia de perfil
        st.session_state["authenticated"] = False 
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error("Credenciales incorrectas o usuario no verificado.")

def sign_up(email, password, name):
    try:
        user_response = supabase.auth.sign_up({
            "email": email.strip().lower(),
            "password": password,
            "options": {"data": {"full_name": name}}
        })
        if user_response.user:
            st.success("✅ Registro iniciado. Revisa tu correo para verificar la cuenta.")
        else:
            st.error("No se pudo completar el registro.")
    except Exception as e:
        st.error(f"Error: {e}")

def handle_logout():
    try:
        supabase.auth.sign_out()
    except: pass
    st.session_state.clear()
    st.rerun()

# ============================================================
# 4. COMPONENTES DE INTERFAZ (UI)
# ============================================================

def render_login_form():
    with st.form("login_form"):
        email = st.text_input("Correo electrónico")
        password = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Iniciar Sesión", use_container_width=True):
            if email and password:
                sign_in_manual(email, password)
            else:
                st.warning("Ingresa tus credenciales.")

def render_signup_form():
    st.markdown("### Crear cuenta")
    # VALIDACIÓN FUERA DEL FORMULARIO PARA RESPUESTA INMEDIATA
    email_reg = st.text_input("Correo institucional para validar", key="reg_email").strip().lower()
    
    email_exists = False
    if email_reg and "@" in email_reg:
        email_exists = check_email_exists(email_reg)
        if email_exists:
            st.error(f"⚠️ El correo {email_reg} ya está registrado.")
            st.info("Por favor, dirígete a la pestaña de 'Iniciar Sesión' o 'Recuperar'.")

    # Formulario bloqueado si el email existe o está vacío
    with st.form("signup_form_final"):
        full_name = st.text_input("Nombre completo")
        pass_reg = st.text_input("Contraseña (mín. 6 caracteres)", type="password")
        
        submit_btn = st.form_submit_button("Registrarse", 
                                          use_container_width=True, 
                                          disabled=email_exists or not email_reg)
        
        if submit_btn:
            if len(pass_reg) < 6:
                st.error("La contraseña es muy corta.")
            elif full_name:
                sign_up(email_reg, pass_reg, full_name)
            else:
                st.error("Completa tu nombre.")

def render_password_reset_form():
    st.markdown("### 🛠️ Recuperar Acceso")
    email_reset = st.text_input("Ingresa tu correo para recibir el código")
    
    if st.button("Enviar código de recuperación", use_container_width=True):
        if email_reset:
            try:
                supabase.auth.reset_password_for_email(email_reset.strip().lower(), {"redirect_to": DIRECT_URL_1})
                st.success(f"📧 Si el correo existe, se ha enviado un enlace a {email_reset}")
            except Exception as e:
                st.error(f"Error: {e}")
    
    st.divider()
    st.caption("Una vez recibas el correo, sigue las instrucciones para actualizar tu clave.")

def render_auth_page():
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        tabs = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse", "🔄 Recuperar"])
        with tabs[0]: render_login_form()
        with tabs[1]: render_signup_form()
        with tabs[2]: render_password_reset_form()

# ============================================================
# 5. SIDEBAR Y NAVEGACIÓN
# ============================================================

def set_page(page_name):
    st.session_state.current_page = page_name

def render_sidebar():
    current_page = st.session_state.get("current_page", "Mi Perfil") 
    user_role = st.session_state.get('user_role', 'guest')
    
    with st.sidebar:
        col1, col2 = st.columns([1, 3])
        with col1:
            avatar = st.session_state.get("avatar_url", "https://placehold.co/100x100?text=U")
            st.markdown(f'<img src="{avatar}" style="border-radius:50%; width:60px; border:2px solid #007ACC;">', unsafe_allow_html=True)
        with col2:
            st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
            st.caption(f"Rol: **{user_role.capitalize()}**")

        st.markdown("---")
        icon_map = {
            "Mi Perfil": "👤", "Dashboard": "📊", "Gestión de Empleados": "👥", 
            "Predicción desde Archivo": "📁", "Predicción Manual": "✏️", 
            "Reconocimiento": "⭐", "Historial de Encuesta": "📜"
        }
        
        for page in PAGES:
            if page == "Gestión de Empleados" and user_role not in ["admin", "supervisor"]: 
                continue
            
            st.button(
                f"{icon_map.get(page, '➡️')} {page}", 
                key=f"nav_{page}", 
                use_container_width=True, 
                type="primary" if current_page == page else "secondary", 
                on_click=set_page, 
                args=(page,)
            )
            
        st.markdown("---")
        if st.button("Cerrar Sesión", use_container_width=True): 
            handle_logout()

        if user_role in ["admin", "supervisor"]:
            st.markdown("### ⚙️ Control")
            render_survey_control_panel(supabase)

# ============================================================
# MAIN FLOW
# ============================================================

if check_session():
    render_sidebar()
    page_map = {
        "Mi Perfil": lambda: render_profile_page(supabase, None), # Ajustado según necesidad
        "Dashboard": render_rotacion_dashboard,
        "Gestión de Empleados": render_employee_management_page, 
        "Predicción desde Archivo": render_predictor_page,
        "Predicción Manual": render_manual_prediction_tab,
        "Reconocimiento": render_recognition_page,
        "Historial de Encuesta": historial_encuestas_module
    }
    current = st.session_state.get("current_page", "Mi Perfil")
    page_map.get(current, lambda: None)()
else:
    render_auth_page()
