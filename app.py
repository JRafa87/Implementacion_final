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
    "Mi Perfil", "Dashboard", "Gestión de Empleados", 
    "Predicción desde Archivo", "Predicción Manual",
    "Reconocimiento" , "Historial de Encuesta" 
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
        else:
            return True
    except Exception as e:
        st.error(f"Error crítico al cargar perfil: {e}")
        return False

# ============================================================
# 3. LÓGICA DE SESIÓN Y AUTH
# ============================================================

def set_page(page_name):
    st.session_state.current_page = page_name

def check_session() -> bool:
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"

    q = st.query_params
    if q.get("access_token") and q.get("refresh_token"):
        try:
            supabase.auth.set_session(access_token=q["access_token"], refresh_token=q["refresh_token"])
            st.query_params.clear()
            st.rerun()
            return True
        except: pass

    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        if user:
            return _fetch_and_set_user_profile(user_id=user.id, email=user.email)
    except: pass
    return False

def sign_in_manual(email, password):
    try:
        supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": password})
        st.rerun()
    except Exception as e:
        st.error(f"Error al iniciar sesión: Credenciales incorrectas.")

def sign_up(email, password, name):
    """Registra usuario validando duplicados primero."""
    email_limpio = email.strip().lower()
    # Validación de duplicados antes de intentar el registro
    try:
        check = supabase.table("profiles").select("email").eq("email", email_limpio).execute()
        if check.data:
            st.error(f"❌ El correo {email_limpio} ya está registrado.")
            return
            
        user_response = supabase.auth.sign_up({"email": email_limpio, "password": password})
        if user_response.user:
            st.success("✅ Registro exitoso. Revisa tu correo para verificar tu cuenta.")
        else:
            st.error("No se pudo completar el registro.")
    except Exception as e:
        st.error(f"Error: {e}")

# (request_password_reset y process_direct_password_update se mantienen igual que en tu código original)
def request_password_reset(email):
    if not email:
        st.warning("⚠️ Por favor, ingresa un correo electrónico.")
        return
    email_limpio = email.strip().lower()
    try:
        user_check = supabase.table("profiles").select("email").eq("email", email_limpio).execute()
        if user_check.data:
            supabase.auth.reset_password_for_email(email_limpio, {"redirect_to": DIRECT_URL_1})
            st.success(f"📧 Enlace enviado a {email_limpio}")
        else:
            st.error(f"❌ El correo '{email_limpio}' no figura en nuestra base de datos.")
    except Exception as e:
        st.error(f"Error de conexión: {e}")

def process_direct_password_update(email, old_p, new_p, rep_p):
    password_regex = r"^(?=.*[A-Z])(?=.*\d).{8,}$"
    if new_p != rep_p:
        st.error("❌ Las nuevas contraseñas no coinciden.")
        return
    if not re.match(password_regex, new_p):
        st.error("⚠️ Requisitos: Mínimo 8 caracteres, una mayúscula y un número.")
        return
    try:
        supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": old_p})
        supabase.auth.update_user({"password": new_p})
        st.balloons()
        st.success("✅ ¡Contraseña actualizada con éxito!")
    except Exception:
        st.error("❌ Error: La contraseña actual es incorrecta.")

def handle_logout():
    try:
        supabase.auth.sign_out()
    except: pass
    st.session_state.clear()
    st.rerun()

# ============================================================
# 5. UI RENDER (CON MEJORAS VISUALES)
# ============================================================

def render_login_form():
    with st.form("login_form"):
        e = st.text_input("Correo", key="login_email")
        p = st.text_input("Contraseña", type="password", key="login_password")
        if st.form_submit_button("Iniciar Sesión", use_container_width=True):
            sign_in_manual(e, p)

def render_signup_form():
    with st.form("signup_form"):
        n = st.text_input("Nombre completo")
        e = st.text_input("Correo")
        p = st.text_input("Contraseña (mín. 8 caracteres)", type="password")
        if st.form_submit_button("Registrarse", use_container_width=True):
            if n and e and p:
                sign_up(e, p, n)
            else:
                st.error("Completa todos los campos.")

