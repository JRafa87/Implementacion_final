import streamlit as st
import datetime
import base64
import time
import re
import pytz

# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

TIMEZONE_PERU = pytz.timezone("America/Lima")

# =========================================================
# SESSION STATE (SEGURO)
# =========================================================

def init_session_state():
    defaults = {
        "user_id": None,
        "user_email": "N/A",
        "user_role": "guest",
        "full_name": "",
        "phone_number": "",
        "address": "",
        "date_of_birth": None,
        "avatar_url": None,
        "avatar_image": None,
        "temp_avatar_bytes": None,
        "created_at": None,
        "last_sign_in_at": None,
        "profile_loaded": False
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_session_state()

# =========================================================
# CARGA DE PERFIL (NO CACHEAR CLIENTE)
# =========================================================

@st.cache_data(ttl=600)
def load_profile(user_id, supabase):
    if not user_id:
        return None
    res = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    return res.data

def sync_profile_to_state(profile):
    if not profile:
        return
    st.session_state["full_name"] = profile.get("full_name", "")
    st.session_state["phone_number"] = profile.get("phone_number", "")
    st.session_state["address"] = profile.get("address", "")
    st.session_state["date_of_birth"] = profile.get("date_of_birth")
    st.session_state["avatar_url"] = profile.get("avatar_url")
    st.session_state["user_role"] = profile.get("role", "supervisor")
    st.session_state["created_at"] = profile.get("created_at")
    st.session_state["profile_loaded"] = True

# =========================================================
# UTILIDADES
# =========================================================

def format_datetime_peru(iso):
    if not iso:
        return "N/A"
    dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.astimezone(TIMEZONE_PERU).strftime("%Y-%m-%d %H:%M hrs (PE)")

def format_date_peru(iso):
    if not iso:
        return "N/A"
    dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.astimezone(TIMEZONE_PERU).strftime("%Y-%m-%d")

def handle_avatar_upload():
    file = st.session_state.get("avatar_uploader")
    if file:
        st.session_state["temp_avatar_bytes"] = file.read()

# =========================================================
# ACTUALIZAR PERFIL
# =========================================================

def update_profile(supabase, user_id, name, phone, address, dob, avatar_bytes):
    data = {}

    if name != st.session_state["full_name"]:
        data["full_name"] = name

    if phone != st.session_state["phone_number"]:
        data["phone_number"] = phone

    if address != st.session_state["address"]:
        data["address"] = address

    dob_str = dob.strftime("%Y-%m-%d") if dob else None
    if dob_str != st.session_state["date_of_birth"]:
        data["date_of_birth"] = dob_str

    if avatar_bytes:
        data["avatar_url"] = f"data:image/png;base64,{base64.b64encode(avatar_bytes).decode()}"

    if not data:
        st.info("ℹ️ No hay cambios para guardar")
        return

    supabase.table("profiles").update(data).eq("id", user_id).execute()
    load_profile.clear()
    st.success("✅ Perfil actualizado")
    time.sleep(1)
    st.rerun()

# =========================================================
# RENDER PRINCIPAL
# =========================================================

def render_profile_page(supabase, request_password_reset):

    user_id = st.session_state.get("user_id")

    if not user_id:
        st.warning("⚠️ Debes iniciar sesión")
        return

    if not st.session_state["profile_loaded"]:
        profile = load_profile(user_id, supabase)
        sync_profile_to_state(profile)
        st.rerun()

    # =========================
    # UI
    # =========================

    st.header("👤 Mi Perfil")

    col_avatar, col_form = st.columns([1, 2])

    with col_avatar:
        avatar = (
            st.session_state.get("temp_avatar_bytes")
            or st.session_state.get("avatar_image")
            or st.session_state.get("avatar_url")
            or "https://placehold.co/200x200?text=User"
        )
        st.image(avatar, width=150)
        st.file_uploader(
            "Cambiar foto",
            type=["png", "jpg", "jpeg"],
            key="avatar_uploader",
            on_change=handle_avatar_upload
        )

    with col_form:
        with st.form("profile_form"):
            name = st.text_input("Nombre completo", st.session_state["full_name"])
            phone = st.text_input("Teléfono", st.session_state["phone_number"], max_chars=9)
            address = st.text_area("Dirección", st.session_state["address"])

            dob_val = None
            if st.session_state["date_of_birth"]:
                dob_val = datetime.datetime.strptime(
                    st.session_state["date_of_birth"], "%Y-%m-%d"
                ).date()

            dob = st.date_input(
                "Fecha de nacimiento",
                value=dob_val or datetime.date(2000, 1, 1),
                min_value=datetime.date(1900, 1, 1),
                max_value=datetime.date.today()
            )

            # =========================
            # VALIDACIONES (AUTO LIMPIABLES)
            # =========================

            name_error = False
            phone_error = False

            if name and not re.match(r"^[A-Za-záéíóúÁÉÍÓÚñÑ\s]+$", name):
                st.error("❌ El nombre solo puede contener letras")
                name_error = True

            if phone and not re.match(r"^9\d{8}$", phone):
                st.error("❌ Teléfono inválido (9 dígitos, inicia en 9)")
                phone_error = True

            submit_disabled = name_error or phone_error

            if st.form_submit_button("💾 Guardar cambios", disabled=submit_disabled):
                update_profile(
                    supabase,
                    user_id,
                    name,
                    phone,
                    address,
                    dob,
                    st.session_state.get("temp_avatar_bytes")
                )

    # =========================
    # DATOS DE CUENTA
    # =========================

    st.markdown("---")
    st.subheader("🔐 Datos de Cuenta")

    col1, col2 = st.columns(2)
    col1.text_input(
        "Fecha de creación",
        value=format_date_peru(st.session_state["created_at"]),
        disabled=True
    )
    col2.text_input(
        "Última sesión",
        value=format_datetime_peru(st.session_state["last_sign_in_at"]),
        disabled=True
    )

    st.text_input("Rol", st.session_state["user_role"].capitalize(), disabled=True)
    st.text_input("Correo", st.session_state["user_email"], disabled=True)

    st.markdown("---")
    if st.button("🔒 Cambiar contraseña", use_container_width=True):
        request_password_reset(st.session_state["user_email"])





