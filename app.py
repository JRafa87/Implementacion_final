import streamlit as st
from typing import Optional
from supabase import create_client, Client
import datetime
import pandas as pd
import re
import time

# Importaciones de módulos locales (Asegúrate de que estos archivos existan en tu proyecto)
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
        st.error("ERROR: Faltan secretos en secrets.toml.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

PAGES = [
    "Mi Perfil", "Dashboard", "Gestión de Empleados", 
    "Predicción desde Archivo", "Predicción Manual",
    "Reconocimiento", "Historial de Encuesta" 
]

# ============================================================
# 1. LÓGICA DE SESIÓN (AUTH)
# ============================================================

def check_session() -> bool:
    """Verifica si hay una sesión activa de Supabase."""
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"
    
    # Manejo de recuperación de contraseña vía URL
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
            user = user_res.user
            # Seteo de variables de sesión si no están inicializadas
            if "user_id" not in st.session_state or st.session_state.get("user_id") != user.id:
                st.session_state.update({
                    "authenticated": True,
                    "user_id": user.id,
                    "user_email": user.email,
                    "user_role": "guest",
                    "full_name": user.email.split('@')[0]
                })
                # Cargar datos adicionales del perfil desde DB
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
# 2. RENDERIZADO DE COMPONENTES DE AUTH
# ============================================================

def render_signup_form():
    """Formulario de registro con validación de correo grisado."""
    email_signup = st.text_input("Correo Institucional", key="reg_email").strip().lower()
    
    is_duplicate = False
    if email_signup:
        res = supabase.table("profiles").select("email").eq("email", email_signup).execute()
        if res.data:
            is_duplicate = True
            st.error(f"❌ El correo {email_signup} ya está registrado.")
            st.info("💡 Por favor, dirígete a la pestaña 'Iniciar Sesión'.")

    # Los campos se deshabilitan (gris) si is_duplicate es True
    with st.form("signup_inner_form"):
        name = st.text_input("Nombre completo", disabled=is_duplicate)
        password = st.text_input("Contraseña (mín. 8 caracteres)", type="password", disabled=is_duplicate)
        submit = st.form_submit_button("Crear Cuenta", disabled=is_duplicate)
        
        if submit:
            if name and email_signup and password:
                try:
                    user_response = supabase.auth.sign_up({"email": email_signup, "password": password})
                    if user_response.user:
                        st.success("✅ Registro enviado. Revisa tu correo para verificar la cuenta.")
                except Exception as e:
                    st.error(f"Error al registrar: {e}")
            else:
                st.warning("Completa todos los campos.")

def render_auth_page():
    """Página de acceso principal."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        st.divider()
        
        tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"])
        
        with tabs[0]:
            with st.form("login_form"):
                e = st.text_input("Correo")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Entrar"):
                    try:
                        supabase.auth.sign_in_with_password({"email": e.strip().lower(), "password": p})
                        st.rerun()
                    except:
                        st.error("Credenciales incorrectas.")

        with tabs[1]:
            render_signup_form()

        with tabs[2]:
            st.subheader("Restablecer")
            st.info("Sigue las instrucciones de recuperación enviadas a tu correo.")

# ============================================================
# 3. RENDERIZADO DEL SIDEBAR
# ============================================================

def render_sidebar():
    """Barra lateral con perfil, navegación y control de encuestas."""
    user_role = st.session_state.get('user_role', 'guest')
    user_email = st.session_state.get('user_email', 'Desconocido')
    current_page = st.session_state.get("current_page", "Mi Perfil")
    
    with st.sidebar:
        # Cabecera de Usuario
        st.markdown(f'''
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px;">
                <img src="https://placehold.co/100x100/007ACC/ffffff?text=U" style="border-radius:50%; width:55px; border:2px solid #007ACC;">
                <div>
                    <h4 style="margin:0;">{st.session_state.get('full_name', 'Usuario').split(' ')[0]}</h4>
                    <p style="margin:0; color: #007ACC; font-size: 0.9em; font-weight: bold;">{user_role.capitalize()}</p>
                    <p style="margin:0; color: gray; font-size: 0.8em;">{user_email}</p>
                </div>
            </div>
        ''', unsafe_allow_html=True)
        
        st.divider()

        # Menú de Navegación
        st.markdown("### Navegación")
        pages_to_show = [p for p in PAGES if not (p == "Gestión de Empleados" and user_role not in ["admin", "supervisor"])]
        
        for page in pages_to_show:
            btn_type = "primary" if current_page == page else "secondary"
            if st.button(page, use_container_width=True, type=btn_type, key=f"nav_{page}"):
                st.session_state.current_page = page
                st.rerun()
        
        st.divider()
        
        if st.button("Cerrar Sesión", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.clear()
            st.rerun()

        # Control de Encuestas (Solo para roles autorizados)
        if user_role in ["admin", "supervisor"]:
            st.markdown("---")
            st.markdown("### ⚙️ Control de Encuestas")
            render_survey_control_panel(supabase)

# ============================================================
# 4. FLUJO PRINCIPAL DE EJECUCIÓN
# ============================================================

# Contenedor vacío para evitar el renderizado prematuro (anti-delay)
main_layout = st.empty()

if check_session():
    with main_layout.container():
        render_sidebar()
        
        # Mapeo de páginas a funciones
        page_map = {
            "Mi Perfil": lambda: render_profile_page(supabase, None),
            "Dashboard": render_rotacion_dashboard,
            "Gestión de Empleados": render_employee_management_page,
            "Predicción desde Archivo": render_predictor_page,
            "Predicción Manual": render_manual_prediction_tab,
            "Reconocimiento": render_recognition_page,
            "Historial de Encuesta": historial_encuestas_module
        }
        
        active_page = st.session_state.get("current_page", "Mi Perfil")
        page_map.get(active_page, lambda: st.info("Página no disponible"))()
else:
    with main_layout.container():
        render_auth_page()

