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
        st.error("ERROR: Faltan credenciales en secrets.toml.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

PAGES = [
    "Mi Perfil", "Dashboard", "Gestión de Empleados", 
    "Predicción desde Archivo", "Predicción Manual",
    "Reconocimiento", "Historial de Encuesta"
]

# ============================================================
# 2. FUNCIONES DE PERFIL (Autorización y Carga Rápida)
# ============================================================

def _fetch_and_set_user_profile(user_id: str, email: str):
    """Establece el estado de sesión sin redundancias."""
    st.session_state["authenticated"] = True
    st.session_state["user_id"] = user_id
    st.session_state["user_email"] = email
    
    try:
        # Usamos maybe_single para obtener el objeto directamente o None
        response = supabase.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
        
        if response.data:
            profile = response.data
            st.session_state.update({
                "user_role": profile.get("role", "guest"),
                "full_name": profile.get("full_name") or email.split('@')[0],
            })
            return True
        else:
            st.session_state.update({"user_role": "guest", "full_name": email.split('@')[0]})
            return True
    except Exception:
        return False

# ============================================================
# 3. AUTENTICACIÓN OPTIMIZADA (Sin Delays)
# ============================================================

def set_page(page_name):
    st.session_state.current_page = page_name

def check_session() -> bool:
    """Verifica sesión. Si ya está autenticado localmente, no consulta a la nube."""
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Mi Perfil"
    
    # Optimizador: Si ya marcamos authenticated, saltamos la consulta a Supabase
    if st.session_state.get("authenticated"):
        return True

    try:
        user_response = supabase.auth.get_user()
        if user_response and user_response.user:
            return _fetch_and_set_user_profile(user_response.user.id, user_response.user.email)
    except:
        pass

    st.session_state.update({"authenticated": False, "user_role": "guest"})
    return False

def sign_in_manual(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email.strip().lower(), "password": password})
        if res.user:
            _fetch_and_set_user_profile(res.user.id, res.user.email)
            st.rerun() # Redirección inmediata
    except Exception:
        st.error("❌ Credenciales inválidas.")

def sign_up(email, password, name):
    """Valida si existe el correo antes de intentar registrar."""
    email_limpio = email.strip().lower()
    try:
        # VALIDACIÓN RÁPIDA: ¿Ya existe en perfiles?
        exists = supabase.table("profiles").select("id").eq("email", email_limpio).maybe_single().execute()
        if exists.data:
            st.error(f"❌ El correo '{email_limpio}' ya está registrado.")
            return

        res = supabase.auth.sign_up({"email": email_limpio, "password": password})
        if res.user:
            # Crear perfil base inmediatamente para evitar inconsistencias
            supabase.table("profiles").insert({
                "id": res.user.id, "email": email_limpio, "full_name": name, "role": "guest"
            }).execute()
            st.success("✅ Registro exitoso. Verifica tu correo.")
        else:
            st.error("❌ No se pudo crear el usuario.")
    except Exception as e:
        st.error(f"Error: {e}")

def handle_logout():
    supabase.auth.sign_out()
    st.session_state.clear()
    st.rerun()

# ============================================================
# 5. UI (Recuperación con OTP y Cambio Directo)
# ============================================================

def render_password_reset_form():
    st.markdown("### 🛠️ Gestión de Credenciales")
    metodo = st.radio("Opción:", ["Olvidé mi contraseña (OTP)", "Cambio directo"], horizontal=True)
    st.divider()

    if metodo == "Olvidé mi contraseña (OTP)":
        if "recovery_step" not in st.session_state: st.session_state.recovery_step = 1

        if st.session_state.recovery_step == 1:
            with st.form("otp_req"):
                email = st.text_input("Correo institucional")
                if st.form_submit_button("Enviar Código"):
                    email_l = email.strip().lower()
                    # Validar existencia antes de enviar
                    check = supabase.table("profiles").select("email").eq("email", email_l).maybe_single().execute()
                    if check.data:
                        supabase.auth.reset_password_for_email(email_l)
                        st.session_state.temp_email = email_l
                        st.session_state.recovery_step = 2
                        st.rerun()
                    else:
                        st.error("❌ Correo no encontrado.")

        elif st.session_state.recovery_step == 2:
            st.info(f"Código enviado a: {st.session_state.temp_email}")
            with st.form("otp_ver"):
                otp = st.text_input("Código", max_chars=10)
                n_p = st.text_input("Nueva contraseña", type="password")
                c_p = st.text_input("Confirmar", type="password")
                if st.form_submit_button("Validar y Cambiar"):
                    if len(n_p) >= 8 and n_p == c_p:
                        try:
                            supabase.auth.verify_otp({"email": st.session_state.temp_email, "token": otp.strip(), "type": "recovery"})
                            supabase.auth.update_user({"password": n_p})
                            st.balloons()
                            st.success("✅ Éxito. Redirigiendo al login...")
                            time.sleep(1)
                            handle_logout() # Limpia y manda al login
                        except: st.error("❌ Código inválido.")
                    else: st.error("❌ Validar longitud o coincidencia.")
            if st.button("⬅️ Volver"):
                st.session_state.recovery_step = 1
                st.rerun()
    else:
        with st.form("direct_form"):
            e_d = st.text_input("Correo")
            o_p = st.text_input("Clave actual", type="password")
            n_p = st.text_input("Nueva clave", type="password")
            r_p = st.text_input("Repetir clave", type="password")
            if st.form_submit_button("Actualizar"):
                process_direct_password_update(e_d, o_p, n_p, r_p)

# ... (Las funciones de renderizado de formularios y sidebar se mantienen igual)
def render_auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso")
        tabs = st.tabs(["Login", "Registro", "Recuperar"])
        with tabs[0]: render_login_form()
        with tabs[1]: render_signup_form()
        with tabs[2]: render_password_reset_form()

# ============================================================
# 6. FLUJO PRINCIPAL
# ============================================================

if check_session():
    # Render Sidebar y Páginas
    from survey_control_logic import render_survey_control_panel # Import local
    
    # Lógica de renderizado de sidebar aquí...
    # (Usar tu código original de render_sidebar)
    
    # Navegación
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


