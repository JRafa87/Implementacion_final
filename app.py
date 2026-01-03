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
    return create_client(url, key)

supabase = get_supabase()

# ============================================================
# 1. FUNCIONES DE LÓGICA Y VALIDACIÓN (Sin Delays)
# ============================================================

def sign_in_manual(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": password})
        if res.user:
            # Almacenamos inmediatamente para evitar el delay de check_session
            st.session_state["authenticated"] = True
            st.rerun() 
    except Exception:
        st.error("❌ Credenciales inválidas.")

def sign_up(email, password, name):
    email_l = email.strip().lower()
    try:
        # Validación instantánea de existencia
        exists = supabase.table("profiles").select("email").eq("email", email_l).maybe_single().execute()
        if exists.data:
            st.error(f"❌ El correo '{email_l}' ya está registrado.")
            return

        res = supabase.auth.sign_up({"email": email_l, "password": password})
        if res.user:
            # Crear perfil base
            supabase.table("profiles").insert({"id": res.user.id, "email": email_l, "full_name": name, "role": "guest"}).execute()
            st.success("✅ Registro exitoso. Verifica tu correo.")
    except Exception as e:
        st.error(f"Error: {e}")

# ============================================================
# 2. RENDERIZADO DE FORMULARIOS (Corrigiendo el NameError)
# ============================================================

def render_login_form():
    with st.form("login_form"):
        e = st.text_input("Correo")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Iniciar Sesión", use_container_width=True):
            sign_in_manual(e, p)

def render_signup_form():
    with st.form("signup_form"):
        n = st.text_input("Nombre completo")
        e = st.text_input("Correo")
        p = st.text_input("Contraseña (mín. 6 caracteres)", type="password")
        if st.form_submit_button("Registrarse", use_container_width=True):
            if n and e and p:
                sign_up(e, p, n)
            else:
                st.error("Completa todos los campos.")

def render_password_reset_form():
    st.markdown("### 🛠️ Gestión de Credenciales")
    metodo = st.radio("Opción:", ["Olvidé mi contraseña (OTP)", "Cambio directo"], horizontal=True)
    
    if metodo == "Olvidé mi contraseña (OTP)":
        if "recovery_step" not in st.session_state: st.session_state.recovery_step = 1
        
        if st.session_state.recovery_step == 1:
            with st.form("otp_req"):
                email = st.text_input("Correo institucional")
                if st.form_submit_button("Enviar Código"):
                    email_l = email.strip().lower()
                    # Validar existencia antes de pedir OTP
                    check = supabase.table("profiles").select("email").eq("email", email_l).maybe_single().execute()
                    if check.data:
                        supabase.auth.reset_password_for_email(email_l)
                        st.session_state.temp_email = email_l
                        st.session_state.recovery_step = 2
                        st.rerun()
                    else:
                        st.error("❌ Correo no encontrado.")
        
        elif st.session_state.recovery_step == 2:
            with st.form("otp_ver"):
                otp = st.text_input("Código de verificación")
                n_p = st.text_input("Nueva contraseña", type="password")
                c_p = st.text_input("Confirmar nueva contraseña", type="password")
                if st.form_submit_button("Cambiar Contraseña"):
                    if n_p == c_p and len(n_p) >= 8:
                        try:
                            supabase.auth.verify_otp({"email": st.session_state.temp_email, "token": otp.strip(), "type": "recovery"})
                            supabase.auth.update_user({"password": n_p})
                            st.success("✅ Contraseña cambiada. Volviendo al login...")
                            time.sleep(1.5)
                            st.session_state.clear()
                            st.rerun()
                        except: st.error("❌ Código inválido.")
            if st.button("⬅️ Volver"):
                st.session_state.recovery_step = 1
                st.rerun()
    else:
        # Aquí iría el formulario de cambio directo que ya tenías definido
        st.info("Formulario de cambio directo activo.")

def render_auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar"])
        with tabs[0]: render_login_form()
        with tabs[1]: render_signup_form()
        with tabs[2]: render_password_reset_form()

# ============================================================
# 3. CONTROL DE FLUJO (Main)
# ============================================================

# Lógica de check_session optimizada para evitar llamadas API constantes
if "authenticated" not in st.session_state:
    try:
        user_res = supabase.auth.get_user()
        if user_res and user_res.user:
            st.session_state["authenticated"] = True
            # Aquí podrías llamar a _fetch_and_set_user_profile si lo necesitas
        else:
            st.session_state["authenticated"] = False
    except:
        st.session_state["authenticated"] = False

if st.session_state["authenticated"]:
    # Llamas a tu sidebar y página actual
    # render_sidebar() ...
    st.write("Bienvenido a la App") 
    if st.button("Cerrar Sesión"):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()
else:
    render_auth_page()


