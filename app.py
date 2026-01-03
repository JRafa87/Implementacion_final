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
        st.error("ERROR: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

PAGES = [
    "Mi Perfil", "Dashboard", "Gestión de Empleados", 
    "Predicción desde Archivo", "Predicción Manual",
    "Reconocimiento", "Historial de Encuesta" 
]

# ============================================================
# 2. FUNCIONES DE SESIÓN Y SEGURIDAD
# ============================================================

def check_session() -> bool:
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"

    # Captura de tokens de recuperación (Password Reset)
    q = st.query_params
    if "access_token" in q:
        try:
            supabase.auth.set_session(access_token=q["access_token"], refresh_token=q["refresh_token"])
            st.query_params.clear()
            st.rerun()
        except: pass

    try:
        user_res = supabase.auth.get_user()
        if user_res.user:
            user = user_res.user
            if "user_id" not in st.session_state:
                st.session_state.update({
                    "authenticated": True,
                    "user_id": user.id,
                    "user_email": user.email,
                    "user_role": "guest",
                    "full_name": user.email.split('@')[0]
                })
                # Carga de perfil real
                res = supabase.table("profiles").select("*").eq("id", user.id).limit(1).execute()
                if res.data:
                    p = res.data[0]
                    st.session_state.update({
                        "user_role": p.get("role", "guest"),
                        "full_name": p.get("full_name") or user.email.split('@')[0]
                    })
            return True
    except: pass
    return False

# ============================================================
# 5. RENDERIZADO DE UI (INTERFAZ ORIGINAL RESTAURADA)
# ============================================================

def render_signup_form():
    """Registro con validación en tiempo real y bloqueo visual."""
    email_signup = st.text_input("Correo Institucional", key="signup_email_unique").strip().lower()
    
    is_duplicate = False
    if email_signup:
        res = supabase.table("profiles").select("email").eq("email", email_signup).execute()
        if res.data:
            is_duplicate = True
            st.error(f"❌ El correo {email_signup} ya está en uso.")

    with st.form("signup_form_original"):
        name = st.text_input("Nombre completo", disabled=is_duplicate)
        password = st.text_input("Contraseña (mín. 8 caracteres)", type="password", disabled=is_duplicate)
        submit = st.form_submit_button("Registrarse", disabled=is_duplicate)
        
        if submit:
            if name and email_signup and password:
                try:
                    supabase.auth.sign_up({"email": email_signup, "password": password})
                    st.success("✅ Revisa tu correo para verificar la cuenta.")
                except Exception as e:
                    st.error(f"Error: {e}")

def render_auth_page():
    """Volvemos a la interfaz inicial de columnas y tabs estéticos."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        st.markdown("---")
        st.markdown("<p style='text-align: center; font-style: italic; color: #666;'>Ingresa con tus credenciales</p>", unsafe_allow_html=True)
        st.markdown("---")

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
                    except:
                        st.error("Acceso denegado.")

        with tabs[1]:
            st.subheader("Crear Cuenta")
            render_signup_form()

        with tabs[2]:
            st.subheader("Restablecer")
            st.info("Ingresa tu correo institucional para recibir las instrucciones.")

def render_sidebar():
    """Sidebar con perfil completo, correo y control de encuestas."""
    user_role = st.session_state.get('user_role', 'guest')
    user_email = st.session_state.get('user_email', '')
    current_page = st.session_state.get("current_page", "Mi Perfil")
    
    with st.sidebar:
        # Perfil Visual Original
        col_img, col_txt = st.columns([1, 3])
        with col_img:
            st.markdown(f'<img src="https://placehold.co/100x100/A0A0A0/ffffff?text=U" style="border-radius:50%; width:60px; border:2px solid #007ACC;">', unsafe_allow_html=True)
        with col_txt:
            st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
            st.caption(f"Rol: **{user_role.capitalize()}**")
            st.caption(f"📧 {user_email}")

        st.markdown("---")
        st.markdown("### Navegación")
        
        # Filtro de páginas por rol
        pages_to_show = [p for p in PAGES if not (p == "Gestión de Empleados" and user_role not in ["admin", "supervisor"])]
        
        for page in pages_to_show:
            if st.button(page, use_container_width=True, type="primary" if current_page == page else "secondary", key=f"btn_{page}"):
                st.session_state.current_page = page
                st.rerun()
        
        st.markdown("---")
        if st.button("Cerrar Sesión", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.clear()
            st.rerun()

        # CONTROL DE ENCUESTAS (No afecta el parpadeo de otras páginas)
        if user_role in ["admin", "supervisor"]:
            st.markdown("---")
            st.markdown("### ⚙️ Control de Encuestas")
            render_survey_control_panel(supabase)

# ============================================================
# 6. FLUJO DE CONTROL PRINCIPAL (OPTIMIZADO)
# ============================================================

# Este contenedor es la clave para eliminar el delay y parpadeo al cargar
placeholder = st.empty()

if check_session():
    with placeholder.container():
        render_sidebar()
        
        page_map = {
            "Mi Perfil": lambda: render_profile_page(supabase, None),
            "Dashboard": render_rotacion_dashboard,
            "Gestión de Empleados": render_employee_management_page,
            "Predicción desde Archivo": render_predictor_page,
            "Predicción Manual": render_manual_prediction_tab,
            "Reconocimiento": render_recognition_page,
            "Historial de Encuesta": historial_encuestas_module
        }
        
        # Ejecutamos la página actual
        active = st.session_state.get("current_page", "Mi Perfil")
        page_map.get(active, lambda: None)()
else:
    with placeholder.container():
        render_auth_page()

