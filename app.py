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
    """Inicializa y cachea el cliente de Supabase."""
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
    """Obtiene el perfil completo y establece el estado de sesión."""
    st.session_state["authenticated"] = True
    st.session_state["user_id"] = user_id
    st.session_state["user_email"] = email
    
    if "user_role" not in st.session_state:
        st.session_state["user_role"] = "guest"
    if "full_name" not in st.session_state:
        st.session_state["full_name"] = email.split('@')[0]

    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        if response.data:
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
# 3. FUNCIONES DE AUTENTICACIÓN (MEJORADAS)
# ============================================================

def set_page(page_name):
    st.session_state.current_page = page_name

def check_session() -> bool:
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"

    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        if user:
            return _fetch_and_set_user_profile(user_id=user.id, email=user.email)
    except:
        pass

    st.session_state.update({
        "authenticated": False,
        "user_role": "guest",
        "user_id": None,
        "user_email": None,
        "full_name": "Usuario",
    })
    return False

def sign_in_manual(email, password):
    if not email or not password:
        st.warning("Por favor, completa ambos campos.")
        return
    
    with st.spinner("Iniciando sesión..."):
        try:
            supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": password})
            st.success("Acceso concedido.")
            time.sleep(0.5) # Delay mínimo para feedback visual
            st.rerun()
        except Exception as e:
            st.error("Error: Credenciales incorrectas o usuario no verificado.")

def sign_up(email, password, name):
    """Registro con validación de duplicados y bloqueo de flujo."""
    email_limpio = email.strip().lower()
    
    if len(password) < 6:
        st.error("La contraseña debe tener al menos 6 caracteres.")
        return

    with st.spinner("Verificando disponibilidad..."):
        try:
            # VALIDACIÓN: Verificar si el correo ya existe en la tabla de perfiles
            check_user = supabase.table("profiles").select("email").eq("email", email_limpio).execute()
            
            if check_user.data:
                st.error(f"❌ El correo '{email_limpio}' ya está registrado. Intenta iniciar sesión.")
                return # Detenemos aquí para no crear el usuario en Auth

            # Proceso de registro
            user_response = supabase.auth.sign_up({
                "email": email_limpio,
                "password": password,
            })
            
            if user_response.user:
                st.success("✅ Registro exitoso.")
                st.info("Revisa tu correo electrónico para verificar tu cuenta antes de ingresar.")
            else:
                st.error("No se pudo completar el registro.")
        except Exception as e:
            st.error(f"Error al registrar: {e}")

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
        st.error("⚠️ Mínimo 8 caracteres, una mayúscula y un número.")
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
    except:
        pass
    st.session_state.clear()
    st.rerun() 
    
# ============================================================
# 5. FUNCIONES DE UI (Interfaz de Usuario)
# ============================================================

def render_login_form():
    with st.form("login_form"):
        email = st.text_input("Correo", key="login_email_input")
        password = st.text_input("Contraseña", type="password", key="login_pass_input")
        if st.form_submit_button("Iniciar Sesión", use_container_width=True):
            sign_in_manual(email, password)

def render_signup_form():
    with st.form("signup_form"):
        name = st.text_input("Nombre completo")
        email = st.text_input("Correo")
        password = st.text_input("Contraseña (mín. 6 caracteres)", type="password")
        if st.form_submit_button("Registrarse", use_container_width=True):
            if name and email and password:
                sign_up(email, password, name)
            else:
                st.error("Completa todos los campos.")

def render_password_reset_form():
    st.markdown("### 🛠️ Gestión de Credenciales")
    metodo = st.radio("Selecciona una opción:", ["Olvidé mi contraseña (OTP)", "Cambio directo"], horizontal=True)
    st.divider()

    if metodo == "Olvidé mi contraseña (OTP)":
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
        
        elif st.session_state.recovery_step == 2:
            st.info(f"Código enviado a: {st.session_state.temp_email}")
            with st.form("otp_verify_form"):
                otp_code = st.text_input("Código de verificación")
                new_pass = st.text_input("Nueva contraseña", type="password")
                conf_pass = st.text_input("Confirma contraseña", type="password")
                if st.form_submit_button("Validar y Cambiar"):
                    if len(new_pass) >= 8 and new_pass == conf_pass:
                        try:
                            supabase.auth.verify_otp({"email": st.session_state.temp_email, "token": otp_code.strip(), "type": "recovery"})
                            supabase.auth.update_user({"password": new_pass})
                            st.success("✅ Contraseña actualizada.")
                            time.sleep(2)
                            st.session_state.clear()
                            st.rerun()
                        except: st.error("❌ Código incorrecto.")
            if st.button("⬅️ Volver"):
                st.session_state.recovery_step = 1
                st.rerun()
    else:
        with st.form("direct_update_form"):
            e_d = st.text_input("Correo")
            o_p = st.text_input("Contraseña actual", type="password")
            n_p = st.text_input("Nueva contraseña", type="password")
            r_p = st.text_input("Confirmar", type="password")
            if st.form_submit_button("Actualizar Ahora"):
                process_direct_password_update(e_d, o_p, n_p, r_p)

def render_auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        st.markdown("---")
        tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"])
        with tabs[0]: render_login_form()
        with tabs[1]: render_signup_form()
        with tabs[2]: render_password_reset_form()

def render_sidebar():
    current_page = st.session_state.get("current_page", "Mi Perfil") 
    user_role = st.session_state.get('user_role', 'guest')
    
    with st.sidebar:
        st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
        st.caption(f"Rol: **{user_role.capitalize()}**")
        st.divider()
        
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
            
        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            handle_logout()

        if user_role in ["admin", "supervisor"]: 
            st.divider()
            st.markdown("### ⚙️ Control de Encuestas")
            render_survey_control_panel(supabase)

# ============================================================
# 6. CONTROL DE FLUJO PRINCIPAL
# ============================================================

if check_session():
    render_sidebar()
    page_map = {
        "Mi Perfil": lambda: render_profile_page(supabase, request_password_reset),
        "Dashboard": render_rotacion_dashboard,
        "Gestión de Empleados": lambda: render_employee_management_page(), 
        "Predicción desde Archivo": render_predictor_page,
        "Predicción Manual": render_manual_prediction_tab,
        "Reconocimiento": render_recognition_page,
        "Historial de Encuesta": historial_encuestas_module
    }
    
    current_page = st.session_state.get("current_page", "Mi Perfil")
    render_func = page_map.get(current_page)
    
    if render_func:
        render_func()
    else:
        st.session_state["current_page"] = "Mi Perfil"
        st.rerun()
else:
    render_auth_page()

