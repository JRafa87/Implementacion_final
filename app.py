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

PAGES = [
    "Mi Perfil", "Dashboard", "Gestión de Empleados", 
    "Predicción desde Archivo", "Predicción Manual",
    "Reconocimiento", "Historial de Encuesta" 
]

# ============================================================
# 2. FUNCIONES DE PERFIL Y SESIÓN
# ============================================================

def _fetch_and_set_user_profile(user_id: str, email: str):
    st.session_state["authenticated"] = True
    st.session_state["user_id"] = user_id
    st.session_state["user_email"] = email
    
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
        st.error(f"Error al cargar perfil: {e}")
        return False

def check_session() -> bool:
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"

    # Verificar tokens en URL
    query_params = st.query_params
    if "access_token" in query_params:
        try:
            supabase.auth.set_session(query_params["access_token"], query_params["refresh_token"])
            st.query_params.clear()
            st.rerun()
        except: pass

    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        if user:
            return _fetch_and_set_user_profile(user.id, user.email)
    except: pass

    st.session_state.update({"authenticated": False, "user_role": "guest"})
    return False

# ============================================================
# 3. ACCIONES DE AUTENTICACIÓN (MEJORADAS)
# ============================================================

def sign_in_manual(email, password):
    try:
        supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": password})
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

def sign_up(email, password, name):
    """MEJORA: Valida duplicados antes de registrar."""
    email_limpio = email.strip().lower()
    try:
        # 1. Verificar si el correo ya existe en la tabla de perfiles
        check_user = supabase.table("profiles").select("email").eq("email", email_limpio).execute()
        
        if check_user.data:
            st.error(f"❌ El correo '{email_limpio}' ya está registrado.")
            st.info("Intenta iniciar sesión o recuperar tu contraseña.")
            return # Bloqueo de flujo

        # 2. Proceder con el registro si no existe
        user_res = supabase.auth.sign_up({"email": email_limpio, "password": password})
        if user_res.user:
            st.success("✅ Registro exitoso. Verifica tu correo electrónico.")
        else:
            st.error("No se pudo completar el registro.")
    except Exception as e:
        st.error(f"Error en registro: {e}")

def handle_logout():
    supabase.auth.sign_out()
    st.session_state.clear()
    st.rerun()

# ============================================================
# 5. RENDERIZADO DE INTERFAZ
# ============================================================

def render_sidebar():
    user_role = st.session_state.get('user_role', 'guest')
    current_page = st.session_state.get("current_page", "Mi Perfil")
    
    with st.sidebar:
        st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
        st.caption(f"Rol: **{user_role.capitalize()}**")
        st.divider()

        # Filtrado de páginas por rol
        pages_to_show = [p for p in PAGES if not (p == "Gestión de Empleados" and user_role not in ["admin", "supervisor"])]
        
        for page in pages_to_show:
            if st.button(page, use_container_width=True, type="primary" if current_page == page else "secondary"):
                st.session_state.current_page = page
                st.rerun()
        
        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            handle_logout()

def render_auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso")
        tab1, tab2, tab3 = st.tabs(["Ingreso", "Registro", "Recuperar"])
        
        with tab1:
            with st.form("login"):
                e = st.text_input("Correo")
                p = st.text_input("Clave", type="password")
                if st.form_submit_button("Entrar"): sign_in_manual(e, p)
        
        with tab2:
            with st.form("signup"):
                n = st.text_input("Nombre")
                e = st.text_input("Correo")
                p = st.text_input("Clave", type="password")
                if st.form_submit_button("Crear Cuenta"): sign_up(e, p, n)
        
        with tab3:
            # Aquí va tu render_password_reset_form original
            pass

# ============================================================
# 6. CONTROL DE FLUJO PRINCIPAL (MEJORA: st.empty)
# ============================================================

# Usamos un contenedor vacío para evitar el renderizado parcial
placeholder = st.empty()

# Verificamos sesión antes de mostrar contenido
is_logged_in = check_session()

if is_logged_in:
    with placeholder.container():
        render_sidebar()
        
        # Mapeo de funciones
        page_map = {
            "Mi Perfil": lambda: render_profile_page(supabase, None), # Ajustar según tu función
            "Dashboard": render_rotacion_dashboard,
            "Gestión de Empleados": render_employee_management_page,
            "Predicción desde Archivo": render_predictor_page,
            "Predicción Manual": render_manual_prediction_tab,
            "Reconocimiento": render_recognition_page,
            "Historial de Encuesta": historial_encuestas_module
        }
        
        current = st.session_state.get("current_page", "Mi Perfil")
        page_map.get(current, lambda: st.write("Página no encontrada"))()
else:
    with placeholder.container():
        render_auth_page()

