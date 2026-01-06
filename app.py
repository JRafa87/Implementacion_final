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

def _fetch_and_set_user_profile(user_id: str, email: str):
    """Carga perfil. Si no existe en tabla 'profiles', retorna False."""
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
        return False
    except:
        return False

# ============================================================
# 3. LÓGICA DE AUTENTICACIÓN (REFINADA PARA EVITAR PARPADEO)
# ============================================================

def login_callback():
    """Ejecuta el login y limpia el estado para un ingreso inmediato."""
    email = st.session_state.get("login_email", "").strip().lower()
    password = st.session_state.get("login_pass", "")
    
    if not email or not password:
        st.session_state.login_error = "Complete todos los campos."
        return

    try:
        auth_res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if auth_res and auth_res.user:
            # Filtro estricto: Debe estar en la tabla profiles
            if _fetch_and_set_user_profile(auth_res.user.id, auth_res.user.email):
                st.session_state.login_error = None
                # No necesitamos hacer nada más, st.rerun() no es necesario aquí 
                # porque el callback ya fuerza la actualización del estado.
            else:
                supabase.auth.sign_out()
                st.session_state.login_error = "Usuario no autorizado: No se encuentra en la base de datos de perfiles."
        else:
            st.session_state.login_error = "Correo o contraseña incorrectos."
    except:
        st.session_state.login_error = "Error de autenticación. Verifique sus datos."

def check_session() -> bool:
    # Prioridad: Si ya marcamos como autenticado en esta ejecución
    if st.session_state.get("authenticated"):
        return True
    
    try:
        # Verificación silenciosa de sesión persistente
        session = supabase.auth.get_session()
        if session and session.user:
            return _fetch_and_set_user_profile(session.user.id, session.user.email)
    except:
        pass
    return False

def handle_logout():
    try:
        supabase.auth.sign_out()
    except:
        pass
    for k in ["authenticated", "user_id", "user_email", "user_role", "full_name", "current_page", "login_error"]:
        st.session_state.pop(k, None)
    st.rerun()

# ============================================================
# 4. COMPONENTES DE INTERFAZ (UI)
# ============================================================

def render_login_form():
    # Usamos un contenedor para agrupar y evitar saltos visuales
    login_cont = st.container()
    with login_cont:
        if st.session_state.get("login_error"):
            st.error(st.session_state.login_error)
            
        st.text_input("Correo electrónico", key="login_email").strip().lower()
        st.text_input("Contraseña", type="password", key="login_pass")
        
        st.button("Iniciar Sesión", 
                  use_container_width=True, 
                  type="primary", 
                  on_click=login_callback)

def render_signup_form():
    st.subheader("📝 Registro de Nuevo Usuario")
    email_reg = st.text_input("Correo institucional", key="reg_email_input").strip().lower()
    
    with st.form("signup_form_final"):
        full_name = st.text_input("Nombre completo")
        pass_reg = st.text_input("Contraseña (mín. 8 caracteres)", type="password")
        submit_btn = st.form_submit_button("Registrarse", use_container_width=True)
        
        if submit_btn:
            if len(pass_reg) >= 8 and full_name and email_reg:
                try:
                    supabase.auth.sign_up({
                        "email": email_reg,
                        "password": pass_reg,
                        "options": {"data": {"full_name": full_name}}
                    })
                    st.success("✅ Registro enviado. Verifica tu correo.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("Datos incompletos o contraseña muy corta.")

def render_password_reset_form():
    st.subheader("🛠️ Gestión de Credenciales")
    metodo = st.radio("Método:", ["Código OTP (Olvido)", "Cambio Directo"], horizontal=True)

    if metodo == "Código OTP (Olvido)":
        if "recovery_step" not in st.session_state:
            st.session_state.recovery_step = 1

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
                        supabase.auth.verify_otp({
                            "email": st.session_state.temp_email,
                            "token": otp_code.strip(),
                            "type": "recovery"
                        })
                        supabase.auth.update_user({"password": new_pass})
                        st.success("Contraseña cambiada con éxito.")
                        st.session_state.recovery_step = 1
                    except:
                        st.error("Error en validación.")

    else:
        with st.form("direct_change_form"):
            old_p = st.text_input("Contraseña Actual", type="password")
            new_p = st.text_input("Nueva contraseña", type="password")
            conf_p = st.text_input("Confirmar nueva contraseña", type="password")

            if st.form_submit_button("Actualizar", use_container_width=True):
                if new_p != conf_p:
                    st.error("Las contraseñas no coinciden.")
                elif len(new_p) < 8:
                    st.error("Mínimo 8 caracteres.")
                elif not old_p:
                    st.error("Ingrese su contraseña actual.")
                else:
                    try:
                        supabase.auth.update_user({"password": new_p})
                        st.success("Contraseña actualizada exitosamente.")
                    except Exception as e:
                        st.error(f"Error: {e}")

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
# 6. EJECUCIÓN MAESTRA (ORDENADA PARA EVITAR PARPADEO)
# ============================================================

# Comprobamos sesión PRIMERO antes de renderizar nada
is_logged_in = check_session()

if is_logged_in:
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
