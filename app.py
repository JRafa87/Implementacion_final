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
        st.error("ERROR: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml. La autenticación fallará.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()


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
    
    # 1. Definimos un estado inicial seguro
    st.session_state["authenticated"] = True
    st.session_state["user_id"] = user_id
    st.session_state["user_email"] = email
    
    # Valores por defecto por si no hay perfil en la DB
    st.session_state["user_role"] = "guest"
    st.session_state["full_name"] = email.split('@')[0]

    try:
        # 2. Consultamos la base de datos
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        
        if response.data and len(response.data) > 0:
            profile = response.data[0] # <--- Ahora SÍ extraemos los datos
            
            # 3. Extraemos el rol y el nombre
            role_db = profile.get("role", "guest")
            name_db = profile.get("full_name")
            
            # Si el nombre en la DB es nulo o genérico, usamos el email
            if not name_db or name_db == "Usuario":
                name_db = email.split('@')[0]
                
            # 4. Actualizamos el estado de sesión con datos REALES de la DB
            st.session_state.update({
                "user_role": role_db,
                "full_name": name_db,
            })
            return True
        else:
            # El usuario existe en Auth pero no tiene fila en la tabla 'profiles'
            return True
            
    except Exception as e:
        st.error(f"Error crítico al cargar perfil: {e}")
        return False


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
    """Solicita el enlace de recuperación limpiando el texto del correo."""
    if not email:
        st.warning("⚠️ Por favor, ingresa un correo electrónico.")
        return

    # Limpiamos el correo: quitamos espacios y pasamos a minúsculas
    email_limpio = email.strip().lower()

    try:
        # Buscamos en la tabla 'profiles'
        user_check = supabase.table("profiles").select("email").eq("email", email_limpio).execute()
        
        if user_check.data:
            # Si existe, enviamos el correo usando la DIRECT_URL
            supabase.auth.reset_password_for_email(
                email_limpio, 
                {"redirect_to": DIRECT_URL_1}
            )
            st.success(f"📧 Enlace enviado a {email_limpio}")
            st.info("Revisa tu bandeja de entrada y la carpeta de spam.")
        else:
            # Si llega aquí, es que el correo no coincide exactamente con la tabla
            st.error(f"❌ El correo '{email_limpio}' no figura en nuestra base de datos.")
            st.info("Asegúrate de que no haya espacios extra al escribirlo.")

    except Exception as e:
        st.error(f"Error de conexión: {e}")

def process_direct_password_update(email, old_p, new_p, rep_p):
    """Actualiza la contraseña validando la antigua y confirma en pantalla."""
    # Validación: Mínimo 8 caracteres, 1 Mayúscula y 1 Número
    password_regex = r"^(?=.*[A-Z])(?=.*\d).{8,}$"
    
    if new_p != rep_p:
        st.error("❌ Las nuevas contraseñas no coinciden.")
        return
    if not re.match(password_regex, new_p):
        st.error("⚠️ Requisitos: Mínimo 8 caracteres, una mayúscula y un número.")
        return

    try:
        # 1. Login técnico para validar que la clave antigua es correcta
        supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": old_p})
        
        # 2. Si el login fue exitoso, actualizamos a la nueva clave
        supabase.auth.update_user({"password": new_p})
        
        # 3. ÉXITO: Solo confirmamos (No redirigimos al login aquí)
        st.balloons()
        st.success("✅ ¡Contraseña actualizada con éxito! Puedes seguir navegando.")
        
    except Exception:
        st.error("❌ Error: La contraseña actual es incorrecta o el usuario no existe.")     

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
    st.markdown("### 🛠️ Gestión de Credenciales")
    
    # Selector de método
    metodo = st.radio(
        "Selecciona una opción:", 
        ["Olvidé mi contraseña (Código OTP)", "Cambio directo (Conozco mi clave actual)"], 
        horizontal=True
    )
    st.divider()

    # --- OPCIÓN 1: RECUPERACIÓN POR CÓDIGO (Redirige al Login) ---
    if metodo == "Olvidé mi contraseña (Código OTP)":
        if "recovery_step" not in st.session_state:
            st.session_state.recovery_step = 1

        if st.session_state.recovery_step == 1:
            with st.form("otp_request_form"):
                email = st.text_input("Ingresa tu correo institucional")
                if st.form_submit_button("Enviar Código de Verificación"):
                    if email:
                        try:
                            supabase.auth.reset_password_for_email(email.strip().lower())
                            st.session_state.temp_email = email.strip().lower()
                            st.session_state.recovery_step = 2
                            st.success("📧 Código enviado. Revisa tu correo.")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                    else:
                        st.warning("Por favor, ingresa un correo.")

        elif st.session_state.recovery_step == 2:
            # TODO ESTE BLOQUE AHORA TIENE LA INDENTACIÓN CORRECTA
            st.info(f"Ingresa el código enviado a: {st.session_state.temp_email}")
            
            with st.form("otp_verify_form"):
                # max_chars=10 para ser flexible con códigos de 6 u 8 dígitos
                otp_code = st.text_input("Código de verificación", max_chars=10)
                new_pass = st.text_input("Nueva contraseña", type="password")
                conf_pass = st.text_input("Confirma nueva contraseña", type="password")
                
                submit_res = st.form_submit_button("Validar y Cambiar Contraseña")
                
                if submit_res:
                    # 1. Validaciones de seguridad (8+ caracteres, Mayúscula, Número)
                    if len(new_pass) >= 8 and re.search(r"[A-Z]", new_pass) and re.search(r"\d", new_pass):
                        if new_pass == conf_pass:
                            try:
                                # 2. Verificación del código OTP
                                supabase.auth.verify_otp({
                                    "email": st.session_state.temp_email, 
                                    "token": otp_code.strip(), 
                                    "type": "recovery"
                                })
                                
                                # 3. Actualización de la contraseña en Supabase
                                supabase.auth.update_user({"password": new_pass})
                                
                                # 2. Feedback visual
                                st.balloons()
                                st.success("✅ ¡Contraseña actualizada con éxito!")
                                st.info("Tus datos y permisos se mantuvieron. Por seguridad, ingresa con tu nueva clave.")
                                
                                st.success("✅ ¡Contraseña actualizada con éxito!")
                                time.sleep(2)
                                
                                # 4. REDIRECCIÓN AL LOGIN
                                st.session_state.clear()
                                supabase.auth.sign_out()
                                st.rerun()
                            except Exception:
                                st.error("❌ Código incorrecto o expirado.")
                        else:
                            st.error("❌ Las contraseñas no coinciden.")
                    else:
                        st.error("❌ La clave debe tener 8+ caracteres, 1 Mayúscula y 1 Número.")

            # Botón para retroceder dentro del paso 2
            if st.button("⬅️ Volver a pedir código"):
                st.session_state.recovery_step = 1
                st.rerun()

    # --- OPCIÓN 2: CAMBIO DIRECTO (Se queda en la app) ---
    else:
        with st.form("direct_update_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                email_d = st.text_input("Correo electrónico")
                old_p = st.text_input("Contraseña actual", type="password")
            with col2:
                new_p = st.text_input("Nueva contraseña", type="password")
                rep_p = st.text_input("Confirmar nueva contraseña", type="password")
            
            if st.form_submit_button("Actualizar Contraseña Ahora"):
                # Esta función debe estar definida en tu código para procesar el cambio
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

