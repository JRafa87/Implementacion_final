import streamlit as st
from supabase import create_client, Client
from typing import Optional
import datetime

# ==============================
# IMPORTS DE TUS MÓDULOS
# ==============================
from profile import render_profile_page
from employees_crud import render_employee_management_page
from app_reconocimiento import render_recognition_page
from dashboard_rotacion import render_rotacion_dashboard
from survey_control_logic import render_survey_control_panel
from prediccion_manual_module import render_manual_prediction_tab
from attrition_predictor import render_predictor_page
from encuestas_historial import historial_encuestas_module

# ==============================
# CONFIGURACIÓN STREAMLIT
# ==============================
st.set_page_config(
    page_title="App Deserción Laboral",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================
# SUPABASE
# ==============================
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("❌ Falta configuración de Supabase en secrets.toml")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

# ==============================
# PÁGINAS
# ==============================
PAGES = [
    "Mi Perfil",
    "Dashboard",
    "Gestión de Empleados",
    "Predicción desde Archivo",
    "Predicción Manual",
    "Reconocimiento",
    "Historial de Encuesta"
]

# ==========================================================
# AUTENTICACIÓN Y SESIÓN
# ==========================================================
def _fetch_and_set_user_profile(user_id: str, email: str) -> bool:

    default_state = {
        "authenticated": True,
        "user_id": user_id,
        "user_email": email,
        "user_role": "guest",
        "full_name": email.split("@")[0],
        "avatar_url": None,
        "date_of_birth": None
    }

    try:
        res = (
            supabase
            .table("profiles")
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        if res.data:
            p = res.data[0]

            dob = None
            if p.get("date_of_birth"):
                dob = datetime.datetime.strptime(
                    p["date_of_birth"], "%Y-%m-%d"
                ).date()

            st.session_state.update({
                "authenticated": True,
                "user_id": user_id,
                "user_email": email,
                "user_role": p.get("role", "guest"),
                "full_name": p.get("full_name") or email.split("@")[0],
                "avatar_url": p.get("avatar_url"),
                "date_of_birth": dob
            })
        else:
            st.session_state.update(default_state)

        return True

    except Exception:
        st.session_state.update(default_state)
        return True


def check_session() -> bool:

    if "current_page" not in st.session_state:
        st.session_state.current_page = "Mi Perfil"

    # Tokens desde URL (reset / verify)
    qp = st.query_params
    if qp.get("access_token") and qp.get("refresh_token"):
        try:
            supabase.auth.set_session(
                access_token=qp["access_token"],
                refresh_token=qp["refresh_token"]
            )
            st.experimental_set_query_params()
            st.rerun()
        except Exception:
            st.experimental_set_query_params()

    try:
        user_resp = supabase.auth.get_user()
        user = getattr(user_resp, "user", None)

        if user:
            return _fetch_and_set_user_profile(user.id, user.email)

    except Exception:
        pass

    st.session_state.update({
        "authenticated": False,
        "user_id": None,
        "user_email": None,
        "user_role": "guest",
        "full_name": "Usuario",
        "avatar_url": None,
        "date_of_birth": None
    })

    return False


def sign_in_manual(email, password):
    try:
        supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        st.success("✅ Sesión iniciada")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error: {e}")


def sign_up(email, password, name):
    try:
        res = supabase.auth.sign_up({
            "email": email,
            "password": password
        })

        user = getattr(res, "user", None)
        if not user:
            st.error("❌ No se pudo crear el usuario")
            return

        supabase.table("profiles").insert({
            "id": user.id,
            "email": email,
            "full_name": name,
            "role": "supervisor"
        }).execute()

        st.success("✅ Registro exitoso. Revisa tu correo.")
    except Exception as e:
        st.error(f"❌ {e}")


def request_password_reset(email):
    try:
        supabase.auth.reset_password_for_email(email)
        st.success("📩 Correo enviado")
    except Exception as e:
        st.error(f"❌ {e}")


def handle_logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    st.rerun()

# ==========================================================
# UI AUTENTICACIÓN
# ==========================================================
def render_login_form():
    with st.form("login"):
        email = st.text_input("Correo")
        password = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Iniciar sesión"):
            sign_in_manual(email, password)


def render_signup_form():
    with st.form("signup"):
        name = st.text_input("Nombre completo")
        email = st.text_input("Correo")
        password = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Registrarse"):
            if name and email and password:
                sign_up(email, password, name)
            else:
                st.warning("Completa todos los campos")


def render_reset_form():
    with st.form("reset"):
        email = st.text_input("Correo")
        if st.form_submit_button("Enviar enlace"):
            request_password_reset(email)


def render_auth_page():
    st.title("Acceso a la Plataforma")
    tabs = st.tabs(["Iniciar sesión", "Registrarse", "Recuperar contraseña"])

    with tabs[0]:
        render_login_form()
    with tabs[1]:
        render_signup_form()
    with tabs[2]:
        render_reset_form()

# ==========================================================
# SIDEBAR
# ==========================================================
def set_page(p):
    st.session_state.current_page = p


def render_sidebar():
    with st.sidebar:
        st.title(f"👋 {st.session_state.full_name}")
        st.caption(f"Rol: {st.session_state.user_role}")
        st.markdown("---")

        for p in PAGES:
            if p == "Gestión de Empleados" and st.session_state.user_role not in ["admin", "supervisor"]:
                continue
            st.button(
                p,
                use_container_width=True,
                on_click=set_page,
                args=(p,),
                type="primary" if st.session_state.current_page == p else "secondary"
            )

        st.markdown("---")
        st.caption(st.session_state.user_email)
        st.button("Cerrar sesión", on_click=handle_logout, use_container_width=True)

        if st.session_state.user_role in ["admin", "supervisor"]:
            st.markdown("---")
            render_survey_control_panel(supabase)

# ==========================================================
# FLUJO PRINCIPAL
# ==========================================================
if check_session():

    if not st.session_state.user_id:
        st.error("Sesión inválida")
        handle_logout()
        st.stop()

    render_sidebar()

    pages = {
        "Mi Perfil": lambda: render_profile_page(supabase, request_password_reset),
        "Dashboard": render_rotacion_dashboard,
        "Gestión de Empleados": render_employee_management_page,
        "Predicción desde Archivo": render_predictor_page,
        "Predicción Manual": render_manual_prediction_tab,
        "Reconocimiento": render_recognition_page,
        "Historial de Encuesta": historial_encuestas_module
    }

    pages.get(st.session_state.current_page, pages["Mi Perfil"])()

else:
    render_auth_page()
          

