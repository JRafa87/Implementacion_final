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
        st.error("ERROR: Faltan secretos de Supabase.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

PAGES = ["Mi Perfil", "Dashboard", "Gestión de Empleados", "Predicción desde Archivo", "Predicción Manual", "Reconocimiento", "Historial de Encuesta"]

# ============================================================
# 1. LÓGICA DE SESIÓN (AUTH)
# ============================================================

def check_session() -> bool:
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"

    try:
        user_res = supabase.auth.get_user()
        if user_res.user:
            user = user_res.user
            if "user_id" not in st.session_state or st.session_state.get("user_id") != user.id:
                # Carga inicial de datos
                res = supabase.table("profiles").select("*").eq("id", user.id).limit(1).execute()
                role_db = "guest"
                name_db = user.email.split('@')[0]
                if res.data:
                    role_db = res.data[0].get("role", "guest")
                    name_db = res.data[0].get("full_name") or name_db
                
                st.session_state.update({
                    "authenticated": True,
                    "user_id": user.id,
                    "user_email": user.email,
                    "user_role": role_db,
                    "full_name": name_db
                })
            return True
    except: pass
    return False

# ============================================================
# 2. MEJORAS EN REGISTRO Y RECUPERACIÓN
# ============================================================

def sign_up_validated(email, password, name):
    """Valida existencia antes de registrar."""
    email_clean = email.strip().lower()
    try:
        # VALIDACIÓN: ¿Ya existe en profiles?
        check = supabase.table("profiles").select("email").eq("email", email_clean).execute()
        if check.data:
            st.error(f"❌ El correo {email_clean} ya está registrado en el sistema.")
            return

        # Si no existe, procedemos
        res = supabase.auth.sign_up({"email": email_clean, "password": password})
        if res.user:
            st.success("✅ Registro exitoso. Por favor, verifica tu correo electrónico.")
    except Exception as e:
        st.error(f"Error: {e}")

def render_auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        st.divider()
        tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"])
        
        with tabs[0]: # LOGIN
            with st.form("login_f"):
                e = st.text_input("Correo")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Entrar", use_container_width=True):
                    try:
                        supabase.auth.sign_in_with_password({"email": e.strip().lower(), "password": p})
                        st.rerun()
                    except: st.error("Credenciales incorrectas.")

        with tabs[1]: # REGISTRO
            with st.form("signup_f"):
                n = st.text_input("Nombre Completo")
                e = st.text_input("Correo Institucional")
                p = st.text_input("Contraseña (mín. 8 caracteres)", type="password")
                if st.form_submit_button("Crear Cuenta", use_container_width=True):
                    if n and e and p: sign_up_validated(e, p, n)
                    else: st.warning("Completa todos los campos.")

        with tabs[2]: # RECUPERACIÓN (Sin st.rerun que mande al inicio)
            st.subheader("Restablecer Contraseña")
            metodo = st.selectbox("Elija un método:", ["Seleccione...", "Código OTP por Correo", "Cambio Directo"], key="reset_method")
            
            if metodo == "Código OTP por Correo":
                email_otp = st.text_input("Correo para recibir código")
                if st.button("Enviar Código"):
                    supabase.auth.reset_password_for_email(email_otp.strip().lower())
                    st.success("Enlace/Código enviado.")
            
            elif metodo == "Cambio Directo":
                st.info("Debe conocer su contraseña actual para esta opción.")
                # Aquí iría tu lógica de process_direct_password_update

# ============================================================
# 3. SIDEBAR Y FLUJO PRINCIPAL (ANTIPARPADEO)
# ============================================================

def render_sidebar():
    user_role = st.session_state.get('user_role', 'guest')
    user_email = st.session_state.get('user_email', '')
    curr = st.session_state.get("current_page", "Mi Perfil")

    with st.sidebar:
        st.markdown(f"### 👋 Hola, {st.session_state.get('full_name', 'Usuario')}")
        st.caption(f"**Rol:** {user_role.capitalize()} | 📧 {user_email}")
        st.divider()

        for p in PAGES:
            if p == "Gestión de Empleados" and user_role not in ["admin", "supervisor"]: continue
            if st.button(p, use_container_width=True, type="primary" if curr == p else "secondary"):
                st.session_state.current_page = p
                st.rerun()
        
        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.clear()
            st.rerun()

        # CONTROL DE ENCUESTAS (Optimizado para no refrescar todo)
        if user_role in ["admin", "supervisor"]:
            st.markdown("---")
            with st.expander("⚙️ Configuración de Encuesta", expanded=False):
                render_survey_control_panel(supabase)

# Lógica de renderizado final
main_placeholder = st.empty()

if check_session():
    with main_placeholder.container():
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
        active = st.session_state.get("current_page", "Mi Perfil")
        page_map.get(active, lambda: None)()
else:
    with main_placeholder.container():
        render_auth_page()

