import streamlit as st
from typing import Optional
from supabase import create_client, Client
import datetime
import pandas as pd
import re
import time

# Importaciones de módulos locales
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
        st.error("ERROR: Faltan SUPABASE_URL o SUPABASE_KEY.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

PAGES = [
    "Mi Perfil", "Dashboard", "Gestión de Empleados", 
    "Predicción desde Archivo", "Predicción Manual",
    "Reconocimiento", "Historial de Encuesta" 
]

# ============================================================
# 2. FUNCIONES DE SESIÓN Y AUTH
# ============================================================

def _fetch_and_set_user_profile(user_id: str, email: str):
    st.session_state["authenticated"] = True
    st.session_state["user_id"] = user_id
    st.session_state["user_email"] = email
    
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        if response.data:
            profile = response.data[0]
            st.session_state.update({
                "user_role": profile.get("role", "guest"),
                "full_name": profile.get("full_name") or email.split('@')[0],
            })
        return True
    except Exception:
        return False

def check_session() -> bool:
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"

    # Redirección rápida si hay tokens de recuperación
    q = st.query_params
    if "access_token" in q and "refresh_token" in q:
        try:
            supabase.auth.set_session(access_token=q["access_token"], refresh_token=q["refresh_token"])
            st.query_params.clear()
            st.rerun()
            return True
        except: pass

    try:
        user_res = supabase.auth.get_user()
        if user_res.user:
            return _fetch_and_set_user_profile(user_res.user.id, user_res.user.email)
    except: pass

    st.session_state.update({"authenticated": False})
    return False

def handle_logout():
    try: supabase.auth.sign_out()
    except: pass
    st.session_state.clear()
    st.rerun()

# ============================================================
# 5. RENDERIZADO DE UI (TU INTERFAZ ORIGINAL MEJORADA)
# ============================================================

def render_signup_form():
    """Formulario de registro con validación de correo existente en tiempo real."""
    
    # Campo de correo fuera del submit para validación inmediata
    email_signup = st.text_input("Correo Institucional", key="signup_email_field").strip().lower()
    
    is_duplicate = False
    if email_signup:
        # Verificamos en la DB
        res = supabase.table("profiles").select("email").eq("email", email_signup).execute()
        if res.data:
            is_duplicate = True
            st.error(f"❌ El correo {email_signup} ya está en uso. Por favor, inicia sesión.")

    # El resto de campos se bloquean (disabled) si el correo ya existe
    with st.form("signup_form", clear_on_submit=True):
        name = st.text_input("Nombre completo", disabled=is_duplicate)
        password = st.text_input("Contraseña (mín. 8 caracteres)", type="password", disabled=is_duplicate)
        
        submit = st.form_submit_button("Registrarse", disabled=is_duplicate)
        
        if submit:
            if name and email_signup and password:
                try:
                    user_response = supabase.auth.sign_up({"email": email_signup, "password": password})
                    if user_response.user:
                        st.success("✅ Registro exitoso. Revisa tu correo para verificar tu cuenta.")
                    else:
                        st.error("Error al procesar el registro.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Completa todos los campos.")

def render_auth_page():
    """Interfaz inicial centrada y estética."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        st.markdown("---")
        st.markdown("<p style='text-align: center; font-style: italic; color: #666;'>Ingresa con tus credenciales</p>", unsafe_allow_html=True)
        
        tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"])
        
        with tabs[0]:
            st.subheader("Ingreso Manual")
            with st.form("login_form"):
                e = st.text_input("Correo")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Iniciar Sesión"):
                    try:
                        supabase.auth.sign_in_with_password({"email": e.strip().lower(), "password": p})
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Credenciales incorrectas: {ex}")

        with tabs[1]:
            st.subheader("Crear Cuenta")
            render_signup_form()

        with tabs[2]:
            st.subheader("Restablecer")
            # Aquí va tu render_password_reset_form() original
            st.info("Sigue los pasos para recuperar tu acceso.")

def render_sidebar():
    """Barra lateral con tu estilo original."""
    user_role = st.session_state.get('user_role', 'guest')
    current_page = st.session_state.get("current_page", "Mi Perfil")
    
    with st.sidebar:
        col_img, col_txt = st.columns([1, 3])
        with col_img:
            st.markdown(f'<img src="https://placehold.co/100x100/A0A0A0/ffffff?text=U" style="border-radius:50%; width:60px; border:2px solid #007ACC;">', unsafe_allow_html=True)
        with col_txt:
            st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
            st.caption(f"Rol: **{user_role.capitalize()}**")

        st.markdown("---")
        st.markdown("### Navegación")
        
        pages_to_show = [p for p in PAGES if not (p == "Gestión de Empleados" and user_role not in ["admin", "supervisor"])]
        
        for page in pages_to_show:
            if st.button(page, use_container_width=True, type="primary" if current_page == page else "secondary"):
                st.session_state.current_page = page
                st.rerun()
        
        st.markdown("---")
        if st.button("Cerrar Sesión", use_container_width=True):
            handle_logout()

# ============================================================
# 6. FLUJO DE EJECUCIÓN (SIN DELAY)
# ============================================================

# Contenedor principal para evitar parpadeos
ui_container = st.empty()

# Primero verificamos sesión
authenticated = check_session()

if authenticated:
    with ui_container.container():
        render_sidebar()
        
        # Diccionario de renderizado
        page_map = {
            "Mi Perfil": lambda: render_profile_page(supabase, None),
            "Dashboard": render_rotacion_dashboard,
            "Gestión de Empleados": render_employee_management_page,
            "Predicción desde Archivo": render_predictor_page,
            "Predicción Manual": render_manual_prediction_tab,
            "Reconocimiento": render_recognition_page,
            "Historial de Encuesta": historial_encuestas_module
        }
        
        current = st.session_state.get("current_page", "Mi Perfil")
        page_map.get(current, lambda: st.write("Página en construcción"))()
else:
    # Si no hay sesión, mostramos el login en el mismo contenedor
    with ui_container.container():
        render_auth_page()

