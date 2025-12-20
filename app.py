import streamlit as st
from typing import Optional
from supabase import create_client, Client
import datetime
import pandas as pd
# Importaciones de módulos locales (deben existir en tu proyecto)
from profile import render_profile_page # <-- Asumimos que profile.py existe
from employees_crud import render_employee_management_page
from app_reconocimiento import render_recognition_page
from dashboard_rotacion import render_rotacion_dashboard
from survey_control_logic import render_survey_control_panel
from prediccion_manual_module import render_manual_prediction_tab
from attrition_predictor import render_predictor_page
from encuestas_historial import historial_encuestas_module
import re
import time

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
        st.error("ERROR: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml. La autenticación fallará.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()


# --- 1. DETECTOR DE REGRESO POR CORREO ---
# Se activa solo si la URL trae el token de recuperación
query_params = st.query_params

if query_params.get("type") == "recovery":
    st.title("🔄 Restablecer mi Contraseña")
    st.info("Has accedido mediante un enlace seguro de recuperación.")
    
    with st.form("recovery_form_final"):
        nueva_clave = st.text_input("Ingresa tu nueva contraseña", type="password")
        confirma_clave = st.text_input("Confirma tu nueva contraseña", type="password")
        
        # Regla de seguridad: 6 caracteres, 1 Mayúscula, 1 Número
        regex_seguridad = r"^(?=.*[A-Z])(?=.*\d).{6,}$"

        if st.form_submit_button("Guardar y volver al Login"):
            if nueva_clave != confirma_clave:
                st.error("Las contraseñas no coinciden.")
            elif not re.match(regex_seguridad, nueva_clave):
                st.error("La clave debe tener al menos 6 caracteres, una mayúscula y un número.")
            else:
                try:
                    # Supabase usa el token invisible de la URL para saber quién es el usuario
                    supabase.auth.update_user({"password": nueva_clave})
                    st.success("✅ ¡Contraseña actualizada con éxito!")
                    
                    # CUMPLIENDO TU INSTRUCCIÓN: Redirigir al Login
                    time.sleep(2)
                    st.query_params.clear() 
                    st.session_state.clear()
                    st.rerun() 
                except Exception as e:
                    st.error(f"Error técnico: {e}")
    st.stop() # Evita que cargue el resto de la página mientras está restableciendo


# Definición de todas las páginas disponibles
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
# 1. FUNCIONES AUXILIARES (ELIMINADAS)
# ============================================================


# ============================================================
# 2. FUNCIONES DE SUPABASE / ROLES (Autorización y Perfil)
# ============================================================

def _fetch_and_set_user_profile(user_id: str, email: str):
    """Obtiene el perfil completo de la tabla 'profiles' y establece el estado de sesión."""
    default_state = {
        "user_role": "guest",
        "full_name": email.split('@')[0],
        "user_id": user_id,
        "authenticated": True,
        "user_email": email,
    }
    st.session_state.update(default_state)

    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        
        if response.data:
            #profile = response.data[0]
            #dob_str = profile.get("date_of_birth")
            #date_of_birth = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None

            full_name = profile.get("full_name")
            if not full_name or full_name == "Usuario":
                full_name = email.split('@')[0]
                
            st.session_state.update({
                "user_role": profile.get("role", "guest"),
                "full_name": full_name,
            })
            return True
        else:
             return True
            
    except Exception:
        return True


# ============================================================
# 3. FUNCIONES PRINCIPALES DE AUTENTICACIÓN (SOLO SUPABASE)
# ============================================================

def set_page(page_name):
    """Callback para establecer la nueva página."""
    st.session_state.current_page = page_name

def check_session() -> bool:
    """Verifica la sesión activa de Supabase."""
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"

    query_params = st.query_params
    access_token = query_params.get("access_token")
    refresh_token = query_params.get("refresh_token")
    
    if access_token and refresh_token:
        try:
            supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
            st.experimental_set_query_params()
            st.rerun()
            return True
        except Exception:
            st.experimental_set_query_params() 
            pass 

    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        
        if user:
            return _fetch_and_set_user_profile(user_id=user.id, email=user.email)

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

def sign_in_manual(email, password):
    """Inicia sesión con Email/Contraseña."""
    try:
        supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.success("Inicio de sesión exitoso. Recargando...")
        st.rerun()
    except Exception as e:
        st.error(f"Error al iniciar sesión: {e}")

def sign_up(email, password, name):
    """Registra un nuevo usuario en Supabase y crea su perfil inicial."""
    try:
        user_response = supabase.auth.sign_up({
            "email": email,
            "password": password,
        })
        user = getattr(user_response, "user", None)
        
        if user:
            user_id = user.id
            #supabase.table("profiles").insert({
                #"id": user_id, 
                #"email": email,
                #"full_name": name, 
                #"role": "supervisor",
            #}).execute()

            st.success("Registro exitoso. Revisa tu correo electrónico para verificar tu cuenta. Recargando...")
            st.info("⚠️ Si no recibes el correo, verifica la configuración SMTP en el panel de Supabase.")
        else:
             st.error("Error al registrar: No se pudo crear el usuario en el servicio de autenticación.")

    except Exception as e:
        st.error(f"Error al registrar: {e}")

def request_password_reset(email):
    """Solicita un enlace para restablecer la contraseña validando primero el correo."""
    if not email:
        st.warning("⚠️ Por favor, ingresa un correo electrónico.")
        return

    try:
        # 1. VALIDACIÓN: Consultar si el correo existe en la tabla 'profiles'
        # Usamos .maybe_single() o .execute() para verificar si hay datos
        user_check = supabase.table("profiles").select("email").eq("email", email).execute()
        
        if not user_check.data:
            st.error("❌ El correo ingresado no está registrado en nuestra base de datos.")
            return

        # 2. PROCESO: Si existe, solicitamos el enlace a Supabase
        supabase.auth.reset_password_for_email(
            email, 
            {"redirect_to": REDIRECT_URL}
        )
        
        st.success(f"📧 ¡Enlace enviado! Hemos mandado las instrucciones a **{email}**.")
        st.info("Nota: Revisa tu carpeta de correos no deseados (spam) si no lo ves en unos minutos.")

    except Exception as e:
        st.error(f"Hubo un error al procesar la solicitud: {e}")

def process_direct_password_update(email, old_p, new_p, rep_p):
    """Actualiza la contraseña validando la antigua y redirige al login."""
    password_regex = r"^(?=.*[A-Z])(?=.*\d).{6,}$"
    
    if new_p != rep_p:
        st.error("❌ Las nuevas contraseñas no coinciden.")
        return
    if not re.match(password_regex, new_p):
        st.error("⚠️ La contraseña debe tener min. 6 caracteres, una mayúscula y un número.")
        return

    try:
        # 1. Validar que el usuario existe en la tabla profiles
        user_check = supabase.table("profiles").select("id").eq("email", email).execute()
        if not user_check.data:
            st.error("📧 Este correo no está registrado.")
            return

        # 2. Login técnico para validar la clave antigua
        supabase.auth.sign_in_with_password({"email": email, "password": old_p})
        
        # 3. Actualizar a la nueva
        supabase.auth.update_user({"password": new_p})
        
        st.success("✅ Actualización exitosa.")
        
        # CUMPLIENDO TU INSTRUCCIÓN: Redirigir al Login
        time.sleep(2)
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()
    except Exception:
        st.error("❌ La contraseña antigua es incorrecta.")        

def handle_logout():
    """Cierra la sesión de Supabase y limpia el estado local."""
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    st.rerun() 
    
# ============================================================
# 5. FUNCIONES DE UI (Interfaz de Usuario) - Renderizado
# ============================================================

def render_login_form():
    with st.form("login_form", clear_on_submit=False):
        st.text_input("Correo", key="login_email")
        st.text_input("Contraseña", type="password", key="login_password")
        if st.form_submit_button("Iniciar Sesión"):
            sign_in_manual(st.session_state.login_email, st.session_state.login_password)

def render_signup_form():
    with st.form("signup_form", clear_on_submit=True):
        st.text_input("Nombre completo", key="signup_name")
        st.text_input("Correo", key="signup_email")
        st.text_input("Contraseña (mín. 6 caracteres)", type="password", key="signup_password")
        if st.form_submit_button("Registrarse"):
            if st.session_state.signup_name and st.session_state.signup_email and st.session_state.signup_password:
                sign_up(st.session_state.signup_email, st.session_state.signup_password, st.session_state.signup_name)
            else:
                st.error("Completa todos los campos.")


def render_password_reset_form():
    st.markdown("### ¿Cómo deseas restablecer tu clave?")
    
    # Selector de método
    metodo = st.radio(
        "Selecciona una opción:", 
        ["Olvidé mi contraseña (Correo)", "Tengo mi clave antigua (Cambio directo)"], 
        horizontal=True
    )

    st.divider()

    if metodo == "Olvidé mi contraseña (Correo)":
        # OPCIÓN 1: RECUPERACIÓN POR CORREO
        with st.form("reset_email_form", clear_on_submit=True):
            email = st.text_input("Correo registrado", key="email_forgot_input")
            if st.form_submit_button("Solicitar Enlace de Recuperación"):
                if email:
                    # Esta función usa la DIRECT_URL que definimos
                    request_password_reset(email)
                else:
                    st.warning("Debes ingresar un correo.")
    
    else:
        # OPCIÓN 2: CAMBIO DIRECTO (Si recuerda la anterior)
        with st.form("direct_update_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                email_d = st.text_input("Correo electrónico")
                old_p = st.text_input("Contraseña actual", type="password")
            with col2:
                new_p = st.text_input("Nueva contraseña", type="password")
                rep_p = st.text_input("Confirmar nueva contraseña", type="password")
            
            if st.form_submit_button("Actualizar Contraseña Ahora"):
                # Esta función valida la clave vieja y luego redirige al login
                process_direct_password_update(email_d, old_p, new_p, rep_p)

def render_auth_page():
    """Renderiza la página de autenticación (SOLO Email/Pass de Supabase)."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        st.markdown("---")

        st.markdown("<p style='text-align: center; font-style: italic; color: #666;'>Ingresa con tus credenciales</p>", unsafe_allow_html=True)
        st.markdown("---")

        tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"])
        with tabs[0]:
            st.subheader("Ingreso Manual")
            render_login_form()
        with tabs[1]:
            st.subheader("Crear Cuenta")
            render_signup_form()
        with tabs[2]:
            st.subheader("Restablecer")
            render_password_reset_form()

def render_sidebar():
    """Renderiza la barra lateral con información de la sesión y navegación."""
    
    current_page = st.session_state.get("current_page", "Mi Perfil") 
    user_role = st.session_state.get('user_role', 'guest')
    
    with st.sidebar:
        col1, col2 = st.columns([1, 3])
        with col1:
            avatar_url = st.session_state.get("avatar_url")
            if not avatar_url:
                avatar_url = "https://placehold.co/100x100/A0A0A0/ffffff?text=U"
            
            st.markdown(f"""
                <style>
                    .sidebar-img {{
                        border-radius: 50%;
                        width: 60px;
                        height: 60px;
                        object-fit: cover;
                        border: 2px solid #007ACC;
                    }}
                </style>
                <img src="{avatar_url}" class="sidebar-img">
            """, unsafe_allow_html=True)

        with col2:
            st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
            st.caption(f"Rol: **{user_role.capitalize()}**")

        st.markdown("---")
        st.markdown("### Navegación")
        
        icon_map = {
            "Mi Perfil": "👤",
            "Dashboard": "📊",
            "Gestión de Empleados": "👥",
            "Predicción desde Archivo": "📁",
            "Predicción Manual": "✏️",
            "Reconocimiento": "⭐",
            "Historial de Encuesta": "📜"
        }
        
        PAGES_FILTRADAS = []
        for page in PAGES:
            if page == "Gestión de Empleados" and user_role not in ["admin", "supervisor"]:
                continue
            PAGES_FILTRADAS.append(page)

        for page in PAGES_FILTRADAS:
            icon = icon_map.get(page, "➡️")
            button_style = "primary" if current_page == page else "secondary"
            
            st.button(
                f"{icon} {page}", 
                key=f"nav_{page}", 
                use_container_width=True, 
                type=button_style,
                on_click=set_page, 
                args=(page,)
            )
            
        st.markdown("---")
        st.markdown(f"**Cuenta:** `{st.session_state.get('user_email', 'Desconocido')}`")
        
        if st.button("Cerrar Sesión", use_container_width=True):
            handle_logout()

        if user_role in ["admin", "supervisor"]: 
            st.markdown("---")
            st.markdown("### ⚙️ Control de Encuestas")
            render_survey_control_panel(supabase)


# ============================================================
# 6. CONTROL DE FLUJO PRINCIPAL
# ============================================================

session_is_active = check_session()

if session_is_active:
    render_sidebar()
    
    page_map = {
        "Mi Perfil": lambda: render_profile_page(supabase, request_password_reset),
        "Dashboard": render_rotacion_dashboard,
        "Gestión de Empleados":lambda: render_employee_management_page(), 
        "Predicción desde Archivo": render_predictor_page,
        "Predicción Manual":render_manual_prediction_tab,
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

