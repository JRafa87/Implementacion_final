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
# 2. FUNCIONES DE APOYO Y OPTIMIZACIÓN
# ============================================================

def check_email_exists(email: str) -> bool:
    if not email or "@" not in email:
        return False
    try:
        res = supabase.table("profiles").select("email").eq("email", email.strip().lower()).execute()
        return len(res.data) > 0
    except:
        return False

def _fetch_and_set_user_profile(user_id: str, email: str):
    st.session_state["authenticated"] = True
    st.session_state["user_id"] = user_id
    st.session_state["user_email"] = email
    st.session_state["user_role"] = "guest"
    st.session_state["full_name"] = email.split('@')[0]

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
    except:
        return False

# ============================================================
# 3. LÓGICA DE AUTENTICACIÓN
# ============================================================

def check_session() -> bool:
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"

    if st.session_state.get("authenticated"):
        return True

    query_params = st.query_params
    if "access_token" in query_params:
        try:
            supabase.auth.set_session(
                access_token=query_params["access_token"], 
                refresh_token=query_params.get("refresh_token", "")
            )
            st.query_params.clear()
            st.rerun()
        except: pass 

    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        if user:
            return _fetch_and_set_user_profile(user_id=user.id, email=user.email)
    except: pass
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
    with st.form("login_form"):
        email = st.text_input("Correo electrónico")
        password = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Iniciar Sesión", use_container_width=True):
            try:
                supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": password})
                st.success("Accediendo...")
                st.session_state["authenticated"] = False 
                time.sleep(0.5)
                st.rerun()
            except:
                st.error("Credenciales incorrectas.")

def render_signup_form():
    st.subheader("📝 Registro de Nuevo Usuario")
    # Validación de correo fuera del formulario
    email_reg = st.text_input("Correo institucional (validación)", key="reg_email_input").strip().lower()
    
    email_exists = False
    if email_reg and "@" in email_reg:
        email_exists = check_email_exists(email_reg)
        if email_exists:
            st.error(f"⚠️ El correo {email_reg} ya existe.")
            st.info("Usa la pestaña de 'Iniciar Sesión'.")

    with st.form("signup_form_final"):
        full_name = st.text_input("Nombre completo")
        pass_reg = st.text_input("Contraseña (mín. 8 caracteres)", type="password")
        
        submit_btn = st.form_submit_button("Registrarse", 
                                          use_container_width=True, 
                                          disabled=email_exists or not email_reg)
        
        if submit_btn:
            if len(pass_reg) >= 8 and full_name:
                try:
                    supabase.auth.sign_up({
                        "email": email_reg, 
                        "password": pass_reg, 
                        "options": {"data": {"full_name": full_name}}
                    })
                    st.success("✅ Registro enviado. Verifica tu correo.")
                except Exception as e: st.error(f"Error: {e}")
            else:
                st.error("Datos incompletos o contraseña muy corta.")

def render_password_reset_form():
    st.subheader("🛠️ Gestión de Credenciales")
    metodo = st.radio("Método de recuperación:", ["Código OTP (Olvido)", "Cambio Directo (Clave actual)"], horizontal=True)
    st.divider()

    if metodo == "Código OTP (Olvido)":
        if "recovery_step" not in st.session_state: st.session_state.recovery_step = 1

        if st.session_state.recovery_step == 1:
            with st.form("otp_request_form"):
                email = st.text_input("Correo para recibir código")
                if st.form_submit_button("Enviar Código"):
                    if email:
                        try:
                            supabase.auth.reset_password_for_email(email.strip().lower())
                            st.session_state.temp_email = email.strip().lower()
                            st.session_state.recovery_step = 2
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
        else:
            with st.form("otp_verify_form"):
                st.info(f"Código enviado a: {st.session_state.temp_email}")
                otp_code = st.text_input("Código OTP")
                new_pass = st.text_input("Nueva contraseña", type="password")
                conf_pass = st.text_input("Confirmar contraseña", type="password")
                if st.form_submit_button("Validar y Cambiar"):
                    if new_pass == conf_pass and len(new_pass) >= 8:
                        try:
                            supabase.auth.verify_otp({"email": st.session_state.temp_email, "token": otp_code.strip(), "type": "recovery"})
                            supabase.auth.update_user({"password": new_pass})
                            st.success("✅ ¡Éxito! Redirigiendo al login...")
                            time.sleep(2)
                            handle_logout()
                        except: st.error("❌ Código inválido o expirado.")
                    else: st.error("Las claves no coinciden o son insuficientes.")
            if st.button("⬅️ Volver"):
                st.session_state.recovery_step = 1
                st.rerun()
    else:
        with st.form("direct_update_form"):
            col1, col2 = st.columns(2)
            with col1:
                email_d = st.text_input("Correo")
                old_p = st.text_input("Clave actual", type="password")
            with col2:
                new_p = st.text_input("Nueva clave", type="password")
                rep_p = st.text_input("Confirmar", type="password")
            
            if st.form_submit_button("Actualizar Ahora"):
                if new_p == rep_p and len(new_p) >= 8:
                    try:
                        supabase.auth.sign_in_with_password({"email": email_d.strip().lower(), "password": old_p})
                        supabase.auth.update_user({"password": new_p})
                        st.success("✅ Contraseña actualizada.")
                        time.sleep(1)
                        handle_logout()
                    except: st.error("❌ Clave actual incorrecta.")
                else: st.error("Revise la nueva clave.")

def render_auth_page():
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso al Sistema")
        tabs = st.tabs(["🔑 Login", "📝 Registro", "🔄 Recuperar"])
        with tabs[0]: render_login_form()
        with tabs[1]: render_signup_form()
        with tabs[2]: render_password_reset_form()

# ============================================================
# 5. SIDEBAR Y MAIN FLOW
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

if check_session():
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
    render_auth_page()
