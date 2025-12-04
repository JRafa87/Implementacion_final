import streamlit as st
from typing import Optional
import jwt
from supabase import create_client, Client
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.oauth2 import OAuth2Token
import asyncio
import httpx
import datetime
import pandas as pd

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
    # Este bloque maneja si las secrets de Google no están configuradas
    st.warning("Advertencia: Faltan secretos de Google (client_id, etc.). Google OAuth no funcionará.")
    google_client = None

# Definición de todas las páginas disponibles
PAGES = [
    "Dashboard", 
    "Mi Perfil",
    "Gestión de Empleados", 
    "Predicción desde Archivo", 
    "Predicción Manual",
    "Reconocimiento" 
]

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

        loop = _ensure_async_loop()
        
        if loop.is_running():
            token = asyncio.run_coroutine_threadsafe(
                _get_access_token(google_client, redirect_url, code), loop
            ).result()
        else:
            token = loop.run_until_complete(_get_access_token(google_client, redirect_url, code))

        st.experimental_set_query_params()
        st.session_state["google_email"] = _decode_google_token(token["id_token"])["email"]
        return st.session_state["google_email"]

    except Exception:
        return None

# ============================================================
# 2. FUNCIONES DE SUPABASE / ROLES (Autorización y Perfil)
# ============================================================

def _fetch_user_profile(user_id: str):
    """Obtiene el perfil completo (nombre, fecha de nacimiento y URL del avatar) del usuario."""
    # Inicialización de fallback local
    st.session_state["user_role"] = "guest"
    st.session_state["full_name"] = "Usuario"
    st.session_state["date_of_birth"] = None
    st.session_state["avatar_url"] = None 
    st.session_state["user_id"] = None

    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        
        if response.data:
            profile = response.data[0]
            st.session_state["user_role"] = profile.get("role", "guest")
            st.session_state["full_name"] = profile.get("full_name", "Usuario") 
            st.session_state["user_id"] = user_id
            st.session_state["avatar_url"] = profile.get("avatar_url", None)
            
            # Manejar la fecha de nacimiento: convertir la cadena de Supabase a objeto date
            dob_str = profile.get("date_of_birth")
            if dob_str:
                st.session_state["date_of_birth"] = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date()
            else:
                 st.session_state["date_of_birth"] = None
            
            # Fallback si el nombre está vacío
            if not st.session_state["full_name"] or st.session_state["full_name"] == "Usuario":
                 st.session_state["full_name"] = st.session_state.get("user_email", "Usuario").split('@')[0]
        else:
            st.session_state["full_name"] = st.session_state.get("user_email", "Usuario").split('@')[0]
            st.session_state["user_id"] = user_id
            
    except Exception as e:
        st.session_state["user_id"] = None

def update_user_profile(new_name: str, new_dob: datetime.date, new_avatar_url: Optional[str], user_id: str):
    """Actualiza el nombre completo, la fecha de nacimiento y la URL del avatar del usuario."""
    data_to_update = {}
    
    # 1. Verificar Nombre
    if new_name != st.session_state.get("full_name"):
        data_to_update["full_name"] = new_name
    
    # 2. Verificar Fecha de Nacimiento
    # La fecha de nacimiento viene como objeto date. Se convierte a string 'YYYY-MM-DD' para Supabase.
    if new_dob != st.session_state.get("date_of_birth"):
        data_to_update["date_of_birth"] = new_dob.strftime('%Y-%m-%d') if new_dob else None
        
    # 3. Verificar URL del Avatar
    if new_avatar_url != st.session_state.get("avatar_url"):
        data_to_update["avatar_url"] = new_avatar_url
        
    if data_to_update:
        try:
            supabase.table("profiles").update(data_to_update).eq("id", user_id).execute()
            
            # Actualizar estado de la sesión local
            if "full_name" in data_to_update:
                st.session_state["full_name"] = new_name
            if "date_of_birth" in data_to_update:
                st.session_state["date_of_birth"] = new_dob
            if "avatar_url" in data_to_update:
                st.session_state["avatar_url"] = new_avatar_url
                
            st.success("¡Perfil actualizado con éxito!")
            # Recargar para que los cambios (como el avatar) se reflejen en el sidebar
            st.experimental_rerun() 

        except Exception as e:
            st.error(f"Error al actualizar el perfil: {e}")
    else:
        st.info("No se detectaron cambios para guardar.")

