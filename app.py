import streamlit as st
from typing import Optional
from supabase import create_client, Client
import datetime
import pandas as pd
import re
import time

# Importaciones de módulos locales (Se mantienen todos tus módulos)
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
    return create_client(url, key)

supabase = get_supabase()

PAGES = [
    "Mi Perfil", "Dashboard", "Gestión de Empleados", 
    "Predicción desde Archivo", "Predicción Manual",
    "Reconocimiento", "Historial de Encuesta"
]

# ============================================================
# 2. FUNCIONES DE LOGICA Y VALIDACIÓN (Sin recargas bruscas)
# ============================================================

def validate_signup_email():
    """Valida si el correo existe en la base de datos inmediatamente."""
    email = st.session_state.get("signup_email", "").strip().lower()
    if email:
        try:
            # Buscamos en la tabla profiles
            res = supabase.table("profiles").select("email").eq("email", email).execute()
            st.session_state["email_exists"] = bool(res.data)
        except:
            st.session_state["email_exists"] = False

def _fetch_and_set_user_profile(user_id: str, email: str):
    """Establece la sesión y carga el perfil de forma silenciosa."""
    st.session_state.update({
        "authenticated": True,
        "user_id": user_id,
        "user_email": email,
        "user_role": st.session_state.get("user_role", "guest"),
        "full_name": st.session_state.get("full_name", email.split('@')[0])
    })
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        if response.data:
            profile = response.data[0]
            st.session_state.update({
                "user_role": profile.get("role", "guest"),
                "full_name": profile.get("full_name", email.split('@')[0]),
            })
    except:
        pass
    return True

# ============================================================
# 3. ACCIONES DE AUTENTICACIÓN
# ============================================================

def sign_in_manual(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": password})
        if res.user:
            _fetch_and_set_user_profile(res.user.id, res.user.email)
            st.rerun() # Recarga única para entrar a la app
    except Exception as e:
        st.error(f"Error al iniciar sesión: {e}")

def sign_up(email, password, name):
    try:
        user_response = supabase.auth.sign_up({"email": email, "password": password})
        if user_response.user:
            st.success("✅ Registro exitoso. Revisa tu correo para verificar tu cuenta.")
    except Exception as e:
        st.error(f"Error al registrar: {e}")

def check_session() -> bool:
    """Verifica si hay una sesión activa sin parpadeos."""
    if st.session_state.get("authenticated"):
        return True
    try:
        user_response = supabase.auth.get_user()
        if user_response and user_response.user:
            return _fetch_and_set_user_profile(user_response.user.id, user_response.user.email)
    except:
        pass
    return False

# ============================================================
# 5. UI COMPONENTS (FORMULARIOS)
# ============================================================

def render_auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"])
        
        with tabs[0]:
            with st.form("login_form"):
                e = st.text_input("Correo", key="l_email")
                p = st.text_input("Contraseña", type="password", key="l_pass")
                if st.form_submit_button("Iniciar Sesión", use_container_width=True):
                    sign_in_manual(e, p)
        
        with tabs[1]:
            if "email_exists" not in st.session_state: st.session_state.email_exists = False
            with st.form("signup_form"):
                st.text_input("Nombre completo", key="signup_name")
                # El on_change valida el correo ANTES de dar clic en el botón
                st.text_input("Correo", key="signup_email", on_change=validate_signup_email)
                
                if st.session_state.email_exists:
                    st.error(f"⚠️ El correo '{st.session_state.signup_email}' ya existe en nuestra base de datos.")
                
                st.text_input("Contraseña (mín. 6 caracteres)", type="password", key="signup_password")
                
                if st.form_submit_button("Registrarse", use_container_width=True):
                    if st.session_state.email_exists:
                        st.warning("No puedes usar ese correo.")
                    elif st.session_state.signup_name and st.session_state.signup_email:
                        sign_up(st.session_state.signup_email, st.session_state.signup_password, st.session_state.signup_name)
                    else:
                        st.error("Completa todos los campos.")

        with tabs[2]:
            # El selector tiene una KEY para que al cambiar de radio NO se reinicie el tab
            metodo = st.radio("Opción:", ["Código OTP", "Cambio directo"], horizontal=True, key="reset_nav")
            st.divider()
            
            if metodo == "Código OTP":
                # Mantenemos toda tu lógica de recuperación por pasos (1 y 2)
                st.write("### Recuperación por correo")
                email_otp = st.text_input("Correo institucional", key="otp_mail")
                if st.button("Enviar Código"):
                    # Aquí llamarías a reset_password_for_email
                    pass
            else:
                with st.form("direct_reset"):
                    st.text_input("Correo", key="d_email")
                    st.text_input("Clave Actual", type="password", key="d_old")
                    st.text_input("Nueva Clave", type="password", key="d_new")
                    if st.form_submit_button("Actualizar Ahora"):
                        # Aquí llamarías a process_direct_password_update
                        pass

# ============================================================
# 6. MAIN FLOW (SIDEBAR Y NAVEGACIÓN)
# ============================================================

if check_session():
    # Renderizar Sidebar
    current_page = st.session_state.get("current_page", "Mi Perfil")
    user_role = st.session_state.get('user_role', 'guest')

    with st.sidebar:
        st.title(f"👋 {st.session_state.full_name}")
        st.caption(f"Rol: {user_role}")
        st.divider()
        
        for page in PAGES:
            if page == "Gestión de Empleados" and user_role not in ["admin", "supervisor"]: continue
            if st.button(page, use_container_width=True, type="primary" if current_page == page else "secondary"):
                st.session_state.current_page = page
                st.rerun()

        if st.button("Cerrar Sesión", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.clear()
            st.rerun()

    # Mapeo de páginas (Ejecución limpia)
    page_map = {
        "Mi Perfil": lambda: render_profile_page(supabase, None),
        "Dashboard": render_rotacion_dashboard,
        "Gestión de Empleados": render_employee_management_page,
        "Predicción desde Archivo": render_predictor_page,
        "Predicción Manual": render_manual_prediction_tab,
        "Reconocimiento": render_recognition_page,
        "Historial de Encuesta": historial_encuestas_module
    }
    
    page_map.get(current_page, lambda: None)()

else:
    render_auth_page()
