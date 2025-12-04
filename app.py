import streamlit as st
from typing import Optional
import jwt
from supabase import create_client, Client
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.oauth2 import OAuth2Token
import asyncio
import httpx # Necesario para GoogleOAuth2

# ============================================================
# 0. CONFIGURACIÓN E INICIALIZACIÓN
# ============================================================

st.set_page_config(
    page_title="App Deserción Laboral",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modo testing (para usar localhost o la URL de despliegue)
testing_mode = st.secrets.get("testing_mode", False)

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

# Cliente de Google OAuth
try:
    client_id = st.secrets["client_id"]
    client_secret = st.secrets["client_secret"]
    redirect_url = (
        st.secrets["redirect_url_test"] if testing_mode else st.secrets["redirect_url"]
    )
    google_client = GoogleOAuth2(client_id=client_id, client_secret=client_secret)
except KeyError:
    st.warning("Advertencia: Faltan secretos de Google (client_id, etc.). Google OAuth no funcionará.")
    google_client = None

# ============================================================
# 1. FUNCIONES AUXILIARES DE GOOGLE OAUTH
# ============================================================

def _decode_google_token(token: str):
    """Decodifica el token JWT de Google sin verificar firma."""
    return jwt.decode(jwt=token, options={"verify_signature": False})

async def _get_authorization_url(client: GoogleOAuth2, redirect_url: str) -> str:
    """Genera la URL para iniciar el flujo OAuth de Google."""
    return await client.get_authorization_url(
        redirect_url,
        scope=["email"],
        extras_params={"access_type": "offline"},
    )

async def _get_access_token(client: GoogleOAuth2, redirect_url: str, code: str) -> OAuth2Token:
    """Obtiene el token de acceso usando el código de la URL."""
    return await client.get_access_token(code, redirect_url)

def _ensure_async_loop():
    """Asegura que haya un loop de asyncio en ejecución o crea uno nuevo."""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

def get_google_user_email() -> Optional[str]:
    """Maneja la respuesta de Google y obtiene el email del usuario."""
    if "google_email" in st.session_state:
        return st.session_state.google_email

    if google_client is None:
        return None

    try:
        code = st.query_params.get("code")
        if not code:
            return None

        # --- Manejo de asyncio seguro en Streamlit ---
        loop = _ensure_async_loop()
        
        if loop.is_running():
            # Ejecutar de forma concurrente si el loop ya está activo
            token = asyncio.run_coroutine_threadsafe(
                _get_access_token(google_client, redirect_url, code), loop
            ).result()
        else:
            # Ejecutar de forma síncrona si el loop no está activo
            token = loop.run_until_complete(_get_access_token(google_client, redirect_url, code))

        st.experimental_set_query_params()  # Limpiar params

        user_info = _decode_google_token(token["id_token"])
        st.session_state["google_email"] = user_info["email"]
        return user_info["email"]

    except Exception as e:
        print(f"Error silencioso de Google OAuth: {e}")
        return None

# ============================================================
# 2. FUNCIONES DE SUPABASE / ROLES (Autorización)
# ============================================================

def _get_user_role_from_db(user_id: Optional[str] = None, email: Optional[str] = None):
    """
    Obtiene el rol de un usuario desde la tabla 'profiles' de Supabase.
    Busca por user_id o por email.
    """
    st.session_state["user_role"] = "guest"
    st.session_state["user_id"] = None

    # Determinamos la columna y valor de búsqueda
    search_col = "id" if user_id else "email"
    search_val = user_id if user_id else email

    if search_val:
        try:
            # Ejecutamos la consulta
            response = supabase.table("profiles").select("role").eq(search_col, search_val).limit(1).execute()
        except Exception as e:
            print(f"Error al consultar Supabase por {search_col}: {e}")
            return
    else:
        return

    try:
        if response.data and len(response.data) > 0:
            profile = response.data[0]
            st.session_state["user_role"] = profile.get("role", "guest")
            st.session_state["user_id"] = user_id or None
    except Exception as e:
        print(f"Error procesando respuesta de Supabase: {e}")
        st.session_state["user_role"] = "guest"
        st.session_state["user_id"] = None

# ============================================================
# 3. FUNCIONES PRINCIPALES DE AUTENTICACIÓN HÍBRIDA
# ============================================================

def check_session_state_hybrid() -> bool:
    """Verifica sesión activa, priorizando Google sobre Supabase local."""
    if "authenticated" not in st.session_state:
        st.session_state.update({
            "authenticated": False,
            "user_role": "guest",
            "user_id": None,
            "user_email": None
        })

    # A. Intento de Google OAuth
    email_google = get_google_user_email()
    if email_google:
        st.session_state["authenticated"] = True
        st.session_state["user_email"] = email_google
        _get_user_role_from_db(email=email_google)
        return True

    # B. Intento de Supabase (Email/Contraseña)
    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        if user:
            st.session_state["authenticated"] = True
            st.session_state["user_email"] = user.email
            if st.session_state.get("user_id") != user.id:
                _get_user_role_from_db(user_id=user.id)
            return True
    except Exception:
        pass # No hay sesión Supabase válida

    # C. No autenticado
    st.session_state.update({
        "authenticated": False,
        "user_role": "guest",
        "user_id": None,
        "user_email": None
    })
    return False

def sign_in_manual(email, password):
    """Inicia sesión con Email/Contraseña."""
    try:
        supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.success("Inicio de sesión exitoso. Recargando...")
        st.experimental_rerun()
    except Exception as e:
        st.error(f"Error al iniciar sesión: {e}")

def sign_up(email, password, name):
    """
    Registra un nuevo usuario en Supabase.
    NOTA: Para que funcione el envío de correo de verificación, debes configurar
    el SMTP en el dashboard de Supabase (Settings -> Auth -> Email Settings).
    """
    try:
        supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"full_name": name, "role": "supervisor", "email": email}}
        })
        st.success("Registro exitoso. Revisa tu correo electrónico para verificar tu cuenta.")
        st.info("⚠️ Si no recibes el correo, verifica la configuración SMTP en el panel de Supabase.")
    except Exception as e:
        st.error(f"Error al registrar: {e}")

