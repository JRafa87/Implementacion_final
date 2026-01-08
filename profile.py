import streamlit as st
import datetime
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
# UTILIDADES DE PERFIL
# ==========================================================

@st.cache_data(ttl=600)
def load_user_profile_data(user_id: str):
    if not user_id: return None
    supabase = st.session_state["supabase"]
    response = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    return response.data

def hydrate_session(profile: dict):
    if not profile: return
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

def format_datetime_peru(iso_str, use_now_if_none=False, date_only=False):
    if not iso_str:
        if use_now_if_none:
            now = datetime.datetime.now(TIMEZONE_PERU)
            return now.strftime("%Y-%m-%d") if date_only else now.strftime("%Y-%m-%d %H:%M hrs (PE)")
        return "N/A"
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt = dt.astimezone(TIMEZONE_PERU)
        return dt.strftime("%Y-%m-%d") if date_only else dt.strftime("%Y-%m-%d %H:%M hrs (PE)")
    except: return "N/A"

# ==========================================================
# ACCIONES DE BASE DE DATOS
# ==========================================================

def update_profile(name, dob, phone, address, avatar):
    supabase = st.session_state["supabase"]
    user_id = st.session_state["user_id"]
    
    payload = {
        "full_name": name.strip().title(), # .title() pone Mayúsculas automáticamente
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
        st.error(f"❌ Error al guardar: {e}")

# ==========================================================
# RENDER PRINCIPAL
# ==========================================================

def render_profile_page(supabase_client):
    st.session_state["supabase"] = supabase_client
    user_id = st.session_state.get("user_id")

    if not user_id:
        st.warning("⚠️ Usuario no autenticado")
        return

    # Inicializar Session State si no existe
    if "profile_loaded" not in st.session_state or not st.session_state.profile_loaded:
        profile = load_user_profile_data(user_id)
        hydrate_session(profile)
        st.rerun()

    # Mensajes de estado
    if st.session_state.get("update_status_message"):
        t, msg = st.session_state.pop("update_status_message")
        st.success(msg) if t == "success" else st.error(msg)

    col_img, col_data = st.columns([1, 2])

    with col_img:
        st.subheader("Foto de Perfil")
        avatar_display = (st.session_state.get("temp_avatar_bytes") or 
                          st.session_state.get("avatar_url") or 
                          "https://placehold.co/200x200?text=Usuario")
        st.image(avatar_display, width=150)
        
        file = st.file_uploader("Cambiar foto", type=["png", "jpg", "jpeg"])
        if file:
            st.session_state["temp_avatar_bytes"] = file.read()

    with col_data:
        st.header("Datos Personales")
        
        # --- CAMPOS DE ENTRADA ---
        name = st.text_input("👤 Nombre completo", st.session_state["full_name"])
        phone = st.text_input("📞 Teléfono (9 dígitos)", st.session_state["phone_number"], max_chars=9)
        address = st.text_area("🏠 Dirección", st.session_state["address"])
        
        initial_dob = st.session_state.get("date_of_birth")
        try:
            dob_val = datetime.date.fromisoformat(initial_dob) if initial_dob else datetime.date(2000, 1, 1)
        except: dob_val = datetime.date(2000, 1, 1)
        dob = st.date_input("🗓️ Fecha de nacimiento", value=dob_val)

        # --- LÓGICA DE VALIDACIÓN ---
        submit_disabled = False
        if name:
            # Regex: Solo letras, espacios y tildes. No permite números ni símbolos.
            if not re.match(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$", name):
                st.error("❌ El nombre solo debe contener letras (sin números ni símbolos).")
                submit_disabled = True
            elif len(name.strip()) < 3:
                st.error("❌ El nombre es demasiado corto.")
                submit_disabled = True
        
        if phone and not re.match(r"^9\d{8}$", phone):
            st.error("❌ El teléfono debe empezar con 9 y tener 9 dígitos.")
            submit_disabled = True

        with st.form("profile_form"):
            st.markdown("---")
            if st.form_submit_button("💾 Guardar cambios", disabled=submit_disabled, use_container_width=True):
                update_profile(name, dob, phone, address, st.session_state.get("temp_avatar_bytes"))

    # --- INFORMACIÓN DE CUENTA (SOLO LECTURA) ---
    st.markdown("### ℹ️ Información de Cuenta")
    c1, c2 = st.columns(2)
    with c1:
        st.text_input("📅 Creación", value=format_datetime_peru(st.session_state["created_at"], date_only=True), disabled=True)
        st.text_input("🏷️ Rol", value=st.session_state["user_role"].upper(), disabled=True)
    with c2:
        st.text_input("📧 Email", value=st.session_state["user_email"], disabled=True)

    # --- SECCIÓN SEGURIDAD ---
    st.markdown("---")
    st.subheader("🔒 Seguridad")
    
    if not st.session_state.get("show_reset_fields", False):
        if st.button("Actualizar contraseña de acceso", use_container_width=True):
            supabase_client.auth.reset_password_for_email(st.session_state["user_email"])
            st.session_state.show_reset_fields = True
            st.info("Se ha enviado un código a su correo.")
            time.sleep(1)
            st.rerun()
    else:
        with st.form("otp_reset_form"):
            otp_code = st.text_input("Código de verificación")
            new_pw = st.text_input("Nueva contraseña", type="password")
            conf_pw = st.text_input("Confirmar contraseña", type="password")
            
            b1, b2 = st.columns(2)
            with b1:
                if st.form_submit_button("✅ Confirmar", use_container_width=True):
                    if new_pw == conf_pw and len(new_pw) >= 8:
                        try:
                            supabase_client.auth.verify_otp({"email": st.session_state["user_email"], "token": otp_code.strip(), "type": "recovery"})
                            supabase_client.auth.update_user({"password": new_pw})
                            st.success("¡Contraseña actualizada!")
                            # Según tus reglas: Luego de recuperar, dirigir a login (limpiando sesión)
                            st.session_state.clear()
                            time.sleep(2)
                            st.rerun()
                        except: st.error("Código inválido o expirado.")
                    else: st.error("Las contraseñas no coinciden o son muy cortas.")
            with b2:
                if st.form_submit_button("❌ Cancelar"):
                    st.session_state.show_reset_fields = False
                    st.rerun()






