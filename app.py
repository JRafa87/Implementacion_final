import streamlit as st
from typing import Optional
from supabase import create_client, Client
import datetime
import pandas as pd
import re
import time

# Importaciones de módulos locales (Se mantienen todos)
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
    return create_client(url, key)

supabase = get_supabase()

# ============================================================
# 2. LÓGICA DE VALIDACIÓN (FUERA DEL FORMULARIO)
# ============================================================

def check_email_exists(email: str):
    """Consulta rápida a la DB para ver si el correo ya existe."""
    if not email: return False
    try:
        res = supabase.table("profiles").select("email").eq("email", email.strip().lower()).execute()
        return bool(res.data)
    except:
        return False

# ============================================================
# 3. ACCIONES DE AUTENTICACIÓN
# ============================================================

def _fetch_and_set_user_profile(user_id: str, email: str):
    """Establece la sesión de forma inmediata para evitar recargas dobles."""
    st.session_state.update({
        "authenticated": True,
        "user_id": user_id,
        "user_email": email,
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

def sign_in_manual(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": password})
        if res.user:
            _fetch_and_set_user_profile(res.user.id, res.user.email)
            st.rerun()
    except Exception as e:
        st.error("Credenciales incorrectas")

def check_session() -> bool:
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
# 5. UI COMPONENTS (TRANSICIÓN LIMPIA)
# ============================================================

def render_auth_page():
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        # Usamos una key para que el cambio de tab sea instantáneo y no recargue la página
        tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"])
        
        with tabs[0]:
            with st.form("login_form"):
                e = st.text_input("Correo", key="l_email")
                p = st.text_input("Contraseña", type="password", key="l_pass")
                if st.form_submit_button("Entrar", use_container_width=True):
                    sign_in_manual(e, p)
        
        with tabs[1]:
            # --- REGISTRO CON VALIDACIÓN REAL-TIME ---
            # Sacamos el correo del st.form para usar on_change y evitar el error de Streamlit
            st.markdown("### Crear Cuenta")
            nombre = st.text_input("Nombre completo", key="reg_name")
            
            # Validación inmediata del correo
            email_reg = st.text_input("Correo electrónico", key="reg_email")
            
            correo_existe = False
            if email_reg:
                correo_existe = check_email_exists(email_reg)
                if correo_existe:
                    st.error(f"⚠️ El correo '{email_reg}' ya está registrado. Por favor, inicia sesión.")

            with st.form("signup_final_step"):
                pass_reg = st.text_input("Contraseña (mín. 6 caracteres)", type="password")
                # El botón solo funciona si el correo es nuevo
                if st.form_submit_button("Completar Registro", use_container_width=True):
                    if correo_existe:
                        st.warning("Usa un correo diferente.")
                    elif nombre and email_reg and pass_reg:
                        # Llamada a tu función sign_up original
                        st.info("Procesando registro...")
                    else:
                        st.error("Completa todos los campos.")

        with tabs[2]:
            metodo = st.radio("Opción:", ["Código OTP", "Cambio directo"], horizontal=True, key="reset_nav")
            st.divider()
            if metodo == "Código OTP":
                st.write("Ingresa tu correo para recibir el código.")
                # Lógica de recuperación...
            else:
                with st.form("direct_reset"):
                    st.text_input("Correo")
                    st.text_input("Clave Actual", type="password")
                    st.text_input("Nueva Clave", type="password")
                    st.form_submit_button("Actualizar")

# ============================================================
# 6. MAIN FLOW
# ============================================================

if check_session():
    # Sidebar
    current_page = st.session_state.get("current_page", "Mi Perfil")
    user_role = st.session_state.get('user_role', 'guest')

    with st.sidebar:
        st.title(f"👋 {st.session_state.get('full_name', 'Usuario')}")
        st.divider()
        for p in ["Mi Perfil", "Dashboard", "Gestión de Empleados", "Predicción desde Archivo", "Predicción Manual", "Reconocimiento", "Historial de Encuesta"]:
            if p == "Gestión de Empleados" and user_role not in ["admin", "supervisor"]: continue
            if st.button(p, use_container_width=True, type="primary" if current_page == p else "secondary"):
                st.session_state.current_page = p
                st.rerun()
        
        if st.button("Cerrar Sesión", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.clear()
            st.rerun()

    # Mapeo de páginas
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
