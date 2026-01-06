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
# 2. FUNCIONES DE APOYO Y PERFIL
# ============================================================

def _fetch_and_set_user_profile(user_id: str, email: str):
    """Carga datos de la tabla 'profiles' y los inyecta en la sesión."""
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        
        role = "guest"
        full_name = email.split('@')[0]
        
        if response.data and len(response.data) > 0:
            profile = response.data[0]
            role = profile.get("role", "guest")
            full_name = profile.get("full_name") or full_name

        st.session_state.update({
            "authenticated": True,
            "user_id": user_id,
            "user_email": email,
            "user_role": role,
            "full_name": full_name
        })
        return True
    except:
        return False

# ============================================================
# 3. LÓGICA DE AUTENTICACIÓN (ESTRICTA Y RÁPIDA)
# ============================================================

def check_session() -> bool:
    """Verifica si el usuario ya está autenticado."""
    # Si ya marcamos authenticated en esta ejecución, retornar True inmediatamente
    if st.session_state.get("authenticated"):
        return True

    # Si no, verificar si hay persistencia en Supabase (ej: después de un F5)
    try:
        user_res = supabase.auth.get_user()
        if user_res and user_res.user:
            return _fetch_and_set_user_profile(user_res.user.id, user_res.user.email)
    except:
        pass
    return False

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
    # Eliminamos el st.form si causaba conflictos de doble click, o lo optimizamos:
    with st.container():
        email = st.text_input("Correo electrónico", key="login_email").strip().lower()
        password = st.text_input("Contraseña", type="password", key="login_pass")
        
        if st.button("Iniciar Sesión", use_container_width=True, type="primary"):
            if email and password:
                try:
                    # 1. Intentar autenticación
                    auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    
                    if auth_res.user:
                        # 2. Sincronizar perfil en el momento
                        _fetch_and_set_user_profile(auth_res.user.id, auth_res.user.email)
                        # 3. Rerun inmediato: Streamlit volverá arriba y check_session será True
                        st.rerun()
                except Exception:
                    st.error("Credenciales incorrectas o cuenta no verificada.")
            else:
                st.warning("Por favor, complete los campos.")

def render_auth_page():
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso al Sistema")
        tabs = st.tabs(["🔑 Login", "📝 Registro", "🔄 Recuperar"])
        with tabs[0]: 
            render_login_form()
        with tabs[1]: 
            # (Lógica de signup omitida por brevedad, usa la que ya tenías)
            st.info("Complete los datos en el formulario de registro.")
        with tabs[2]: 
            # (Lógica de recovery omitida por brevedad, usa la que ya tenías)
            st.info("Ingrese su correo para recuperar contraseña.")
ef render_password_reset_form():
    st.subheader("🛠️ Gestión de Credenciales")
    metodo = st.radio("Método:", ["Código OTP (Olvido)", "Cambio Directo"], horizontal=True)

    if metodo == "Código OTP (Olvido)":
        if "recovery_step" not in st.session_state: st.session_state.recovery_step = 1

        if st.session_state.recovery_step == 1:
            with st.form("otp_request"):
                email = st.text_input("Correo")
                if st.form_submit_button("Enviar Código"):
                    supabase.auth.reset_password_for_email(email.strip().lower())
                    st.session_state.temp_email = email.strip().lower()
                    st.session_state.recovery_step = 2
                    st.rerun()
        else:
            with st.form("otp_verify"):
                otp_code = st.text_input("Código OTP")
                new_pass = st.text_input("Nueva contraseña", type="password")
                if st.form_submit_button("Cambiar"):
                    try:
                        supabase.auth.verify_otp({"email": st.session_state.temp_email, "token": otp_code.strip(), "type": "recovery"})
                        supabase.auth.update_user({"password": new_pass})
                        st.success("Cambiado. Volviendo al login...")
                        time.sleep(1.5)
                        handle_logout() # Redirige al login según tus instrucciones
                    except: st.error("Error en validación.")
    else:
        # Lógica de cambio directo omitida para brevedad, igual a la tuya pero con handle_logout() al final
        pass

def render_auth_page():
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso al Sistema")
        tabs = st.tabs(["🔑 Login", "📝 Registro", "🔄 Recuperar"])
        with tabs[0]: render_login_form()
        with tabs[1]: render_signup_form()
        with tabs[2]: render_password_reset_form()
# ============================================================
# 5. SIDEBAR Y FLUJO PRINCIPAL
# ============================================================

def set_page(page_name):
    st.session_state.current_page = page_name

def render_sidebar():
    current_page = st.session_state.get("current_page", "Mi Perfil") 
    user_role = st.session_state.get('user_role', 'guest')
    
    with st.sidebar:
        st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
        st.caption(f"Rol: **{user_role.capitalize()}**")
        st.markdown("---")
        
        icon_map = {"Mi Perfil": "👤", "Dashboard": "📊", "Gestión de Empleados": "👥", "Predicción desde Archivo": "📁", "Predicción Manual": "✏️", "Reconocimiento": "⭐", "Historial de Encuesta": "📜"}
        
        for page in PAGES:
            if page == "Gestión de Empleados" and user_role not in ["admin", "supervisor"]: continue
            st.button(f"{icon_map.get(page, '➡️')} {page}", key=f"nav_{page}", use_container_width=True, 
                      type="primary" if current_page == page else "secondary", on_click=set_page, args=(page,))
            
        st.markdown("---")
        if st.button("Cerrar Sesión", use_container_width=True): handle_logout()
        if user_role in ["admin", "supervisor"]:
            render_survey_control_panel(supabase)

# ============================================================
# 6. EJECUCIÓN MAESTRA
# ============================================================

# Paso 1: Verificar sesión antes de cualquier dibujo
if check_session():
    # Paso 2: Si está logueado, dibujar la App directamente
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
    
    current = st.session_state.get("current_page", "Mi Perfil")
    page_map.get(current, lambda: None)()
else:
    # Paso 3: Si no hay sesión, mostrar Login
    render_auth_page()
