import streamlit as st
import datetime
from typing import Optional
import base64
import time
import re
import pytz
from supabase import Client # Asegúrate de que Supabase Client esté importado si lo necesitas

# ==========================================================
# CONFIGURACIÓN
# ==========================================================

TIMEZONE_PERU = pytz.timezone("America/Lima")

# ==========================================================
# SESSION STATE INIT (OBLIGATORIO)
# ==========================================================

if "profile_loaded" not in st.session_state:
    st.session_state.update({
        "user_id": None,
        "user_email": "N/A",
        "user_role": "guest",
        "full_name": "",
        "phone_number": "",
        "address": "",
        "date_of_birth": None,
        "avatar_image": None,
        "avatar_url": None,
        "created_at": None,
        "last_sign_in_at": None,
        "temp_avatar_bytes": None,
        "profile_loaded": False,
        "update_status_message": None # <-- Nuevo campo para mensajes de estado
    })

# ==========================================================
# CARGA DE PERFIL (CACHE SEGURO)
# ==========================================================

@st.cache_data(ttl=600)
def load_user_profile_data(user_id: str):
    if not user_id:
        return None

    supabase = st.session_state["supabase"]

    response = (
        supabase
        .table("profiles")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
    )

    return response.data


def hydrate_session(profile: dict):
    if not profile:
        return

    st.session_state.update({
        "full_name": profile.get("full_name", ""),
        "phone_number": profile.get("phone_number", ""),
        "address": profile.get("address", ""),
        "date_of_birth": profile.get("date_of_birth"),
        "avatar_url": profile.get("avatar_url"),
        "user_role": profile.get("role", "supervisor"),
        "created_at": profile.get("created_at"),
        "profile_loaded": True
    })

# ==========================================================
# UTILIDADES
# ==========================================================

def format_datetime_peru(iso_str, use_now_if_none=False, date_only=False):
    if not iso_str:
        if use_now_if_none:
            now = datetime.datetime.now(TIMEZONE_PERU)
            return now.strftime("%Y-%m-%d") if date_only else now.strftime("%Y-%m-%d %H:%M hrs (PE)")
        return "N/A"

    dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    dt = dt.astimezone(TIMEZONE_PERU)

    return dt.strftime("%Y-%m-%d") if date_only else dt.strftime("%Y-%m-%d %H:%M hrs (PE)")


def handle_avatar_upload():
    file = st.session_state.get("avatar_uploader")
    if file:
        st.session_state["temp_avatar_bytes"] = file.read()


def update_profile(
    name: str,
    dob: datetime.date,
    phone: str,
    address: str,
    avatar: Optional[bytes]
):
    supabase = st.session_state["supabase"]
    user_id = st.session_state["user_id"]

    # 1. Validación de NOT NULL (Ejemplo: Si el Nombre es obligatorio en DB)
    if not name or len(name.strip()) < 1:
        st.session_state["update_status_message"] = ("error", "❌ El nombre es obligatorio.")
        return # Sale sin intentar guardar

    payload = {
        "full_name": name.strip(), # Limpia espacios extra
        "phone_number": phone.strip() if phone else None,
        "address": address.strip() if address else None,
        "date_of_birth": dob.strftime("%Y-%m-%d") if dob else None
    }

    # Manejo de Avatar
    if avatar:
        # Nota: Idealmente, usar Supabase Storage en lugar de Base64 grande
        payload["avatar_url"] = (
            "data:image/png;base64,"
            + base64.b64encode(avatar).decode()
        )

    # 🚨 Manejo del APIError con try...except
    try:
        supabase.table("profiles").update(payload).eq("id", user_id).execute()
        
        # Éxito: Limpiar cache y forzar recarga
        load_user_profile_data.clear()
        st.session_state["update_status_message"] = ("success", "✅ Perfil actualizado correctamente.")
        
        # Limpiamos los bytes temporales si hubo éxito en la DB
        st.session_state["temp_avatar_bytes"] = None 

        time.sleep(1)
        st.rerun() # Forzar rerun para cargar nuevos datos de sesión

    except Exception as e:
        # Captura cualquier error de PostgREST, RLS, o de longitud de campo
        print(f"Error al actualizar perfil (DB): {e}")
        st.session_state["update_status_message"] = ("error", "❌ Error al guardar. Revisa los datos (ej. longitud) y verifica que la Política RLS esté activa para tu ID.")
        # No hacemos rerun, permitimos al usuario ver el error y corregir en la misma interfaz

# ==========================================================
# RENDER PRINCIPAL (Con manejo de mensajes de estado)
# ==========================================================

