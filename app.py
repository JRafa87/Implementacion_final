import streamlit as st
from typing import Optional
from supabase import create_client, Client
import datetime
import pandas as pd

# Importaciones locales
from profile import render_profile_page
from employees_crud import render_employee_management_page
from app_reconocimiento import render_recognition_page
from dashboard_rotacion import render_rotacion_dashboard
from survey_control_logic import render_survey_control_panel
from prediccion_manual_module import render_manual_prediction_tab
from attrition_predictor import render_predictor_page
from encuestas_historial import historial_encuestas_module

import re
import time

DIRECT_URL_1 = "https://desercion-predictor.streamlit.app/?type=recovery"

# ============================================================
# 0. CONFIGURACIÓN
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
        st.error("ERROR: Faltan credenciales Supabase.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

PAGES = [
    "Mi Perfil",
    "Dashboard",
    "Gestión de Empleados",
    "Predicción desde Archivo",
    "Predicción Manual",
    "Reconocimiento",
    "Historial de Encuesta"
]

# ============================================================
# 2. PERFIL Y ROLES
# ============================================================

def _fetch_and_set_user_profile(user_id: str, email: str):
    st.session_state["authenticated"] = True
    st.session_state["user_id"] = user_id
    st.session_state["user_email"] = email
    st.session_state["user_role"] = "guest"
    st.session_state["full_name"] = email.split("@")[0]

    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        if response.data:
            profile = response.data[0]
            st.session_state["user_role"] = profile.get("role", "guest")
            st.session_state["full_name"] = profile.get("full_name") or email.split("@")[0]
        return True
    except Exception as e:
        st.error(f"Error cargando perfil: {e}")
        return False

# ============================================================
# 3. AUTENTICACIÓN
# ============================================================

def set_page(page_name):
    st.session_state.current_page = page_name

def check_session() -> bool:
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Mi Perfil"

    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        if user:
            return _fetch_and_set_user_profile(user.id, user.email)
    except Exception:
        pass

    st.session_state.update({
        "authenticated": False,
        "user_role": "guest",
        "user_id": None,
        "user_email": None,
        "full_name": "Usuario",
    })
    return False

# ============================================================
# LOGIN SIN DELAY
# ============================================================

def sign_in_manual(email, password):
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": email.strip().lower(),
            "password": password
        })

        user = auth_response.user
        if user:
            _fetch_and_set_user_profile(user.id, user.email)
            st.session_state.current_page = "Mi Perfil"
            st.success("✅ Sesión iniciada")
            st.rerun()

    except Exception:
        st.error("❌ Correo o contraseña incorrectos.")

# ============================================================
# REGISTRO CON VALIDACIÓN DE CORREO
# ============================================================

def sign_up(email, password, name):
    email = email.strip().lower()

    try:
        exists = supabase.table("profiles").select("id").eq("email", email).execute()
        if exists.data and len(exists.data) > 0:
            st.error("❌ Este correo ya está registrado.")
            return

        user_response = supabase.auth.sign_up({
            "email": email,
            "password": password,
        })

        user = getattr(user_response, "user", None)
        if user:
            supabase.table("profiles").insert({
                "id": user.id,
                "email": email,
                "full_name": name,
                "role": "guest"
            }).execute()

            st.success("✅ Registro exitoso.")
            st.info("📧 Revisa tu correo para verificar tu cuenta.")
        else:
            st.error("❌ No se pudo crear el usuario.")

    except Exception as e:
        st.error(f"Error al registrar: {e}")

# ============================================================
# RECUPERACIÓN DE CONTRASEÑA (ORIGINAL INTACTO)
# ============================================================

def request_password_reset(email):
    if not email:
        st.warning("⚠️ Ingresa un correo.")
        return

    email = email.strip().lower()
    try:
        user_check = supabase.table("profiles").select("email").eq("email", email).execute()
        if user_check.data:
            supabase.auth.reset_password_for_email(email, {"redirect_to": DIRECT_URL_1})
            st.success(f"📧 Enlace enviado a {email}")
        else:
            st.error("❌ El correo no está registrado.")
    except Exception as e:
        st.error(f"Error: {e}")

def process_direct_password_update(email, old_p, new_p, rep_p):
    regex = r"^(?=.*[A-Z])(?=.*\d).{8,}$"

    if new_p != rep_p:
        st.error("❌ Las contraseñas no coinciden.")
        return
    if not re.match(regex, new_p):
        st.error("⚠️ Mínimo 8 caracteres, una mayúscula y un número.")
        return

    try:
        supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": old_p})
        supabase.auth.update_user({"password": new_p})
        st.balloons()
        st.success("✅ Contraseña actualizada.")
    except Exception:
        st.error("❌ Contraseña actual incorrecta.")

# ============================================================
# LOGOUT
# ============================================================

def handle_logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    st.rerun()

# ============================================================
# UI AUTH (LOGIN / REGISTRO / RECUPERACIÓN)
# ============================================================

def render_login_form():
    with st.form("login_form"):
        st.text_input("Correo", key="login_email")
        st.text_input("Contraseña", type="password", key="login_password")
        if st.form_submit_button("Iniciar Sesión"):
            sign_in_manual(st.session_state.login_email, st.session_state.login_password)

def render_signup_form():
    with st.form("signup_form"):
        st.text_input("Nombre completo", key="signup_name")
        st.text_input("Correo", key="signup_email")
        st.text_input("Contraseña", type="password", key="signup_password")
        if st.form_submit_button("Registrarse"):
            sign_up(
                st.session_state.signup_email,
                st.session_state.signup_password,
                st.session_state.signup_name
            )

def render_password_reset_form():
    st.markdown("### 🛠️ Recuperar Contraseña")
    email = st.text_input("Correo")
    if st.button("Enviar enlace"):
        request_password_reset(email)

def render_auth_page():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("Acceso a la Plataforma")
        tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"])
        with tabs[0]:
            render_login_form()
        with tabs[1]:
            render_signup_form()
        with tabs[2]:
            render_password_reset_form()

# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar():
    current_page = st.session_state.get("current_page")
    user_role = st.session_state.get("user_role")

    with st.sidebar:
        st.title(f"👋 {st.session_state.get('full_name')}")
        st.caption(f"Rol: {user_role}")

        for page in PAGES:
            if page == "Gestión de Empleados" and user_role not in ["admin", "supervisor"]:
                continue
            st.button(page, on_click=set_page, args=(page,), use_container_width=True)

        st.markdown("---")
        st.button("Cerrar Sesión", use_container_width=True, on_click=handle_logout)

        if user_role in ["admin", "supervisor"]:
            st.markdown("---")
            render_survey_control_panel(supabase)

# ============================================================
# MAIN
# ============================================================

session_is_active = check_session()

if session_is_active:
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

    render_func = page_map.get(st.session_state.current_page)
    if render_func:
        render_func()
else:
    render_auth_page()



