import streamlit as st
from supabase import create_client
import time

# Supabase
@st.cache_resource
def get_supabase():
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("Faltan SUPABASE_URL o SUPABASE_KEY")
        st.stop()
    return create_client(url, key)

# Login manual
def sign_in_manual(email, password):
    supabase = get_supabase()
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        profile = supabase.from("profiles").select("role").eq("id", res.user.id).single().execute()
        st.session_state["authenticated"] = True
        st.session_state["user_id"] = res.user.id
        st.session_state["user_role"] = profile.data.get("role", "guest")
        st.success("Inicio de sesión exitoso")
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"Error al iniciar sesión: {e}")

# Registro
def sign_up(email, password, name):
    supabase = get_supabase()
    try:
        supabase.auth.sign_up({"email": email, "password": password,
                               "options": {"data": {"full_name": name, "role": "supervisor"}}})
        st.success("Registro exitoso")
    except Exception as e:
        st.error(f"Error al registrar: {e}")

# Logout
def handle_logout():
    st.session_state["authenticated"] = False
    st.session_state["user_role"] = "guest"
    st.rerun()

# Login UI
def render_login_form():
    st.subheader("Iniciar Sesión")
    st.write("Botón Google OAuth pendiente de estilo")
    email = st.text_input("Correo")
    password = st.text_input("Contraseña", type="password")
    if st.button("Iniciar"):
        sign_in_manual(email, password)

# Registro UI
def render_signup_form():
    st.subheader("Registrarse")
    name = st.text_input("Nombre completo")
    email = st.text_input("Correo")
    password = st.text_input("Contraseña", type="password")
    if st.button("Crear Cuenta"):
        if name and email and password:
            sign_up(email, password, name)
        else:
            st.error("Completa todos los campos")

# Auth page
def render_auth_page():
    tabs = st.tabs(["Iniciar Sesión", "Registrarse"])
    with tabs[0]:
        render_login_form()
    with tabs[1]:
        render_signup_form()

