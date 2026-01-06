import streamlit as st
import datetime
from typing import Optional
import base64
import time
import re
import pytz
from supabase import Client 

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
        "update_status_message": None 
    })

# ==========================================================
# CARGA DE PERFIL (CACHE SEGURO)
# ==========================================================

@st.cache_data(ttl=600)
def load_user_profile_data(user_id: str):
    if not user_id:
        return None
    # Usamos el cliente desde el state
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


def update_profile(name, dob, phone, address, avatar):
    supabase = st.session_state["supabase"]
    user_id = st.session_state["user_id"]

    if not name or len(name.strip()) < 1:
        st.session_state["update_status_message"] = ("error", "❌ El nombre es obligatorio.")
        return 

    payload = {
        "full_name": name.strip(),
        "phone_number": phone.strip() if phone else None,
        "address": address.strip() if address else None,
        "date_of_birth": dob.strftime("%Y-%m-%d") if dob else None
    }

    if avatar:
        payload["avatar_url"] = "data:image/png;base64," + base64.b64encode(avatar).decode()

    try:
        supabase.table("profiles").update(payload).eq("id", user_id).execute()
        load_user_profile_data.clear()
        st.session_state["update_status_message"] = ("success", "✅ Perfil actualizado correctamente.")
        st.session_state["temp_avatar_bytes"] = None 
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.session_state["update_status_message"] = ("error", f"❌ Error al guardar: {e}")

# ==========================================================
# RENDER PRINCIPAL
# ==========================================================

def render_profile_page(supabase_client, request_password_reset_func=None):
    # Definimos supabase localmente para que todo el bloque funcione
    supabase = supabase_client 
    st.session_state["supabase"] = supabase_client
    user_id = st.session_state.get("user_id")

    if not user_id:
        st.warning("⚠️ Usuario no autenticado")
        return

    if st.session_state.get("update_status_message"):
        status_type, status_msg = st.session_state.pop("update_status_message")
        if status_type == "success": st.success(status_msg)
        elif status_type == "error": st.error(status_msg)

    if not st.session_state.get("profile_loaded", False):
        profile = load_user_profile_data(user_id)
        hydrate_session(profile)
        st.rerun()

    col_img, col_data = st.columns([1, 2])

    with col_img:
        st.subheader("Foto de Perfil")
        avatar_display = (st.session_state.get("temp_avatar_bytes") or st.session_state.get("avatar_url") or "https://placehold.co/200x200?text=U")
        st.image(avatar_display, width=150)
        st.file_uploader("Subir / Cambiar foto", type=["png", "jpg", "jpeg"], key="avatar_uploader", on_change=handle_avatar_upload)

    with col_data:
        st.header("Datos Personales")
        name = st.text_input("👤 Nombre completo", st.session_state["full_name"])
        phone = st.text_input("📞 Teléfono", st.session_state["phone_number"], max_chars=9)
        address = st.text_area("🏠 Dirección", st.session_state["address"])

        initial_dob = st.session_state.get("date_of_birth")
        if isinstance(initial_dob, str):
            try: initial_dob = datetime.date.fromisoformat(initial_dob)
            except: initial_dob = datetime.date(2000, 1, 1)
        
        dob = st.date_input("🗓️ Fecha de nacimiento", value=initial_dob or datetime.date(2000, 1, 1))

        # Validaciones simples
        submit_disabled = False
        if phone and not re.match(r"^9\d{8}$", phone):
            st.error("❌ Teléfono debe iniciar con 9 y tener 9 dígitos.")
            submit_disabled = True

        with st.form("profile_form"):
            st.markdown("---")
            if st.form_submit_button("💾 Guardar cambios", disabled=submit_disabled):
                update_profile(name, dob, phone, address, st.session_state.get("temp_avatar_bytes"))

        # Datos lectura
        st.markdown("### Datos de Cuenta")
        st.info(f"**Rol:** {st.session_state['user_role'].capitalize()} | **Correo:** {st.session_state['user_email']}")

    # ======================================================
    # CAMBIO DE CONTRASEÑA (CORREGIDO)
    # ======================================================
    st.markdown("---")
    st.subheader("🔒 Seguridad de la cuenta")

    if "show_reset_fields" not in st.session_state:
        st.session_state.show_reset_fields = False

    if not st.session_state.show_reset_fields:
        if st.button("Actualizar contraseña", use_container_width=True):
            try:
                # Usamos supabase (definido al inicio de render_profile_page)
                supabase.auth.reset_password_for_email(st.session_state["user_email"])
                st.session_state.show_reset_fields = True
                st.info(f"Código enviado a: **{st.session_state['user_email']}**")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        with st.form("profile_otp_reset_form"):
            st.markdown("#### Validar Cambio")
            otp_code = st.text_input("Código de verificación", placeholder="000000")
            new_pw = st.text_input("Nueva contraseña", type="password")
            conf_pw = st.text_input("Confirmar nueva contraseña", type="password")
            
            c1, c2 = st.columns(2)
            with c1:
                if st.form_submit_button("✅ Guardar nueva contraseña", use_container_width=True):
                    if new_pw == conf_pw and len(new_pw) >= 8:
                        try:
                            # Validar OTP y Actualizar
                            supabase.auth.verify_otp({"email": st.session_state["user_email"], "token": otp_code.strip(), "type": "recovery"})
                            supabase.auth.update_user({"password": new_pw})
                            st.success("✨ ¡Contraseña actualizada!")
                            st.balloons()
                            st.session_state.show_reset_fields = False
                            time.sleep(2)
                            st.rerun()
                        except: st.error("Código incorrecto o expirado.")
                    else: st.error("Las contraseñas no coinciden o son muy cortas.")
            with c2:
                if st.form_submit_button("❌ Cancelar", use_container_width=True):
                    st.session_state.show_reset_fields = False
                    st.rerun()






