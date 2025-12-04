import streamlit as st
from supabase import create_client
import time

# ============================================================
# SUPABASE
# ============================================================
@st.cache_resource
def get_supabase():
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")

    if not url or not key:
        st.error("❌ Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml")
        st.stop()

    return create_client(url, key)

# ============================================================
# AUTENTICACIÓN
# ============================================================
def sign_in_manual(email, password):
    supabase = get_supabase()
    try:
        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        profile = (
            supabase.from("profiles")
            .select("role")
            .eq("id", res.user.id)
            .single()
            .execute()
        )

        st.session_state["authenticated"] = True
        st.session_state["user_id"] = res.user.id
        st.session_state["user_role"] = profile.data.get("role", "guest")

        st.success("Inicio de sesión exitoso.")
        time.sleep(0.8)
        st.rerun()

    except Exception as e:
        st.error(f"Error al iniciar sesión: {e}")

def sign_up(email, password, name):
    supabase = get_supabase()
    try:
        supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {"full_name": name, "role": "supervisor"}
            }
        })
        st.success("Registro exitoso. Revisa tu correo.")
    except Exception as e:
        st.error(f"Error al registrar: {e}")

def sign_in_with_google():
    supabase = get_supabase()
    redirect_url = st.secrets.get("REDIRECT_URL", "http://localhost:8501")
    try:
        url = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {"redirectTo": redirect_url}
        }).url
        st.write("Inicia sesión con Google aquí:", url)
    except Exception as e:
        st.error(f"Error Google OAuth: {e}")

def handle_logout():
    st.session_state["authenticated"] = False
    st.session_state["user_role"] = "guest"
    st.rerun()

# ============================================================
# UI LOGIN
# ============================================================
def render_login_form():
    st.subheader("Iniciar Sesión")

    sign_in_with_google()

    st.markdown("---")

    email = st.text_input("Correo")
    password = st.text_input("Contraseña", type="password")

    if st.button("Iniciar"):
        sign_in_manual(email, password)

# ============================================================
# UI SIGNUP
# ============================================================
def render_signup_form():
    st.subheader("Registrarse")

    name = st.text_input("Nombre completo")
    email = st.text_input("Correo electrónico")
    password = st.text_input("Contraseña", type="password")

    if st.button("Crear Cuenta"):
        if name and email and password:
            sign_up(email, password, name)
        else:
            st.error("Completa todos los campos.")

# ============================================================
# AUTH PAGE
# ============================================================
def render_auth_page():
    tabs = st.tabs(["Iniciar Sesión", "Registrarse"])
    with tabs[0]:
        render_login_form()
    with tabs[1]:
        render_signup_form()

