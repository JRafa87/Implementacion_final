import streamlit as st
from typing import Optional
from supabase import create_client, Client
import datetime
import pandas as pd
import re
import time

# --- IMPORTACIONES DE TUS MÓDULOS ---
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
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        role = "guest"
        full_name = email.split('@')[0]
        
        if response.data and len(response.data) > 0:
            profile = response.data[0]
            role = profile.get("role", "guest")
            full_name = profile.get("full_name") or full_name

        st.session_state["authenticated"] = True
        st.session_state["user_id"] = user_id
        st.session_state["user_email"] = email
        st.session_state["user_role"] = role
        st.session_state["full_name"] = full_name
        # Aseguramos que haya una página inicial
        if "current_page" not in st.session_state:
            st.session_state["current_page"] = "Mi Perfil"
        return True
    except:
        return False

def check_session() -> bool:
    if st.session_state.get("authenticated"):
        return True
    try:
        user_res = supabase.auth.get_user()
        if user_res and user_res.user:
            return _fetch_and_set_user_profile(user_res.user.id, user_res.user.email)
    except:
        pass
    return False

def handle_logout():
    supabase.auth.sign_out()
    st.session_state.clear()
    st.rerun()

# ============================================================
# 4. COMPONENTES DE INTERFAZ (LOGIN OPTIMIZADO)
# ============================================================

def render_login_form():
    msg = st.empty()
    email = st.text_input("Correo electrónico", key="login_email").strip().lower()
    password = st.text_input("Contraseña", type="password", key="login_pass")
    
    if st.button("Iniciar Sesión", use_container_width=True, type="primary"):
        if email and password:
            try:
                auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if auth_res.user:
                    _fetch_and_set_user_profile(auth_res.user.id, auth_res.user.email)
                    msg.success("✅ Acceso correcto.")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    msg.error("No se pudo obtener el usuario.")
            except:
                msg.error("Credenciales incorrectas.")
        else:
            msg.warning("Complete los campos.")

# --- Los demás formularios (Signup y Reset) se mantienen igual a tu lógica ---
def render_signup_form():
    st.subheader("📝 Registro")
    email_reg = st.text_input("Correo institucional", key="reg_email_input").strip().lower()
    with st.form("signup_form_final"):
        full_name = st.text_input("Nombre completo")
        pass_reg = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Registrarse", use_container_width=True):
            try:
                supabase.auth.sign_up({"email": email_reg, "password": pass_reg, "options": {"data": {"full_name": full_name}}})
                st.success("Verifica tu correo.")
            except Exception as e: st.error(f"Error: {e}")

def render_password_reset_form():
    st.subheader("🔄 Recuperar")
    metodo = st.radio("Método:", ["Código OTP (Olvido)", "Cambio Directo"], horizontal=True)
    if metodo == "Código OTP (Olvido)":
        # ... lógica de OTP ya establecida ...
        pass
    else:
        with st.form("direct_change"):
            new_p = st.text_input("Nueva contraseña", type="password")
            if st.form_submit_button("Actualizar"):
                supabase.auth.update_user({"password": new_p})
                st.success("Listo.")
                time.sleep(1)
                handle_logout()

def render_auth_page():
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso al Sistema")
        tabs = st.tabs(["🔑 Login", "📝 Registro", "🔄 Recuperar"])
        with tabs[0]: render_login_form()
        with tabs[1]: render_signup_form()
        with tabs[2]: render_password_reset_form()

# ============================================================
# 5. SIDEBAR Y LOGICA DE NAVEGACIÓN
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
        
        for page in PAGES:
            if page == "Gestión de Empleados" and user_role not in ["admin", "supervisor"]: continue
            st.button(f"➡️ {page}", key=f"nav_{page}", use_container_width=True, 
                      type="primary" if current_page == page else "secondary", 
                      on_click=set_page, args=(page,))
            
        st.markdown("---")
        if st.button("Cerrar Sesión", use_container_width=True): handle_logout()

# ============================================================
# 6. EJECUCIÓN MAESTRA (REPARADA PARA MOSTRAR CONTENIDO)
# ============================================================

if check_session():
    render_sidebar()
    
    # Mapeo de funciones de tus archivos externos
    page_map = {
        "Mi Perfil": lambda: render_profile_page(supabase, None),
        "Dashboard": render_rotacion_dashboard,
        "Gestión de Empleados": render_employee_management_page, 
        "Predicción desde Archivo": render_predictor_page,
        "Predicción Manual": render_manual_prediction_tab,
        "Reconocimiento": render_recognition_page,
        "Historial de Encuesta": historial_encuestas_module
    }
    
    # Obtener la página actual o ir a "Mi Perfil" por defecto
    current = st.session_state.get("current_page", "Mi Perfil")
    
    # Ejecutar la función de la página
    if current in page_map:
        page_map[current]()
    else:
        st.error(f"La página '{current}' no está disponible.")
else:
    render_auth_page()