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
# 2. FUNCIONES DE SUPABASE / ROLES
# ============================================================

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
            role_db = profile.get("role", "guest")
            name_db = profile.get("full_name")
            
            if not name_db or name_db == "Usuario":
                name_db = email.split('@')[0]
                
            st.session_state.update({
                "user_role": role_db,
                "full_name": name_db,
            })
            return True
        return True
    except Exception as e:
        st.error(f"Error crítico al cargar perfil: {e}")
        return False

# ============================================================
# 3. FUNCIONES DE AUTENTICACIÓN
# ============================================================

def set_page(page_name):
    st.session_state.current_page = page_name

def check_session() -> bool:
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"

    # Si ya estamos autenticados, no re-validamos contra el servidor en cada frame
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
        except:
            pass 

    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        if user:
            return _fetch_and_set_user_profile(user_id=user.id, email=user.email)
    except:
        pass

    return False

def sign_in_manual(email, password):
    try:
        supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.success("Cargando entorno...")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")

def sign_up(email, password, name):
    email_clean = email.strip().lower()
    try:
        # VALIDACIÓN: Verificar si ya existe en la base de datos (TABLA PROFILES)
        existing_user = supabase.table("profiles").select("email").eq("email", email_clean).execute()
        
        if existing_user.data:
            st.warning(f"⚠️ El correo {email_clean} ya está registrado. Por favor, inicia sesión.")
            return

        user_response = supabase.auth.sign_up({
            "email": email_clean,
            "password": password,
        })
        user = getattr(user_response, "user", None)
        
        if user:
            st.success("✅ Registro iniciado. Revisa tu correo para verificar la cuenta.")
        else:
            st.error("Error al registrar: No se pudo crear el usuario.")
    except Exception as e:
        st.error(f"Error al registrar: {e}")

def request_password_reset(email):
    if not email:
        st.warning("⚠️ Ingresa un correo.")
        return
    email_limpio = email.strip().lower()
    try:
        user_check = supabase.table("profiles").select("email").eq("email", email_limpio).execute()
        if user_check.data:
            supabase.auth.reset_password_for_email(email_limpio, {"redirect_to": DIRECT_URL_1})
            st.success(f"📧 Enlace enviado a {email_limpio}")
        else:
            st.error(f"❌ El correo '{email_limpio}' no figura en nuestra base.")
    except Exception as e:
        st.error(f"Error: {e}")

def process_direct_password_update(email, old_p, new_p, rep_p):
    password_regex = r"^(?=.*[A-Z])(?=.*\d).{8,}$"
    if new_p != rep_p:
        st.error("❌ Las contraseñas no coinciden.")
        return
    if not re.match(password_regex, new_p):
        st.error("⚠️ Requisitos: 8+ caracteres, una mayúscula y un número.")
        return
    try:
        supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": old_p})
        supabase.auth.update_user({"password": new_p})
        st.balloons()
        st.success("✅ Contraseña actualizada.")
    except Exception:
        st.error("❌ Credenciales actuales incorrectas.")

def handle_logout():
    try:
        supabase.auth.sign_out()
    except:
        pass
    st.session_state.clear()
    st.rerun()

# ============================================================
# 5. UI COMPONENTS
# ============================================================

def render_login_form():
    with st.form("login_form"):
        st.text_input("Correo", key="login_email")
        st.text_input("Contraseña", type="password", key="login_password")
        if st.form_submit_button("Iniciar Sesión", use_container_width=True):
            sign_in_manual(st.session_state.login_email, st.session_state.login_password)

def render_signup_form():
    with st.form("signup_form", clear_on_submit=False):
        st.text_input("Nombre completo", key="signup_name")
        st.text_input("Correo", key="signup_email")
        st.text_input("Contraseña (mín. 6 caracteres)", type="password", key="signup_password")
        if st.form_submit_button("Registrarse", use_container_width=True):
            if st.session_state.signup_name and st.session_state.signup_email and st.session_state.signup_password:
                sign_up(st.session_state.signup_email, st.session_state.signup_password, st.session_state.signup_name)
            else:
                st.error("Completa todos los campos.")

def render_password_reset_form():
    st.markdown("### 🛠️ Gestión de Credenciales")
    metodo = st.radio("Opción:", ["Código OTP", "Cambio directo"], horizontal=True)
    st.divider()

    if metodo == "Código OTP":
        if "recovery_step" not in st.session_state: st.session_state.recovery_step = 1

        if st.session_state.recovery_step == 1:
            with st.form("otp_request_form"):
                email = st.text_input("Correo institucional")
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
                otp_code = st.text_input("Código OTP")
                new_pass = st.text_input("Nueva contraseña", type="password")
                conf_pass = st.text_input("Confirma contraseña", type="password")
                if st.form_submit_button("Validar y Cambiar"):
                    if len(new_pass) >= 8 and re.search(r"[A-Z]", new_pass) and re.search(r"\d", new_pass):
                        if new_pass == conf_pass:
                            try:
                                supabase.auth.verify_otp({"email": st.session_state.temp_email, "token": otp_code.strip(), "type": "recovery"})
                                supabase.auth.update_user({"password": new_pass})
                                st.success("✅ ¡Éxito! Redirigiendo al login...")
                                time.sleep(2)
                                st.session_state.clear()
                                supabase.auth.sign_out()
                                st.rerun()
                            except: st.error("❌ Código inválido.")
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
                process_direct_password_update(email_d, old_p, new_p, rep_p)

def render_auth_page():
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar"])
        with tabs[0]: render_login_form()
        with tabs[1]: render_signup_form()
        with tabs[2]: render_password_reset_form()

def render_sidebar():
    current_page = st.session_state.get("current_page", "Mi Perfil") 
    user_role = st.session_state.get('user_role', 'guest')
    
    with st.sidebar:
        col1, col2 = st.columns([1, 3])
        with col1:
            avatar = st.session_state.get("avatar_url", "https://placehold.co/100x100?text=U")
            st.markdown(f'<img src="{avatar}" style="border-radius:50%; width:60px; border:2px solid #007ACC;">', unsafe_allow_html=True)
        with col2:
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
            st.markdown("### ⚙️ Control")
            render_survey_control_panel(supabase)

# ============================================================
# MAIN FLOW
# ============================================================

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
    current = st.session_state.get("current_page", "Mi Perfil")
    page_map.get(current, lambda: None)()
else:
    render_auth_page()
