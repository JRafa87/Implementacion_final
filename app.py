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
    """Carga perfil. Si no existe en la tabla, lo crea automáticamente."""
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            profile = response.data[0]
        else:
            # AUTO-CREACIÓN: Evita que el usuario quede bloqueado si no tiene fila en profiles
            new_profile = {
                "id": user_id,
                "email": email,
                "full_name": email.split("@")[0],
                "role": "guest"
            }
            supabase.table("profiles").insert(new_profile).execute()
            profile = new_profile

        st.session_state.update({
            "authenticated": True,
            "user_id": user_id,
            "user_email": email,
            "user_role": profile.get("role", "guest"),
            "full_name": profile.get("full_name") or email.split("@")[0]
        })
        return True
    except Exception as e:
        st.error(f"Error en perfil: {e}")
        return False

# ============================================================
# 3. LÓGICA DE AUTENTICACIÓN
# ============================================================

def login_callback():
    """Ejecuta el login y maneja errores de confirmación de email."""
    email = st.session_state.get("login_email", "").strip().lower()
    password = st.session_state.get("login_pass", "")
    
    if not email or not password:
        st.session_state.login_error = "⚠️ Complete todos los campos."
        return

    try:
        auth_res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if auth_res and auth_res.user:
            if _fetch_and_set_user_profile(auth_res.user.id, auth_res.user.email):
                st.session_state.login_error = None
                st.session_state.just_logged_in = True
            else:
                st.session_state.login_error = "❌ No se pudo cargar el perfil."
    except Exception as e:
        err_msg = str(e).lower()
        if "confirm" in err_msg:
            st.session_state.login_error = "📧 Debes confirmar tu correo institucional."
        else:
            st.session_state.login_error = "❌ Correo o contraseña incorrectos."

def check_session() -> bool:
    if st.session_state.get("authenticated"):
        return True
    try:
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
    # Limpieza total cumpliendo tus reglas de seguridad
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

# ============================================================
# 4. COMPONENTES DE INTERFAZ (UI)
# ============================================================

def render_login_form():
    if st.session_state.get("just_logged_in"):
        st.empty()
        return

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
    
    # 1. Input de correo fuera del formulario para validación instantánea
    email_reg = st.text_input("Correo institucional", key="reg_email_input").strip().lower()
    
    user_exists = False
    
    # 2. Validación inmediata (Reactiva)
    if email_reg:
        if re.match(r"[^@]+@[^@]+\.[^@]+", email_reg): # Validación básica de formato
            try:
                # Consultamos la tabla profiles gracias a tu política RLS para 'anon'
                check_user = supabase.table("profiles").select("id").eq("email", email_reg).execute()
                
                if check_user.data and len(check_user.data) > 0:
                    user_exists = True
                    st.error("⚠️ Este correo ya está registrado. El botón de registro se ha desactivado.")
            except Exception as e:
                # Si hay error de permisos, fallamos silenciosamente o mostramos alerta técnica
                pass
        elif len(email_reg) > 5:
            st.caption("Escribe un correo válido...")

    # 3. Formulario de registro
    with st.form("signup_form_final"):
        full_name = st.text_input("Nombre completo")
        pass_reg = st.text_input("Contraseña (mín. 8 caracteres)", type="password")
        
        # El botón se bloquea si 'user_exists' es True
        submit_btn = st.form_submit_button(
            "Registrarse", 
            use_container_width=True, 
            disabled=user_exists
        )
        
        if submit_btn:
            if not user_exists and len(pass_reg) >= 8 and full_name and email_reg:
                try:
                    res = supabase.auth.sign_up({
                        "email": email_reg,
                        "password": pass_reg,
                        "options": {"data": {"full_name": full_name}}
                    })
                    st.success("✅ Registro enviado. Verifica tu correo institucional.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("Por favor, verifica que todos los campos sean correctos.")

def render_password_reset_form():
    st.subheader("🔄 Recuperar acceso")
    st.info("Se enviará un código a tu correo para restablecer la contraseña.")

    if "recovery_step" not in st.session_state:
        st.session_state.recovery_step = 1

    if st.session_state.recovery_step == 1:
        with st.form("otp_request"):
            email = st.text_input("Correo institucional")
            if st.form_submit_button("Enviar Código"):
                if email:
                    try:
                        supabase.auth.reset_password_for_email(email.strip().lower())
                        st.session_state.temp_email = email.strip().lower()
                        st.session_state.recovery_step = 2
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        with st.form("otp_verify"):
            st.write(f"Código enviado a: **{st.session_state.temp_email}**")
            otp_code = st.text_input("Código de 6 dígitos")
            new_pass = st.text_input("Nueva contraseña", type="password")
            
            if st.form_submit_button("Confirmar Cambio"):
                try:
                    supabase.auth.verify_otp({
                        "email": st.session_state.temp_email,
                        "token": otp_code.strip(),
                        "type": "recovery"
                    })
                    supabase.auth.update_user({"password": new_pass})
                    st.success("✅ ¡Hecho! Redirigiendo al login...")
                    time.sleep(2)
                    st.session_state.clear()
                    st.rerun()
                except:
                    st.error("Código incorrecto o expirado.")

def render_auth_page():
    if st.session_state.get("just_logged_in"):
        return

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
# 6. EJECUCIÓN MAESTRA
# ============================================================

# ============================================================
# 6. EJECUCIÓN MAESTRA (SIN FLASH)
# ============================================================

# Paso 1: Verificación de sesión
is_logged_in = check_session()

# Paso 2: Dibujar interfaz
if is_logged_in:
    # Si ya entramos, eliminamos cualquier rastro del formulario de login
    if "just_logged_in" in st.session_state:
        del st.session_state["just_logged_in"]
    
    # IMPORTANTE: No renderizamos NADA del login si is_logged_in es True
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
    # Solo si NO está logueado mostramos la página de auth
    render_auth_page()