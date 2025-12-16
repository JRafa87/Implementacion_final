import streamlit as st
import datetime
from typing import Optional
import base64
import time
import re
import pytz

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
        "profile_loaded": False
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

    payload = {
        "full_name": name,
        "phone_number": phone,
        "address": address,
        "date_of_birth": dob.strftime("%Y-%m-%d") if dob else None
    }

    if avatar:
        # Nota: Idealmente, usar Supabase Storage en lugar de Base64 grande
        payload["avatar_url"] = (
            "data:image/png;base64,"
            + base64.b64encode(avatar).decode()
        )

    supabase.table("profiles").update(payload).eq("id", user_id).execute()

    load_user_profile_data.clear()
    st.success("✅ Perfil actualizado correctamente")
    time.sleep(1)
    st.rerun()

# ==========================================================
# RENDER PRINCIPAL
# ==========================================================

def render_profile_page(supabase_client, request_password_reset):

    # Guardamos Supabase en session_state (clave para cache)
    st.session_state["supabase"] = supabase_client

    # 🚨 SOLUCIÓN KEYERROR: Inicializar user_id si no existe
    # Esto es crítico si la sesión no está completamente hidratada
    user_id = st.session_state.get("user_id")

    if not user_id:
        st.warning("⚠️ Usuario no autenticado")
        return

    # ===============================
    # CARGA DEL PERFIL
    # ===============================
    # 🚨 SOLUCIÓN KEYERROR: Usar .get() con valor por defecto
    # Esto evita el KeyError si la clave no se carga a tiempo en el móvil.
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

        # 🖼️ SOLUCIÓN AVATAR: Usar bytes directamente si están disponibles, 
        # lo que es más eficiente para el renderizado móvil que el Base64.
        avatar_display = (
            st.session_state.get("temp_avatar_bytes") # Bytes (si se acaba de subir)
            or st.session_state.get("avatar_url")      # URL (Base64 o pública)
            or "https://placehold.co/200x200?text=U"  # Placeholder
        )

        st.image(avatar_display, width=150)

        st.file_uploader(
            "Subir / Cambiar foto",
            type=["png", "jpg", "jpeg"],
            key="avatar_uploader",
            on_change=handle_avatar_upload
        )

    # ======================================================
    # DATOS + VALIDACIONES (FUERA DEL FORM)
    # ======================================================
    with col_data:
        st.header("Datos Personales y de Cuenta")

        name = st.text_input("👤 Nombre completo", st.session_state["full_name"])
        phone = st.text_input("📞 Teléfono", st.session_state["phone_number"], max_chars=9)
        address = st.text_area("🏠 Dirección", st.session_state["address"])

        # Manejo más seguro para date_of_birth, asumiendo una fecha por defecto si es None
        initial_dob = st.session_state.get("date_of_birth")
        if initial_dob:
            # Si se almacena como string 'YYYY-MM-DD', conviértelo a date
            if isinstance(initial_dob, str):
                try:
                    initial_dob = datetime.date.fromisoformat(initial_dob)
                except ValueError:
                    initial_dob = datetime.date(2000, 1, 1) # Fallback
        else:
             initial_dob = datetime.date(2000, 1, 1) # Default si es None

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

        if name and not re.match(r"^[A-Za-záéíóúÁÉÍÓÚñÑ\s]+$", name):
            st.error("❌ El nombre solo puede contener letras")
            name_error = True

        if phone and not re.match(r"^9\d{8}$", phone):
            st.error("❌ Teléfono inválido (9 dígitos, inicia en 9)")
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
            if st.form_submit_button("💾 Guardar cambios", disabled=submit_disabled):
                update_profile(
                    name,
                    dob,
                    phone,
                    address,
                    st.session_state.get("temp_avatar_bytes")
                )

    # ======================================================
    # CAMBIO DE CONTRASEÑA
    # ======================================================
    st.markdown("---")
    if st.button("🔒 Cambiar contraseña", use_container_width=True):
        request_password_reset(st.session_state["user_email"])







