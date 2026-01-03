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
        st.error("ERROR: Faltan secretos de Supabase.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

PAGES = ["Mi Perfil", "Dashboard", "Gestión de Empleados", "Predicción desde Archivo", "Predicción Manual", "Reconocimiento", "Historial de Encuesta"]

# ============================================================
# 2. FUNCIONES DE PERFIL Y SESIÓN
# ============================================================

def _fetch_and_set_user_profile(user_id: str, email: str):
    """Establece datos de sesión rápidamente."""
    # Seteo inmediato para evitar que check_session devuelva False por error de latencia
    st.session_state["authenticated"] = True
    st.session_state["user_id"] = user_id
    st.session_state["user_email"] = email

    try:
        # Traemos solo lo necesario para mayor velocidad
        response = supabase.table("profiles").select("role, full_name").eq("id", user_id).maybe_single().execute()
        if response.data:
            st.session_state["user_role"] = response.data.get("role", "guest")
            st.session_state["full_name"] = response.data.get("full_name") or email.split('@')[0]
        else:
            st.session_state["user_role"] = "guest"
            st.session_state["full_name"] = email.split('@')[0]
        return True
    except:
        return True # Permitir entrada aunque falle el perfil (fallback a email)

def check_session() -> bool:
    """Verificación de sesión ultra-rápida."""
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
# 3. LÓGICA DE AUTENTICACIÓN (MEJORADA Y SIN DELAY)
# ============================================================

def sign_in_manual(email, password):
    if not email or not password:
        st.warning("⚠️ Completa todos los campos.")
        return
    
    with st.spinner("Autenticando..."):
        try:
            res = supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": password})
            if res.user:
                # Actualizamos estado ANTES del rerun para eliminar el delay visual
                _fetch_and_set_user_profile(res.user.id, res.user.email)
                st.rerun()
        except:
            st.error("❌ Credenciales inválidas.")

def sign_up(email, password, name):
    """Validación de duplicados y registro bloqueante."""
    email_limpio = email.strip().lower()
    
    if len(password) < 6:
        st.error("❌ La contraseña debe tener al menos 6 caracteres.")
        return

    with st.spinner("Validando correo..."):
        try:
            # 1. BLOQUEO DE DUPLICADOS: Verificar si el correo ya existe en la DB
            check_user = supabase.table("profiles").select("email").eq("email", email_limpio).execute()
            
            if check_user.data and len(check_user.data) > 0:
                st.error(f"❌ El correo '{email_limpio}' ya está registrado. El registro se ha bloqueado.")
                return # SE BLOQUEA EL REGISTRO AQUÍ

            # 2. Si no existe, procedemos
            user_response = supabase.auth.sign_up({"email": email_limpio, "password": password})
            
            if user_response.user:
                st.success("✅ Cuenta creada. Por favor, verifica tu correo electrónico.")
                st.balloons()
            else:
                st.error("No se pudo procesar el registro.")
        except Exception as e:
            st.error(f"Error: {str(e)}")

# ============================================================
# 5. UI Y RENDERIZADO
# ============================================================

def render_auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        st.divider()
        tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar"])
        
        with tabs[0]:
            with st.form("login_f"):
                e = st.text_input("Correo")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Entrar", use_container_width=True):
                    sign_in_manual(e, p)
        
        with tabs[1]:
            with st.form("signup_f"):
                n = st.text_input("Nombre completo")
                em = st.text_input("Correo")
                pw = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Crear Cuenta", use_container_width=True):
                    if n and em and pw:
                        sign_up(em, pw, n)
                    else:
                        st.error("Faltan datos.")
        
        with tabs[2]:
            render_password_reset_form()

def render_sidebar():
    user_role = st.session_state.get('user_role', 'guest')
    current_page = st.session_state.get("current_page", "Mi Perfil")
    
    with st.sidebar:
        st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
        st.caption(f"Rol: {user_role}")
        st.divider()
        
        for page in PAGES:
            if page == "Gestión de Empleados" and user_role not in ["admin", "supervisor"]:
                continue
            
            if st.button(page, use_container_width=True, type="primary" if current_page == page else "secondary"):
                st.session_state.current_page = page
                st.rerun()
                
        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.clear()
            st.rerun()

# ============================================================
# 6. FLUJO PRINCIPAL (ATÓMICO)
# ============================================================

# Eliminamos el delay de carga verificando la sesión una sola vez al inicio
if check_session():
    render_sidebar()
    
    page_map = {
        "Mi Perfil": lambda: render_profile_page(supabase, request_password_reset),
        "Dashboard": render_rotacion_dashboard,
        "Gestión de Empleados": render_employee_management_page, 
        "Predicción desde Archivo": render_predictor_page,
        "Predicción Manual": render_manual_prediction_tab,
        "Reconocimiento": render_recognition_page,
        "Historial de Encuesta": historial_encuestas_module
    }
    
    cp = st.session_state.get("current_page", "Mi Perfil")
    if cp in page_map:
        page_map[cp]()
else:
    render_auth_page()

