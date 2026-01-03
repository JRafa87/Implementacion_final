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
# 0. CONFIGURACIÓN
# ============================================================

st.set_page_config(page_title="App Deserción Laboral", layout="wide", initial_sidebar_state="expanded")

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key)

supabase = get_supabase()

# ============================================================
# 2. LÓGICA DE PERFIL Y SESIÓN
# ============================================================

def _fetch_and_set_user_profile(user_id: str, email: str):
    st.session_state.update({"authenticated": True, "user_id": user_id, "user_email": email})
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        if response.data:
            p = response.data[0]
            st.session_state.update({
                "user_role": p.get("role", "guest"),
                "full_name": p.get("full_name", email.split('@')[0]),
                "avatar_url": p.get("avatar_url", None)
            })
    except:
        pass
    return True

def check_session() -> bool:
    if st.session_state.get("authenticated"): return True
    try:
        user_res = supabase.auth.get_user()
        if user_res and user_res.user:
            return _fetch_and_set_user_profile(user_res.user.id, user_res.user.email)
    except: pass
    return False

# ============================================================
# 3. COMPONENTES DE INTERFAZ (AUTH)
# ============================================================

def render_auth_page():
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"])
        
        # --- TAB 1: LOGIN ---
        with tabs[0]:
            with st.form("login_form"):
                e = st.text_input("Correo")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Iniciar Sesión", use_container_width=True):
                    try:
                        res = supabase.auth.sign_in_with_password({"email": e.strip().lower(), "password": p})
                        if res.user:
                            _fetch_and_set_user_profile(res.user.id, res.user.email)
                            st.rerun()
                    except: st.error("Credenciales incorrectas")

        # --- TAB 2: REGISTRO ---
        with tabs[1]:
            st.subheader("Crear Cuenta")
            # Validación de correo fuera del form para evitar el error de Streamlit
            email_reg = st.text_input("Correo electrónico", key="reg_email_field")
            if email_reg:
                res = supabase.table("profiles").select("email").eq("email", email_reg.strip().lower()).execute()
                if res.data:
                    st.error(f"⚠️ El correo '{email_reg}' ya existe.")
                    st.session_state["block_reg"] = True
                else:
                    st.session_state["block_reg"] = False

            with st.form("signup_form_complete"):
                nombre = st.text_input("Nombre completo")
                pass1 = st.text_input("Contraseña (mín. 6 caracteres)", type="password")
                if st.form_submit_button("Registrarse", use_container_width=True):
                    if st.session_state.get("block_reg"):
                        st.error("Usa otro correo.")
                    elif nombre and email_reg and pass1:
                        try:
                            supabase.auth.sign_up({"email": email_reg, "password": pass1})
                            st.success("Revisa tu correo para verificar la cuenta.")
                        except Exception as e: st.error(f"Error: {e}")

        # --- TAB 3: RECUPERACIÓN ---
        with tabs[2]:
            st.subheader("Gestión de Credenciales")
            metodo = st.radio("Selecciona:", ["Olvidé mi contraseña (OTP)", "Cambio directo"], horizontal=True, key="reset_nav")
            
            if metodo == "Olvidé mi contraseña (OTP)":
                step = st.session_state.get("recovery_step", 1)
                if step == 1:
                    with st.form("step1_otp"):
                        mail = st.text_input("Correo institucional")
                        if st.form_submit_button("Enviar Código"):
                            try:
                                supabase.auth.reset_password_for_email(mail.strip().lower())
                                st.session_state.temp_email = mail.strip().lower()
                                st.session_state.recovery_step = 2
                                st.rerun()
                            except: st.error("Error al enviar")
                else:
                    st.info(f"Código enviado a {st.session_state.temp_email}")
                    with st.form("step2_otp"):
                        code = st.text_input("Código OTP")
                        n_p = st.text_input("Nueva contraseña", type="password")
                        c_p = st.text_input("Confirmar contraseña", type="password")
                        if st.form_submit_button("Actualizar"):
                            if n_p == c_p and len(n_p) >= 8:
                                try:
                                    supabase.auth.verify_otp({"email": st.session_state.temp_email, "token": code, "type": "recovery"})
                                    supabase.auth.update_user({"password": n_p})
                                    st.success("¡Éxito! Iniciando sesión...")
                                    time.sleep(2)
                                    st.session_state.clear()
                                    st.rerun()
                                except: st.error("Código inválido")
                    if st.button("⬅️ Volver"):
                        st.session_state.recovery_step = 1
                        st.rerun()
            
            else:
                with st.form("direct_form"):
                    d_mail = st.text_input("Correo electrónico")
                    d_old = st.text_input("Contraseña actual", type="password")
                    d_new = st.text_input("Nueva contraseña", type="password")
                    d_rep = st.text_input("Repetir nueva contraseña", type="password")
                    if st.form_submit_button("Actualizar Ahora"):
                        if d_new == d_rep:
                            try:
                                supabase.auth.sign_in_with_password({"email": d_mail, "password": d_old})
                                supabase.auth.update_user({"password": d_new})
                                st.success("Contraseña cambiada.")
                            except: st.error("Datos incorrectos")

# ============================================================
# 4. SIDEBAR Y PRINCIPAL
# ============================================================

def render_sidebar():
    role = st.session_state.get("user_role", "guest")
    email = st.session_state.get("user_email", "")
    name = st.session_state.get("full_name", "Usuario")
    
    with st.sidebar:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown(f'<img src="https://placehold.co/100x100?text=U" style="border-radius:50%; width:60px; border:2px solid #007ACC;">', unsafe_allow_html=True)
        with col2:
            st.title(f"👋 {name.split()[0]}")
            st.caption(f"Rol: **{role.capitalize()}**")
        
        st.markdown("---")
        curr = st.session_state.get("current_page", "Mi Perfil")
        for p in ["Mi Perfil", "Dashboard", "Gestión de Empleados", "Predicción desde Archivo", "Predicción Manual", "Reconocimiento", "Historial de Encuesta"]:
            if p == "Gestión de Empleados" and role not in ["admin", "supervisor"]: continue
            if st.button(p, use_container_width=True, type="primary" if curr == p else "secondary"):
                st.session_state.current_page = p
                st.rerun()
        
        st.markdown("---")
        st.caption(f"Cuenta: `{email}`")
        if st.button("Cerrar Sesión", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.clear()
            st.rerun()

# --- FLUJO PRINCIPAL ---
if check_session():
    render_sidebar()
    page = st.session_state.get("current_page", "Mi Perfil")
    
    if page == "Mi Perfil": render_profile_page(supabase, None)
    elif page == "Dashboard": render_rotacion_dashboard()
    elif page == "Gestión de Empleados": render_employee_management_page()
    elif page == "Predicción desde Archivo": render_predictor_page()
    elif page == "Predicción Manual": render_manual_prediction_tab()
    elif page == "Reconocimiento": render_recognition_page()
    elif page == "Historial de Encuesta": historial_encuestas_module()
else:
    render_auth_page()
