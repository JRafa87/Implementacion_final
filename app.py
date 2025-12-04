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
        st.error("ERROR: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

# Cliente de Google
try:
    client_id = st.secrets["client_id"]
    client_secret = st.secrets["client_secret"]
    redirect_url = (
        st.secrets["redirect_url_test"] if testing_mode else st.secrets["redirect_url"]
    )
    google_client = GoogleOAuth2(client_id=client_id, client_secret=client_secret)
except KeyError:
    # Si faltan las secrets de Google, inicializar el cliente con placeholders
    # Esto permite que la app cargue aunque Google OAuth falle más tarde.
    st.warning("Advertencia: Faltan secretos de Google (client_id, etc.). Google OAuth no funcionará.")
    google_client = None

# ============================================================
# 1. FUNCIONES AUXILIARES DE GOOGLE OAUTH
# ============================================================

def _decode_google_token(token: str):
    """Decodifica el token JWT de Google."""
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
        return None # No intentar si el cliente no se inicializó

    try:
        code = st.query_params.get("code")
        if not code:
            return None

        # --- Manejo de asyncio seguro en Streamlit ---
        loop = _ensure_async_loop()
        
        # Ejecutar corrutina de forma síncrona
        if loop.is_running():
            token = asyncio.run_coroutine_threadsafe(
                _get_access_token(google_client, redirect_url, code), loop
            ).result()
        else:
            token = loop.run_until_complete(_get_access_token(google_client, redirect_url, code))
        
        # Limpiar query params para evitar loops
        st.experimental_set_query_params() 

        user_info = _decode_google_token(token["id_token"])
        st.session_state["google_email"] = user_info["email"]
        return user_info["email"]

    except Exception as e:
        # st.error(f"Error al procesar Google OAuth: {e}") 
        # Es común que falle en el primer load, solo imprimir en console para no asustar al usuario.
        print(f"Error silencioso de Google OAuth: {e}")
        return None

# ============================================================
# 2. FUNCIONES DE SUPABASE / ROLES (Autorización)
# ============================================================

def _get_user_role_from_db(user_id: Optional[str] = None, email: Optional[str] = None):
    """Obtiene rol desde la tabla profiles (puede usar ID o Email)."""
    st.session_state["user_role"] = "guest"
    st.session_state["user_id"] = None

    if user_id:
        # Aquí está la línea original 108:
        query = supabase.from("profiles").select("role").eq("id", user_id)
        # Aseguramos que solo devuelva un resultado
        response = query.limit(1).execute()
    elif email:
        query = supabase.from("profiles").select("role").eq("email", email)
        response = query.limit(1).execute()
    else:
        return

    try:
        # Reemplazamos .single() por un limit(1) y verificamos el resultado
        if response.data and len(response.data) > 0:
            profile = response.data[0]
            st.session_state["user_role"] = profile.get("role", "guest")
            st.session_state["user_id"] = user_id or None
    except Exception as e:
        print(f"Error al obtener rol: {e}")
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
        # Mapea el email de Google a tu base de datos de perfiles (obtiene el rol)
        _get_user_role_from_db(email=email_google)
        return True

    # B. Intento de Supabase (Email/Contraseña)
    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        if user:
            st.session_state["authenticated"] = True
            st.session_state["user_email"] = user.email
            # Lee el rol solo si el ID cambió o es la primera carga
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
    """Registra un nuevo usuario."""
    try:
        supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"full_name": name, "role": "supervisor", "email": email}}
        })
        st.success("Registro exitoso. Revisa tu correo electrónico para verificar tu cuenta.")
    except Exception as e:
        st.error(f"Error al registrar: {e}")

def request_password_reset(email):
    """Solicita un enlace para restablecer la contraseña."""
    try:
        supabase.auth.reset_password_for_email(email)
        st.success("Correo de recuperación enviado.")
    except Exception as e:
        st.error(f"Error al solicitar recuperación: {e}")

def handle_logout():
    """Cierra la sesión de Supabase y limpia el estado local (incluyendo Google)."""
    try:
        supabase.auth.sign_out()
    except Exception as e:
        print(f"Error logout Supabase: {e}")
    
    # Limpia el estado de Streamlit por completo
    st.session_state.clear() 
    st.experimental_rerun()

