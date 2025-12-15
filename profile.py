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
        "profile_loaded": False,
        "name_error": False,
        "phone_error": False
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

def format_date_peru(iso_str, date_only=True):
    if not iso_str:
        return "N/A"

    dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    dt = dt.astimezone(TIMEZONE_PERU)

    return dt.strftime("%Y-%m-%d") if date_only else dt.strftime("%Y-%m-%d %H:%M")


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
    if st.session_state["name_error"] or st.session_state["phone_error"]:
        st.error("Corrige los errores antes de guardar")
        return

    supabase = st.session_state["supabase"]
    user_id = st.session_state["user_id"]

    payload = {
        "full_name": name,
        "phone_number": phone,
        "address": address,
        "date_of_birth": dob.strftime("%Y-%m-%d") if dob else None
    }

    if avatar:
        payload["avatar_url"] = (
            "data:image/png;base64,"
            + base64.b64encode(avatar).decode()
        )

    supabase.table("profiles").update(payload).eq("id", user_id).execute()

    load_user_profile_data.clear()
    st.success("Perfil actualizado correctamente")
    time.sleep(1)
    st.rerun()

# ==========================================================
# RENDER PRINCIPAL
# ==========================================================

def render_profile_page(supabase_client, request_password_reset):

    # Guardamos supabase en session_state (CLAVE)
    st.session_state["supabase"] = supabase_client

    user_id = st.session_state.get("user_id")

    if not user_id:
        st.warning("Usuario no autenticado")
        return

    if not st.session_state["profile_loaded"]:
        profile = load_user_profile_data(user_id)
        hydrate_session(profile)
        st.rerun()

    col_img, col_data = st.columns([1, 2])

    # ======================================================
    # AVATAR
    # ======================================================
    with col_img:
        st.subheader("Foto de Perfil")

        avatar = (
            st.session_state.get("temp_avatar_bytes")
            or st.session_state.get("avatar_url")
            or "https://placehold.co/200x200?text=U"
        )

        st.image(avatar, width=150)

        st.file_uploader(
            "Subir / Cambiar foto",
            type=["png", "jpg", "jpeg"],
            key="avatar_uploader",
            on_change=handle_avatar_upload
        )

    # ======================================================
    # FORMULARIO
    # ======================================================
    with col_data:
        st.header("Datos Personales y de Cuenta")

        with st.form("profile_form"):

            name = st.text_input("Nombre completo", st.session_state["full_name"])
            phone = st.text_input("Teléfono", st.session_state["phone_number"], max_chars=9)
            address = st.text_area("Dirección", st.session_state["address"])

            dob = st.date_input(
                "Fecha de nacimiento",
                value=datetime.date(2000, 1, 1)
            )

            # VALIDACIONES
            st.session_state["name_error"] = not re.match(r"^[A-Za-záéíóúÁÉÍÓÚñÑ\s]+$", name)
            st.session_state["phone_error"] = not re.match(r"^9\d{8}$", phone)

            if st.session_state["name_error"]:
                st.error("Nombre inválido")

            if st.session_state["phone_error"]:
                st.error("Teléfono inválido")

            st.markdown("### Datos de Cuenta (Solo lectura)")

            st.text_input(
                "Fecha de Creación",
                value=format_date_peru(st.session_state["created_at"]),
                disabled=True
            )

            st.text_input(
                "Rol",
                value=st.session_state["user_role"].capitalize(),
                disabled=True
            )

            st.text_input(
                "Correo",
                value=st.session_state["user_email"],
                disabled=True
            )

            if st.form_submit_button("Guardar cambios"):
                update_profile(
                    name,
                    dob,
                    phone,
                    address,
                    st.session_state.get("temp_avatar_bytes")
                )

    if st.button("Cambiar contraseña"):
        request_password_reset(st.session_state["user_email"])




