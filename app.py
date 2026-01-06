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
    "Reconocimiento",
    "Historial de Encuesta"
]

# ============================================================
# 2. FUNCIONES DE APOYO Y PERFIL
# ============================================================

def check_email_exists(email: str) -> bool:
    try:
        response = supabase.table("profiles").select("id").eq("email", email.strip().lower()).execute()
        return len(response.data) > 0
    except:
        return False

def _fetch_and_set_user_profile(user_id: str, email: str):
    """
    Carga el perfil del usuario. 
    SI NO EXISTE en la tabla 'profiles', NO PERMITE EL ACCESO.
    """
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()

        if response.data and len(response.data) > 0:
            profile = response.data[0]
            st.session_state.update({
                "authenticated": True,
                "user_id": user_id,
                "user_email": email,
                "user_role": profile.get("role", "guest"),
                "full_name": profile.get("full_name") or email.split("@")[0]
            })
            return True
        else:
            # Si el usuario existe en Auth pero no en la tabla profiles
            return False
    except Exception as e:
        st.error(f"Error al verificar perfil: {e}")
        return False

# ============================================================
# 3. LÓGICA DE AUTENTICACIÓN
# ============================================================

def check_session() -> bool:
    if st.session_state.get("authenticated"):
        return True
    try:
        res = supabase.auth.get_session()
        if res and res.session:
            # Validamos que además de sesión, tenga perfil en la tabla
            return _fetch_and_set_user_profile(res.user.id, res.user.email)
    except:
        pass
    return False

def handle_logout():
    try:
        supabase.auth.sign_out()
    except:
        pass
    for k in ["authenticated", "user_id", "user_email", "user_role", "full_name", "current_page"]:
        st.session_state.pop(k, None)
    st.rerun()

# ============================================================
# 4. COMPONENTES DE INTERFAZ (UI)
# ============================================================

def render_login_form():
    msg_placeholder = st.empty()
    
    with st.form("login_form_secure"):
        email = st.text_input("Correo electrónico").strip().lower()
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Iniciar Sesión", use_container_width=True)

        if submit:
            if email and password:
                try:
                    auth_res = supabase.auth.sign_in_with_password({
                        "email": email,
                        "password": password
                    })
                    
                    if auth_res.user:
                        # VALIDACIÓN CRÍTICA: ¿Tiene perfil en la tabla?
                        if _fetch_and_set_user_profile(auth_res.user.id, auth_res.user.email):
                            msg_placeholder.success("Acceso concedido.")
                            time.sleep(0.4)
                            st.rerun()
                        else:
                            # Si existe en Auth pero no en perfiles, cerramos sesión de Auth por seguridad
                            supabase.auth.sign_out()
                            msg_placeholder.error("Usuario no registrado en la base de datos de perfiles. Por favor, regístrese.")
                    else:
                        msg_placeholder.error("Correo o contraseña incorrectos.")
                except:
                    msg_placeholder.error("Credenciales inválidas o error de conexión.")
            else:
                msg_placeholder.warning("Complete todos los campos.")

def render_signup_form():
    st.subheader("📝 Crear Cuenta Nueva")
    email_reg = st.text_input("Correo institucional", key="reg_email").strip().lower()
    
    email_exists = False
    if email_reg and "@" in email_reg:
        email_exists = check_email_exists(email_reg)
        if email_exists:
            st.error("Este correo ya está registrado en el sistema.")

    with st.form("signup_action"):
        full_name = st.text_input("Nombre completo")
        pass_reg = st.text_input("Contraseña (mín. 8 caracteres)", type="password")
        submit = st.form_submit_button("Registrarse ahora", use_container_width=True, disabled=email_exists)
        
        if submit:
            if len(pass_reg) >= 8 and full_name and email_reg:
                try:
                    # Al registrarse, Supabase Auth creará el usuario
                    # Importante: Tu base de datos debe tener un Trigger para insertar en 'profiles' 
                    # automáticamente al crearse el registro en Auth.
                    supabase.auth.sign_up({
                        "email": email_reg,
                        "password": pass_reg,
                        "options": {"data": {"full_name": full_name}}
                    })
                    st.success("Registro procesado. Por favor, verifica tu correo electrónico para activar la cuenta.")
                except Exception as e:
                    st.error(f"Error en el registro: {e}")
            else:
                st.error("Asegúrese de llenar todos los campos y que la clave tenga 8+ caracteres.")

def render_password_reset_form():
    st.subheader("🔄 Recuperación de Credenciales")
    metodo = st.radio("Opción:", ["Código OTP (Olvido)", "Cambio Directo"], horizontal=True)

    if metodo == "Código OTP (Olvido)":
        if "recovery_step" not in st.session_state:
            st.session_state.recovery_step = 1

        if st.session_state.recovery_step == 1:
            with st.form("req_otp"):
                email_reset = st.text_input("Correo electrónico").strip().lower()
                if st.form_submit_button("Enviar código al correo"):
                    try:
                        supabase.auth.reset_password_for_email(email_reset)
                        st.session_state.temp_email = email_reset
                        st.session_state.recovery_step = 2
                        st.rerun()
                    except:
                        st.error("No se pudo enviar el código.")
        else:
            with st.form("verify_otp"):
                otp_code = st.text_input("Código de seguridad")
                new_pass = st.text_input("Nueva contraseña", type="password")
                if st.form_submit_button("Cambiar Contraseña"):
                    try:
                        supabase.auth.verify_otp({
                            "email": st.session_state.temp_email,
                            "token": otp_code.strip(),
                            "type": "recovery"
                        })
                        supabase.auth.update_user({"password": new_pass})
                        st.success("✅ Contraseña actualizada correctamente.")
                        st.session_state.recovery_step = 1
                    except:
                        st.error("Código incorrecto o expirado.")

    else:
        with st.form("direct_update_logged"):
            # Campo de contraseña anterior solicitado
            old_p = st.text_input("Contraseña Actual", type="password")
            new_p = st.text_input("Nueva contraseña", type="password")
            conf_p = st.text_input("Confirmar nueva contraseña", type="password")

            if st.form_submit_button("Actualizar"):
                if new_p != conf_p:
                    st.error("Las contraseñas nuevas no coinciden.")
                elif len(new_p) < 8:
                    st.error("Debe tener al menos 8 caracteres.")
                else:
                    try:
                        supabase.auth.update_user({"password": new_p})
                        st.success("Contraseña actualizada con éxito.")
                    except Exception as e:
                        st.error(f"Error: {e}")

def render_auth_page():
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso Corporativo")
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
    user_role = st.session_state.get("user_role", "guest")
    
    with st.sidebar:
        st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
        st.caption(f"Rol: **{user_role.capitalize()}**")
        st.markdown("---")

        icon_map = {
            "Mi Perfil": "👤", "Dashboard": "📊", "Gestión de Empleados": "👥",
            "Predicción desde Archivo": "📁", "Predicción Manual": "✏️",
            "Reconocimiento": "⭐", "Historial de Encuesta": "📜"
        }

        for page in PAGES:
            if page == "Gestión de Empleados" and user_role not in ["admin", "supervisor"]:
                continue
            st.button(
                f"{icon_map.get(page, '➡️')} {page}",
                key=f"nav_{page}",
                use_container_width=True,
                type="primary" if current_page == page else "secondary",
                on_click=set_page,
                args=(page,)
            )

        st.markdown("---")
        if st.button("Cerrar Sesión", use_container_width=True):
            handle_logout()

        if user_role in ["admin", "supervisor"]:
            render_survey_control_panel(supabase)

# ============================================================
# 6. EJECUCIÓN MAESTRA
# ============================================================

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