# ============================================================
# 4. FUNCIONES DE UI (Interfaz de Usuario)
# ============================================================

def render_login_form():
    st.subheader("Iniciar Sesión")
    with st.form("login_form"):
        email = st.text_input("Correo", key="login_email")
        password = st.text_input("Contraseña", type="password", key="login_password")
        if st.form_submit_button("Iniciar Sesión"):
            sign_in_manual(email, password)

def render_signup_form():
    st.subheader("Crear Cuenta")
    with st.form("signup_form"):
        name = st.text_input("Nombre completo", key="signup_name")
        email = st.text_input("Correo", key="signup_email")
        password = st.text_input("Contraseña", type="password", key="signup_password")
        if st.form_submit_button("Registrarse"):
            if name and email and password:
                sign_up(email, password, name)
            else:
                st.error("Completa todos los campos.")

def render_password_reset_form():
    st.subheader("Recuperar Contraseña")
    st.info("Ingresa tu correo. Recibirás un enlace por email.")
    with st.form("reset_form"):
        email = st.text_input("Correo registrado", key="reset_email")
        if st.form_submit_button("Solicitar Enlace"):
            if email:
                request_password_reset(email)
            else:
                st.warning("Debes ingresar un correo.")

def render_auth_page():
    """Renderiza la página de autenticación híbrida (Google + Email/Pass)."""
    st.title("🔐 Acceso Requerido")

    if google_client is not None:
        # Botón de Google (Solo si el cliente se inicializó)
        authorization_url = asyncio.run(_get_authorization_url(client=google_client, redirect_url=redirect_url))
        
        st.markdown("## Elegir Método de Acceso")
        
        st.markdown(
            f"""
            <a href="{authorization_url}" target="_self" style="text-decoration: none;">
                <div style="
                    display: inline-flex; justify-content: center; align-items: center;
                    font-weight: 600; padding: 0.5rem 1rem; border-radius: 0.5rem;
                    background-color: #4285F4; color: white; border: none;
                    width: 100%; text-align: center; margin-bottom: 20px;">
                    <img src="https://upload.wikimedia.org/wikipedia/commons/4/4a/Logo_2013_Google.png" style="width: 20px; margin-right: 10px; background-color: white; border-radius: 50%;">
                    Continuar con Google
                </div>
            </a>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown("### O usar Email y Contraseña")
    else:
        st.markdown("## Usar Email y Contraseña")

    # Pestañas para los formularios de Supabase
    tabs = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"]) 
    with tabs[0]:
        render_login_form()
    with tabs[1]:
        render_signup_form()
    with tabs[2]:
        render_password_reset_form()

def render_sidebar():
    """Renderiza la barra lateral con información de la sesión."""
    with st.sidebar:
        st.title("Menú")
        st.write(f"**Email:** {st.session_state.get('user_email', 'Desconocido')}")
        st.write(f"**Rol:** {st.session_state.get('user_role', 'guest')}")
        st.write(f"**Estado:** {'Autenticado' if st.session_state['authenticated'] else 'No autenticado'}")
        
        st.markdown("---")
        
        if st.button("Cerrar Sesión"):
            handle_logout()

def render_main_content():
    """Contenido principal de la aplicación (Visible para todos los autenticados)."""
    st.title("App Deserción Laboral 📊")
    
    email = st.session_state.get("user_email", "Desconocido")
    # role = st.session_state.get("user_role", "guest") # Ya no lo necesitas si no hay discriminación
    
    st.success(f"👋 Bienvenido, {email}. Tienes acceso completo a la aplicación.")
    
    # Ejemplo de métricas
    st.subheader("Datos Generales")
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Tasa de Deserción", value="12%", delta="-2%")
    with col2:
        st.metric(label="Empleados Activos", value="128", delta="+5%")
    
    st.subheader("Gráfico de Retención")
    st.bar_chart({"Departamentos": [20, 15, 30, 45], "Retención": [95, 88, 75, 92]})

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
    st.warning("No estás autenticado. Por favor inicia sesión.")
    render_auth_page()