def request_password_reset(email):
    """
    Solicita un enlace para restablecer la contraseña.
    NOTA: Requiere la configuración SMTP de Supabase.
    """
    try:
        supabase.auth.reset_password_for_email(email)
        st.success("Correo de recuperación enviado.")
        st.info("⚠️ Si no recibes el correo, verifica la configuración SMTP en el panel de Supabase.")
    except Exception as e:
        st.error(f"Error al solicitar recuperación: {e}")

def handle_logout():
    """Cierra la sesión de Supabase y limpia el estado local (incluyendo Google)."""
    try:
        supabase.auth.sign_out()
    except Exception as e:
        print(f"Error logout Supabase: {e}")
    st.session_state.clear()
    st.experimental_rerun()

# ============================================================
# 4. FUNCIONES DE UI (Interfaz de Usuario)
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
    with st.form("reset_form", clear_on_submit=True):
        st.text_input("Correo registrado", key="reset_email_input")
        if st.form_submit_button("Solicitar Enlace"):
            if st.session_state.reset_email_input:
                request_password_reset(st.session_state.reset_email_input)
            else:
                st.warning("Debes ingresar un correo.")

def render_auth_page():
    """Renderiza la página de autenticación híbrida (Google + Email/Pass)."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Acceso a la Plataforma")
        st.markdown("---")

        # --- Botón de Google Rediseñado ---
        if google_client is not None:
            try:
                loop = _ensure_async_loop()
                authorization_url = loop.run_until_complete(
                    _get_authorization_url(client=google_client, redirect_url=redirect_url)
                )
            except Exception as e:
                authorization_url = "#"
                st.error(f"Error al inicializar Google OAuth. Revisa secrets.toml. ({e})")
            
            # Estilo minimalista para el botón de Google (usando HTML/CSS simple)
            st.markdown(
                f"""
                <a href="{authorization_url}" target="_self" style="text-decoration: none;">
                    <button style="
                        width: 100%; 
                        height: 40px; 
                        background-color: white; 
                        color: #333; 
                        border: 1px solid #ccc;
                        border-radius: 0.5rem; 
                        font-weight: 500; 
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 10px;
                        margin-bottom: 20px;">
                        <img src="https://upload.wikimedia.org/wikipedia/commons/4/4a/Logo_2013_Google.png" 
                             style="width: 18px; height: 18px;">
                        Continuar con Google
                    </button>
                </a>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<p style='text-align: center; font-style: italic; color: #666;'>o usa tus credenciales</p>", unsafe_allow_html=True)
        st.markdown("---")

        # Pestañas para los formularios de Supabase
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
    """Renderiza la barra lateral con información de la sesión."""
    with st.sidebar:
        st.title("⚙️ Sesión")
        st.markdown("---")
        st.markdown(f"**Email:** `{st.session_state.get('user_email', 'Desconocido')}`")
        st.markdown(f"**Rol:** `{st.session_state.get('user_role', 'guest')}`")
        st.markdown("---")
        if st.button("Cerrar Sesión", use_container_width=True):
            handle_logout()

def render_main_content():
    """Contenido principal de la aplicación con diseño minimalista."""
    st.title("App Deserción Laboral 📊")
    
    email = st.session_state.get("user_email", "Desconocido")
    st.success(f"Bienvenido, {email}. Acceso Nivel: {st.session_state.get('user_role', 'guest').upper()}")

    st.markdown("## Resumen Ejecutivo")
    
    # Contenedor para métricas clave
    with st.container(border=True):
        st.subheader("Métricas de Retención")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Tasa de Deserción", value="12%", delta="-2% (vs. mes anterior)", delta_color="inverse")
        with col2:
            st.metric(label="Empleados Activos", value="1,280", delta="+5% (vs. trimestre)", delta_color="normal")
        with col3:
            st.metric(label="Rotación Voluntaria", value="8.5%", delta="-1.5%", delta_color="inverse")
    
    st.markdown("## Análisis de Tendencias por Departamento")
    
    # Gráfico de retención con datos simulados
    chart_data = {
        "Departamento": ["Ventas", "Marketing", "Ingeniería", "Soporte"], 
        "Deserción %": [15, 12, 8, 20]
    }
    st.bar_chart(chart_data, x="Departamento", y="Deserción %", color="#007ACC")
    
    st.markdown("---")
    st.info("La plataforma está lista para recibir sus datos de deserción para el análisis avanzado.")

# ============================================================
# 5. CONTROL DE FLUJO PRINCIPAL
# ============================================================

# 1. Se ejecuta al inicio para determinar el estado de la sesión
session_is_active = check_session_state_hybrid()

# 2. Control de Acceso
if session_is_active:
    # Si está autenticado
    render_sidebar()
    render_main_content()
else:
    # Si NO está autenticado
    render_auth_page()




