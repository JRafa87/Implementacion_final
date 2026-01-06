import streamlit as st
from typing import Optional
from supabase import create_client, Client
import datetime
import pandas as pd
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
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key)

supabase = get_supabase()

PAGES = ["Mi Perfil", "Dashboard", "Gestión de Empleados", "Predicción desde Archivo", "Predicción Manual", "Reconocimiento" , "Historial de Encuesta"]

# ============================================================
# 2. FUNCIONES DE APOYO Y PERFIL (OPTIMIZADAS)
# ============================================================

def _fetch_and_set_user_profile(user_id: str, email: str):
    """Fuerza la escritura inmediata en session_state."""
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        role = "guest"
        full_name = email.split('@')[0]
        if response.data:
            profile = response.data[0]
            role = profile.get("role", "guest")
            full_name = profile.get("full_name") or full_name

        st.session_state["authenticated"] = True
        st.session_state["user_id"] = user_id
        st.session_state["user_email"] = email
        st.session_state["user_role"] = role
        st.session_state["full_name"] = full_name
        return True
    except:
        return False

def check_session() -> bool:
    if st.session_state.get("authenticated"):
        return True
    try:
        # Verificación directa con el servidor
        user_res = supabase.auth.get_user()
        if user_res and user_res.user:
            return _fetch_and_set_user_profile(user_res.user.id, user_res.user.email)
    except:
        pass
    return False

def handle_logout():
    supabase.auth.sign_out()
    st.session_state.clear()
    st.cache_data.clear()
    st.rerun()

# ============================================================
# 4. COMPONENTES DE INTERFAZ (UI OPTIMIZADA)
# ============================================================

def render_login_form():
    with st.container():
        # Contenedor para mensajes que se limpia en cada interacción
        msg = st.empty()
        
        email = st.text_input("Correo electrónico", key="login_email").strip().lower()
        password = st.text_input("Contraseña", type="password", key="login_pass")
        
        if st.button("Iniciar Sesión", use_container_width=True, type="primary"):
            if not email or not password:
                msg.warning("Por favor, complete los campos.")
                return

            try:
                # 1. Intentar login
                auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                
                if auth_res.user:
                    # 2. ÉXITO: Sincronizar datos inmediatamente
                    _fetch_and_set_user_profile(auth_res.user.id, auth_res.user.email)
                    msg.success("✅ Acceso correcto. Iniciando...")
                    time.sleep(0.6) # Tiempo para que Supabase asiente la sesión
                    st.rerun()
                else:
                    msg.error("No se pudo iniciar sesión. Verifique su cuenta.")
            except Exception as e:
                # 3. Solo mostrar error si Supabase realmente rechaza las credenciales
                error_msg = str(e).lower()
                if "invalid login credentials" in error_msg:
                    msg.error("Contraseña o correo incorrectos.")
                elif "email not confirmed" in error_msg:
                    msg.error("Por favor, confirma tu correo electrónico antes de entrar.")
                else:
                    msg.error(f"Error de conexión: Intentelo de nuevo.")

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
                except Exception as e: st.error(f"Error: {e}")
            else:
                st.error("Por favor complete todos los datos correctamente.")

def render_password_reset_form():
    st.subheader("🛠️ Gestión de Credenciales")
    metodo = st.radio("Método:", ["Código OTP (Olvido)", "Cambio Directo"], horizontal=True)

    if metodo == "Código OTP (Olvido)":
        if "recovery_step" not in st.session_state: st.session_state.recovery_step = 1
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
                        supabase.auth.verify_otp({"email": st.session_state.temp_email, "token": otp_code.strip(), "type": "recovery"})
                        supabase.auth.update_user({"password": new_pass})
                        st.success("Cambiado correctamente.")
                        time.sleep(1.2)
                        handle_logout() 
                    except: st.error("Código inválido.")
    
    elif metodo == "Cambio Directo":
        with st.form("direct_change_form"):
            old_p = st.text_input("Contraseña anterior", type="password")
            new_p = st.text_input("Nueva contraseña", type="password")
            conf_p = st.text_input("Confirmar nueva contraseña", type="password")
            if st.form_submit_button("Actualizar", use_container_width=True):
                if new_p != conf_p: st.error("Las contraseñas no coinciden.")
                elif len(new_p) < 8: st.error("Mínimo 8 caracteres.")
                else:
                    try:
                        supabase.auth.update_user({"password": new_p})
                        st.success("Actualizado correctamente.")
                        time.sleep(1.2)
                        handle_logout()
                    except Exception as e: st.error(f"Error: {e}")

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
    user_role = st.session_state.get('user_role', 'guest')
    with st.sidebar:
        st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
        st.caption(f"Rol: **{user_role.capitalize()}**")
        st.markdown("---")
        for page in PAGES:
            if page == "Gestión de Empleados" and user_role not in ["admin", "supervisor"]: continue
            st.button(f"➡️ {page}", key=f"nav_{page}", use_container_width=True, 
                      type="primary" if current_page == page else "secondary", on_click=set_page, args=(page,))
        st.markdown("---")
        if st.button("Cerrar Sesión", use_container_width=True): handle_logout()

# ============================================================
# 6. EJECUCIÓN MAESTRA
# ============================================================

if check_session():
    render_sidebar()
    # Importaciones dinámicas o mapeo de páginas aquí...
    st.write(f"Cargando página: {st.session_state.get('current_page', 'Mi Perfil')}")
else:
    render_auth_page()