# ============================================================
# 3. FUNCIONES PRINCIPALES DE AUTENTICACIÓN HÍBRIDA
# ============================================================

def set_page(page_name):
    """Callback para establecer la nueva página y forzar la recarga (FIX)."""
    st.session_state.current_page = page_name
    st.experimental_rerun()

def check_session_state_hybrid() -> bool:
    """Verifica sesión activa e inicializa el perfil si es necesario."""
    
    # 0. CRÍTICO: Garantizar que la variable de navegación (current_page) siempre exista.
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Dashboard"

    # Inicializar el resto del estado de sesión si falta el flag de autenticación.
    if "authenticated" not in st.session_state:
        st.session_state.update({
            "authenticated": False,
            "user_role": "guest",
            "user_id": None,
            "user_email": None,
            "full_name": "Usuario",
            "date_of_birth": None,
            "avatar_url": None,
            # 'current_page' ya no se inicializa aquí
        })

    # 1. Manejo de tokens de Supabase desde la URL (Verificación/Reset)
    query_params = st.query_params
    access_token = query_params.get("access_token")
    refresh_token = query_params.get("refresh_token")
    
    if access_token and refresh_token:
        try:
            supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
            st.experimental_set_query_params()
            st.experimental_rerun()
            return True
        except Exception:
            pass

    # 2. Intento de Google OAuth
    email_google = get_google_user_email()
    if email_google:
        user_response = supabase.auth.get_user()
        user_id = user_response.user.id if user_response and user_response.user else None
        
        st.session_state["authenticated"] = True
        st.session_state["user_email"] = email_google
        if user_id and st.session_state.get("user_id") != user_id:
             _fetch_user_profile(user_id=user_id)
        return True

    # 3. Intento de Supabase (Email/Contraseña o Sesión existente)
    try:
        user_response = supabase.auth.get_user()
        user = getattr(user_response, "user", None)
        if user:
            st.session_state["authenticated"] = True
            st.session_state["user_email"] = user.email
            if st.session_state.get("user_id") != user.id:
                _fetch_user_profile(user_id=user.id)
            return True
    except Exception:
        pass

    # 4. No autenticado (Fall-back de seguridad, garantiza que todos los valores son Nones)
    st.session_state.update({
        "authenticated": False,
        "user_role": "guest",
        "user_id": None,
        "user_email": None,
        "full_name": "Usuario",
        "date_of_birth": None,
        "avatar_url": None,
        # 'current_page' no se toca aquí para mantener el estado de navegación si no hay logout
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
    Registra un nuevo usuario en Supabase y crea su perfil inicial.
    """
    try:
        # 1. Registrar usuario
        user_info = supabase.auth.sign_up({
            "email": email,
            "password": password,
        })
        
        # 2. Crear entrada en la tabla 'profiles' para el nombre y rol
        user_id = user_info.user.id
        supabase.table("profiles").insert({
            "id": user_id, 
            "email": email,
            "full_name": name, 
            "role": "supervisor",
            "date_of_birth": None,
            "avatar_url": None
        }).execute()

        st.success("Registro exitoso. Revisa tu correo electrónico para verificar tu cuenta.")
        st.info("⚠️ Si no recibes el correo, verifica la configuración SMTP en el panel de Supabase.")
    except Exception as e:
        st.error(f"Error al registrar: {e}")

def request_password_reset(email):
    """
    Solicita un enlace para restablecer la contraseña.
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
    except Exception:
        pass
    st.session_state.clear()
    st.experimental_rerun()


# ============================================================
# 4. FUNCIONES CRUD DE EMPLEADOS
# ============================================================

def fetch_employees():
    """Obtiene todos los empleados de la tabla 'employees'."""
    try:
        # Nota: La tabla 'employees' debe existir en Supabase
        response = supabase.table("employees").select("*").order("employee_id").execute()
        return response.data
    except Exception as e:
        st.error(f"Error al cargar empleados: {e}")
        return []

def add_employee(employee_data: dict):
    """Agrega un nuevo empleado a la tabla 'employees'."""
    try:
        supabase.table("employees").insert(employee_data).execute()
        st.success(f"Empleado {employee_data['name']} (ID: {employee_data['employee_id']}) añadido con éxito.")
    except Exception as e:
        st.error(f"Error al añadir empleado: {e}")

def update_employee_record(record_id: str, update_data: dict):
    """Actualiza un empleado existente por su ID de registro de Supabase."""
    try:
        supabase.table("employees").update(update_data).eq("id", record_id).execute()
        st.success(f"Empleado actualizado con éxito.")
    except Exception as e:
        st.error(f"Error al actualizar empleado: {e}")

def delete_employee_record(record_id: str):
    """Elimina un empleado por su ID de registro de Supabase."""
    try:
        supabase.table("employees").delete().eq("id", record_id).execute()
        st.success("Empleado eliminado con éxito.")
    except Exception as e:
        st.error(f"Error al eliminar empleado: {e}")


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
    """Renderiza la barra lateral con información de la sesión y navegación."""
    
    # Acceder a current_page de forma segura con .get() y un valor por defecto.
    current_page = st.session_state.get("current_page", "Dashboard") 
    
    with st.sidebar:
        # Mini perfil en la barra lateral
        col1, col2 = st.columns([1, 3])
        with col1:
            avatar_url = st.session_state.get("avatar_url")
            # Usar un placeholder si no hay URL válida
            if not avatar_url:
                avatar_url = "https://placehold.co/100x100/A0A0A0/ffffff?text=U"
            
            # CSS para hacer la imagen redonda
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
            # Mostrar el nombre del usuario autenticado
            st.title(f"👋 {st.session_state.get('full_name', 'Usuario').split(' ')[0]}")
            st.caption(f"Rol: **{st.session_state.get('user_role', 'guest').capitalize()}**")

        st.markdown("---")
        
        # Menú de Navegación
        st.markdown("### Navegación")
        
        # Botones de navegación (FIX: Usando on_click para estabilidad)
        for page in PAGES:
            # Asignar iconos
            icon_map = {
                "Dashboard": "📊",
                "Mi Perfil": "👤",
                "Gestión de Empleados": "👥",
                "Predicción desde Archivo": "📁",
                "Predicción Manual": "✏️",
                "Reconocimiento": "⭐"
            }
            icon = icon_map.get(page, "➡️")
            
            # Resaltar el botón de la página actual, usando la variable segura current_page
            button_style = "primary" if current_page == page else "secondary"
            
            # Uso de on_click para manejar la navegación de forma segura
            st.button(
                f"{icon} {page}", 
                key=f"nav_{page}", 
                use_container_width=True, 
                type=button_style,
                on_click=set_page, # Función callback
                args=(page,)      # Argumento de la función callback
            )
            
        st.markdown("---")
        # Sección de la cuenta (Cerrar Sesión)
        st.markdown(f"**Cuenta:** `{st.session_state.get('user_email', 'Desconocido')}`")
        
        if st.button("Cerrar Sesión", use_container_width=True):
            handle_logout()

def render_dashboard():
    """Contenido principal de la aplicación (Dashboard)."""
    st.title("App Deserción Laboral 📊")
    
    st.success(f"Bienvenido, {st.session_state.get('full_name', 'Usuario')}. Acceso Nivel: {st.session_state.get('user_role', 'guest').upper()}")

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
    st.info("Esta es la vista principal de resumen de datos de deserción.")

def render_profile_page():
    """Página para gestionar la información del perfil del usuario (Mi Perfil)."""
    st.title("👤 Mi Perfil")
    st.markdown("Actualiza tu foto, información personal y de cuenta.")
    
    user_id = st.session_state.get("user_id")
    current_name = st.session_state.get("full_name")
    current_dob = st.session_state.get("date_of_birth")
    current_avatar_url = st.session_state.get("avatar_url", "")
    
    # Usar una fecha sensata como valor por defecto para el selector
    default_dob = current_dob if current_dob else datetime.date(2000, 1, 1)

    if not user_id:
        st.error("Error: No se pudo cargar el ID del usuario.")
        return

    col_avatar, col_details = st.columns([1, 2.5])

    # Columna de la Foto de Perfil
    with col_avatar:
        st.subheader("Foto de Perfil")
        # Usar un placeholder si no hay URL válida
        display_url = current_avatar_url if current_avatar_url else "https://placehold.co/200x200/A0A0A0/ffffff?text=U"
        
        # Estilo para hacer la imagen redonda
        st.markdown(f"""
            <style>
                .profile-img {{
                    border-radius: 50%;
                    width: 150px;
                    height: 150px;
                    object-fit: cover;
                    border: 4px solid #007ACC;
                    margin-bottom: 20px;
                }}
            </style>
            <img src="{display_url}" class="profile-img">
        """, unsafe_allow_html=True)

    # Columna de Detalles y Formulario
    with col_details:
        st.header("Datos Personales y de Cuenta")
        
        with st.form("profile_form", clear_on_submit=False):
            # 1. Nombre Completo
            new_name = st.text_input("Nombre Completo", value=current_name, key="new_full_name")
            
            # 2. Fecha de Nacimiento
            new_dob = st.date_input(
                "Fecha de Nacimiento",
                value=default_dob,
                max_value=datetime.date.today(), # La fecha máxima es hoy
                key="new_date_of_birth"
            )

            # 3. URL del Avatar
            new_avatar_url = st.text_input(
                "URL de la Foto de Perfil", 
                value=current_avatar_url if current_avatar_url else "",
                help="Pegue el enlace directo a una imagen (ej. de Gravatar o una pública).",
                key="new_avatar_url_input"
            )

            st.markdown("---")
            st.subheader("Datos de Cuenta (Solo Lectura)")
            
            st.text_input("Rol de Usuario", value=st.session_state.get("user_role", "guest").capitalize(), disabled=True)
            st.text_input("Correo Electrónico", value=st.session_state.get("user_email", "N/A"), disabled=True)
            
            col_save, col_password = st.columns([1, 1])
            with col_save:
                if st.form_submit_button("💾 Guardar Cambios"):
                    # Llamar a la función de actualización con todos los campos
                    update_user_profile(new_name, new_dob, new_avatar_url, user_id)
            
            with col_password:
                st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True) # Espacio para alinear
                if st.button("🔒 Cambiar Contraseña", use_container_width=True):
                    request_password_reset(st.session_state.get("user_email"))

def render_employee_management_page():
    """Página de Gestión de Empleados (CRUD)."""
    st.title("👥 Gestión de Empleados")
    st.markdown("Administración de perfiles y estados de los colaboradores de la empresa.")

    # Control de Acceso: Solo para Administradores y Supervisores
    if st.session_state.get("user_role") not in ["admin", "supervisor"]:
        st.error("🚫 Acceso Denegado. Solo administradores y supervisores pueden gestionar empleados.")
        return

    # --- 1. Formulario de Creación de Empleados ---
    st.header("1. Añadir Nuevo Empleado")
    
    with st.form("add_employee_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        # Opciones para campos de selección
        departments = ["Ventas", "Marketing", "Ingeniería", "Soporte", "RR.HH.", "Finanzas"]
        
        with col1:
            new_id = st.text_input("ID de Empleado (Único)", key="new_emp_id")
            new_department = st.selectbox("Departamento", departments, key="new_emp_dept")
            
        with col2:
            new_name = st.text_input("Nombre Completo", key="new_emp_name")
            new_position = st.text_input("Puesto", key="new_emp_pos")

        with col3:
            # Usar un valor por defecto sensato para la fecha
            default_hire_date = datetime.date.today()
            new_hire_date = st.date_input("Fecha de Contratación", value=default_hire_date, max_value=datetime.date.today(), key="new_emp_hire_date")
            new_is_active = st.checkbox("Activo", value=True, key="new_emp_is_active")
        
        if st.form_submit_button("➕ Añadir Empleado"):
            if new_id and new_name and new_department and new_position:
                employee_data = {
                    "employee_id": new_id,
                    "name": new_name,
                    "department": new_department,
                    "position": new_position,
                    "date_of_hire": new_hire_date.isoformat(),
                    "is_active": new_is_active
                }
                add_employee(employee_data)
                st.experimental_rerun() # Recargar para ver el nuevo empleado en la lista
            else:
                st.error("Por favor, complete todos los campos obligatorios.")


    st.markdown("---")

    # --- 2. Listado y Gestión de Empleados ---
    st.header("2. Empleados Actuales")
    
    employees = fetch_employees()
    if not employees:
        st.warning("No hay empleados registrados en la base de datos.")
        return

    # Convertir a DataFrame para mejor visualización y filtrado
    df = pd.DataFrame(employees)
    df.rename(columns={
        "employee_id": "ID Empleado",
        "name": "Nombre",
        "department": "Departamento",
        "position": "Puesto",
        "date_of_hire": "F. Contratación",
        "is_active": "Activo",
        "id": "Supabase ID" # Mantener el ID de Supabase
    }, inplace=True)
    
    # Filtrar por Activo
    active_filter = st.checkbox("Mostrar solo Activos", value=True, help="Desmarca para ver empleados inactivos.")
    if active_filter:
        df_display = df[df['Activo'] == True]
    else:
        df_display = df
        
    st.dataframe(df_display[['ID Empleado', 'Nombre', 'Departamento', 'Puesto', 'F. Contratación', 'Activo']], use_container_width=True, hide_index=True)

    st.markdown("---")
    
    # --- 3. Edición/Eliminación ---
    st.header("3. Editar o Eliminar Empleado")
    
    # Selector de empleado a editar/eliminar
    # Usamos el ID Empleado como valor único para el selectbox
    employee_ids = df_display['ID Empleado'].tolist()
    selected_id = st.selectbox("Selecciona Empleado por ID", [""] + employee_ids)
    
    if selected_id:
        selected_record_row = df[df['ID Empleado'] == selected_id].iloc[0]
        # Usamos el ID de Supabase (columna 'Supabase ID') para las operaciones de base de datos
        record_id_supabase = selected_record_row['Supabase ID'] 
        
        with st.expander(f"Editar datos de {selected_record_row['Nombre']}"):
            with st.form(f"edit_employee_form_{record_id_supabase}"):
                
                # Campos de edición
                st.text_input("ID de Empleado (Único)", value=selected_record_row['ID Empleado'], disabled=True)
                edit_name = st.text_input("Nombre Completo", value=selected_record_row['Nombre'])
                
                # Manejar la fecha de contratación
                current_date_hire = datetime.datetime.strptime(selected_record_row['F. Contratación'], '%Y-%m-%d').date()
                edit_hire_date = st.date_input("Fecha de Contratación", value=current_date_hire, max_value=datetime.date.today())
                
                # Usar el índice para seleccionar el valor actual
                current_dept_index = departments.index(selected_record_row['Departamento'])
                edit_department = st.selectbox("Departamento", departments, index=current_dept_index)
                
                edit_position = st.text_input("Puesto", value=selected_record_row['Puesto'])
                edit_is_active = st.checkbox("Activo", value=selected_record_row['Activo'])
                
                col_upd, col_del = st.columns(2)
                with col_upd:
                    if st.form_submit_button("✅ Guardar Actualización"):
                        update_data = {
                            "name": edit_name,
                            "department": edit_department,
                            "position": edit_position,
                            "date_of_hire": edit_hire_date.isoformat(),
                            "is_active": edit_is_active
                        }
                        update_employee_record(record_id_supabase, update_data)
                        st.experimental_rerun()
                        
                with col_del:
                    # Usar un botón diferente para confirmar la eliminación (más seguro)
                    if st.form_submit_button("❌ Eliminar Empleado", type="primary"):
                        delete_employee_record(record_id_supabase)
                        st.experimental_rerun()


def render_placeholder_page(page_title):
    """Función de marcador de posición para páginas futuras (sin la gestión de empleados)."""
    st.title(page_title)
    st.info(f"Esta es la página de **{page_title}**. El contenido detallado se desarrollará en el siguiente paso.")
    st.markdown("---")
    if page_title == "Predicción desde Archivo 📁":
        st.warning("Se incluirá una sección para subir un archivo CSV y obtener predicciones de deserción masiva.")
    elif page_title == "Predicción Manual ✏️":
        st.warning("Se mostrará un formulario para ingresar manualmente las características de un empleado y obtener la probabilidad de deserción.")
    elif page_title == "Reconocimiento ⭐":
        st.warning("Esta sección será para gestionar y visualizar reconocimientos o premios a empleados.")


# ============================================================
# 6. CONTROL DE FLUJO PRINCIPAL
# ============================================================

# 1. Se ejecuta al inicio para determinar el estado de la sesión
session_is_active = check_session_state_hybrid()

# 2. Control de Acceso
if session_is_active:
    render_sidebar()
    # 3. Renderizar la página actual
    page_map = {
        "Dashboard": render_dashboard,
        "Mi Perfil": render_profile_page,
        "Gestión de Empleados": render_employee_management_page, # Función CRUD dedicada
        "Predicción desde Archivo": lambda: render_placeholder_page("Predicción desde Archivo 📁"),
        "Predicción Manual": lambda: render_placeholder_page("Predicción Manual ✏️"),
        "Reconocimiento": lambda: render_placeholder_page("Reconocimiento ⭐")
    }
    
    # Ejecutar la función de renderizado para la página actual
    page_map.get(st.session_state.get("current_page", "Dashboard"), render_dashboard)()
    
else:
    # Si NO está autenticado
    render_auth_page()