def render_profile_page(supabase_client, request_password_reset):

    st.session_state["supabase"] = supabase_client
    user_id = st.session_state.get("user_id")

    if not user_id:
        st.warning("⚠️ Usuario no autenticado")
        return

    # ===============================
    # 1. MANEJO DE MENSAJES DE ESTADO
    # ===============================
    if st.session_state.get("update_status_message"):
        status_type, status_msg = st.session_state.pop("update_status_message")
        if status_type == "success":
            st.success(status_msg)
        elif status_type == "error":
            st.error(status_msg)

    # ===============================
    # 2. CARGA DEL PERFIL (si es necesario)
    # ===============================
    if not st.session_state.get("profile_loaded", False):
        profile = load_user_profile_data(user_id)
        hydrate_session(profile)
        st.rerun()

    col_img, col_data = st.columns([1, 2])

    # ======================================================
    # AVATAR
    # ======================================================
    with col_img:
        st.subheader("Foto de Perfil")

        avatar_display = (
            st.session_state.get("temp_avatar_bytes") 
            or st.session_state.get("avatar_url") 
            or "https://placehold.co/200x200?text=U"
        )
        st.image(avatar_display, width=150)

        st.file_uploader(
            "Subir / Cambiar foto",
            type=["png", "jpg", "jpeg"],
            key="avatar_uploader",
            on_change=handle_avatar_upload
        )

    # ======================================================
    # DATOS + VALIDACIONES
    # ======================================================
    with col_data:
        st.header("Datos Personales y de Cuenta")
        
        # Obtener valores para los inputs
        current_name = st.session_state["full_name"]
        current_phone = st.session_state["phone_number"]
        current_address = st.session_state["address"]
        
        # Inputs que definen las variables a guardar
        name = st.text_input("👤 Nombre completo", current_name)
        phone = st.text_input("📞 Teléfono", current_phone, max_chars=9)
        address = st.text_area("🏠 Dirección", current_address)

        # Manejo de Fecha de Nacimiento
        initial_dob = st.session_state.get("date_of_birth")
        if isinstance(initial_dob, str):
            try:
                initial_dob = datetime.date.fromisoformat(initial_dob)
            except ValueError:
                initial_dob = datetime.date(2000, 1, 1) 
        elif initial_dob is None:
            initial_dob = datetime.date(2000, 1, 1)

        dob = st.date_input(
            "🗓️ Fecha de nacimiento",
            value=initial_dob,
            min_value=datetime.date(1900, 1, 1),
            max_value=datetime.date.today()
        )

        # ===============================
        # VALIDACIONES EN TIEMPO REAL
        # ===============================
        name_error = False
        phone_error = False
        
        # Si el usuario ha tocado el campo, valida
        if name and not re.match(r"^[A-Za-záéíóúÁÉÍÓÚñÑ\s]+$", name):
            st.error("❌ El nombre solo puede contener letras.")
            name_error = True
        elif not name.strip():
             st.warning("El nombre es un campo importante. Se validará como obligatorio al guardar.")
             name_error = True # Consideramos que no tener nombre es un error para deshabilitar.

        if phone and not re.match(r"^9\d{8}$", phone):
            st.error("❌ Teléfono inválido (9 dígitos, inicia en 9).")
            phone_error = True
            
        submit_disabled = name_error or phone_error

        # ===============================
        # DATOS SOLO LECTURA
        # ===============================
        st.markdown("### Datos de Cuenta (Solo lectura)")

        st.text_input(
            "📅 Fecha de Creación",
            value=format_datetime_peru(st.session_state["created_at"], date_only=True),
            disabled=True
        )

        st.text_input(
            "⏰ Última sesión",
            value=format_datetime_peru(
                st.session_state.get("last_sign_in_at"),
                use_now_if_none=True
            ),
            disabled=True
        )

        st.text_input(
            "🏷️ Rol",
            value=st.session_state["user_role"].capitalize(),
            disabled=True
        )

        st.text_input(
            "📧 Correo",
            value=st.session_state["user_email"],
            disabled=True
        )

        # ===============================
        # FORM SOLO PARA GUARDAR
        # ===============================
        with st.form("profile_form"):
            st.markdown("---")
            if st.form_submit_button("💾 Guardar cambios", disabled=submit_disabled):
                # Llama a la función que ahora maneja el APIError
                update_profile(
                    name,
                    dob,
                    phone,
                    address,
                    st.session_state.get("temp_avatar_bytes")
                )
                # Si hubo error en update_profile, el mensaje se mostrará al inicio del siguiente ciclo.

    # ======================================================
    # CAMBIO DE CONTRASEÑA
    # ======================================================
    st.markdown("---")
    if st.button("🔒 Cambiar contraseña", use_container_width=True):
        request_password_reset(st.session_state["user_email"])