def render_password_reset_form():
    st.markdown("### 🛠️ Gestión de Credenciales")
    metodo = st.radio("Selecciona una opción:", ["Olvidé mi contraseña (OTP)", "Cambio directo"], horizontal=True)
    st.divider()

    if metodo == "Olvidé mi contraseña (OTP)":
        if "recovery_step" not in st.session_state: st.session_state.recovery_step = 1
        if st.session_state.recovery_step == 1:
            with st.form("otp_req"):
                email = st.text_input("Correo institucional")
                if st.form_submit_button("Enviar Código"):
                    request_password_reset(email)
                    st.session_state.temp_email = email
                    st.session_state.recovery_step = 2
                    st.rerun()
        else:
            with st.form("otp_verify"):
                otp = st.text_input("Código de verificación")
                new_p = st.text_input("Nueva contraseña", type="password")
                conf_p = st.text_input("Confirma contraseña", type="password")
                if st.form_submit_button("Validar y Cambiar"):
                    # Lógica OTP simplificada para el ejemplo
                    try:
                        supabase.auth.verify_otp({"email": st.session_state.temp_email, "token": otp, "type": "recovery"})
                        supabase.auth.update_user({"password": new_p})
                        st.success("Cambio exitoso. Redirigiendo...")
                        time.sleep(2)
                        handle_logout()
                    except: st.error("Código incorrecto.")
            if st.button("⬅️ Volver"): st.session_state.recovery_step = 1; st.rerun()
    else:
        with st.form("direct_form"):
            e = st.text_input("Correo")
            o = st.text_input("Clave Actual", type="password")
            n = st.text_input("Nueva Clave", type="password")
            r = st.text_input("Repetir Nueva Clave", type="password")
            if st.form_submit_button("Actualizar"):
                process_direct_password_update(e, o, n, r)

def render_auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        st.markdown("---")
        st.markdown("<p style='text-align: center; font-style: italic; color: #666;'>Ingresa con tus credenciales</p>", unsafe_allow_html=True)
        st.markdown("---")
        tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"])
        with tabs[0]: render_login_form()
        with tabs[1]: render_signup_form()
        with tabs[2]: render_password_reset_form()

def render_sidebar():
    current_page = st.session_state.get("current_page", "Mi Perfil") 
    user_role = st.session_state.get('user_role', 'guest')
    user_email = st.session_state.get('user_email', 'Desconocido')
    
    with st.sidebar:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown(f'<img src="https://placehold.co/100x100/A0A0A0/ffffff?text=U" style="border-radius:50%; width:60px; border:2px solid #007ACC;">', unsafe_allow_html=True)
        with col2:
            st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
            st.caption(f"Rol: **{user_role.capitalize()}**")
            st.caption(f"📧 {user_email}") # <-- Correo visible debajo del Rol

        st.markdown("---")
        st.markdown("### Navegación")
        pages_to_show = [p for p in PAGES if not (p == "Gestión de Empleados" and user_role not in ["admin", "supervisor"])]
        
        for page in pages_to_show:
            if st.button(page, use_container_width=True, type="primary" if current_page == page else "secondary", key=f"nav_{page}"):
                set_page(page)
                st.rerun()
            
        st.markdown("---")
        if st.button("Cerrar Sesión", use_container_width=True):
            handle_logout()

        if user_role in ["admin", "supervisor"]: 
            st.markdown("---")
            st.markdown("### ⚙️ Control de Encuestas")
            render_survey_control_panel(supabase)

# ============================================================
# 6. FLUJO PRINCIPAL (ANTI-DELAY)
# ============================================================

main_placeholder = st.empty()

if check_session():
    with main_placeholder.container():
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
        active = st.session_state.get("current_page", "Mi Perfil")
        page_map.get(active, lambda: st.rerun())()
else:
    with main_placeholder.container():
        render_auth_page()

