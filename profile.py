import streamlit as st
import datetime
import base64
import time
import re
import pytz
from supabase import Client 

# ==========================================================
# CONFIGURACIÓN Y UTILIDADES
# ==========================================================
TIMEZONE_PERU = pytz.timezone("America/Lima")

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

# ==========================================================
# LÓGICA DE ACTUALIZACIÓN
# ==========================================================

def update_profile(name, dob, phone, address, avatar):
    supabase = st.session_state["supabase"]
    user_id = st.session_state["user_id"]
    
    payload = {
        "full_name": name.strip().title(), # "juan pérez" -> "Juan Pérez"
        "phone_number": phone.strip() if phone else None,
        "address": address.strip() if address else None,
        "date_of_birth": dob.strftime("%Y-%m-%d") if dob else None
    }
    
    if avatar:
        base64_image = "data:image/png;base64," + base64.b64encode(avatar).decode()
        payload["avatar_url"] = base64_image
        # ACTUALIZACIÓN CRUCIAL: Actualizamos el estado local antes del rerun
        st.session_state["avatar_url"] = base64_image
    
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
# RENDER PRINCIPAL (CORREGIDO CON 2 ARGUMENTOS)
# ==========================================================

def render_profile_page(supabase_client, request_password_reset_func=None):
    """
    Recibe 2 argumentos para ser compatible con tu app.py:
    1. supabase_client: El cliente de base de datos.
    2. request_password_reset_func: (Opcional) Función externa de reseteo.
    """
    st.session_state["supabase"] = supabase_client
    user_id = st.session_state.get("user_id")

    if not user_id:
        st.warning("⚠️ Usuario no autenticado")
        return

    # Carga inicial de datos
    if not st.session_state.get("profile_loaded", False):
        profile = load_user_profile_data(user_id)
        hydrate_session(profile)
        st.rerun()

    # Mostrar notificaciones de éxito/error
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
        
        # Entradas de usuario
        name = st.text_input("👤 Nombre completo", st.session_state["full_name"])
        phone = st.text_input("📞 Teléfono", st.session_state["phone_number"], max_chars=9)
        address = st.text_area("🏠 Dirección", st.session_state["address"])
        
        # Manejo de fecha de nacimiento
        initial_dob = st.session_state.get("date_of_birth")
        try:
            dob_val = datetime.date.fromisoformat(initial_dob) if initial_dob else datetime.date(2000, 1, 1)
        except: dob_val = datetime.date(2000, 1, 1)
        dob = st.date_input("🗓️ Fecha de nacimiento", value=dob_val)

        # --- VALIDACIONES ESTRICTAS ---
        submit_disabled = False
        
        if name:
            # Regex: Solo letras, espacios y tildes. Bloquea números.
            if not re.match(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$", name):
                st.error("❌ El nombre no puede contener números ni caracteres especiales.")
                submit_disabled = True
            elif len(name.strip()) < 3:
                st.error("❌ El nombre debe tener al menos 3 letras.")
                submit_disabled = True
        
        if phone and not re.match(r"^9\d{8}$", phone):
            st.error("❌ El teléfono debe iniciar con 9 y tener 9 dígitos.")
            submit_disabled = True

        with st.form("profile_form"):
            st.markdown("---")
            if st.form_submit_button("💾 Guardar cambios", disabled=submit_disabled, use_container_width=True):
                update_profile(name, dob, phone, address, st.session_state.get("temp_avatar_bytes"))

    # --- INFORMACIÓN DE CUENTA ---
    st.divider()
    st.markdown("### ℹ️ Detalles de la Cuenta")
    # Si no existe en la sesión, la creamos ahora mismo
    if "session_time_pe" not in st.session_state:
        # datetime.datetime.now(TIMEZONE_PERU) obtiene la hora exacta de Lima
        st.session_state["session_time_pe"] = datetime.datetime.now(TIMEZONE_PERU).strftime("%Y-%m-%d %H:%M hrs (PE)")

    last_login_display = st.session_state["session_time_pe"]

    # --- RENDER DE DETALLES DE CUENTA ---

    c_acc1, c_acc2, c_acc3 = st.columns(3)
    
    with c_acc1:
        st.text_input("📅 Registrado el", 
                     value=format_datetime_peru(st.session_state.get("created_at"), date_only=True), 
                     disabled=True)
    with c_acc2:
        st.text_input("🏷️ Nivel de Acceso", 
                     value=str(st.session_state.get("user_role", "")).upper(), 
                     disabled=True)
    with c_acc3:
        # Aquí se muestra la hora del sistema que capturamos arriba
        st.text_input("🕒 Última Conexión", 
                     value=last_login_display, 
                     disabled=True)

    st.text_input("📧 Correo de Usuario", value=st.session_state.get("user_email"), disabled=True)

    # --- SEGURIDAD (PASSWORD RESET) ---
    st.markdown("---")
    st.subheader("🔒 Seguridad")
    
    if not st.session_state.get("show_reset_fields", False):
        if st.button("Actualizar contraseña de acceso", use_container_width=True):
            supabase_client.auth.reset_password_for_email(st.session_state["user_email"])
            st.session_state.show_reset_fields = True
            st.info(f"Se ha enviado un código a: {st.session_state['user_email']}")
            time.sleep(1)
            st.rerun()
    else:
        with st.form("otp_reset_form"):
            st.markdown("#### Confirmar cambio")
            otp_code = st.text_input("Código enviado al correo", placeholder="123456")
            new_pw = st.text_input("Nueva contraseña (min. 8 caracteres)", type="password")
            conf_pw = st.text_input("Repetir contraseña", type="password")
            
            b1, b2 = st.columns(2)
            with b1:
                if st.form_submit_button("✅ Actualizar ahora", use_container_width=True):
                    if new_pw == conf_pw and len(new_pw) >= 8:
                        try:
                            supabase_client.auth.verify_otp({
                                "email": st.session_state["user_email"], 
                                "token": otp_code.strip(), 
                                "type": "recovery"
                            })
                            supabase_client.auth.update_user({"password": new_pw})
                            st.success("✅ Contraseña actualizada.")
                            # REGLA PERSONALIZADA: Redirigir a login (limpiando todo el estado)
                            st.session_state.clear()
                            time.sleep(2)
                            st.rerun()
                        except Exception:
                            st.error("Código incorrecto o expirado.")
                    else:
                        st.error("Verifica que las contraseñas coincidan y tengan longitud mínima.")
            with b2:
                if st.form_submit_button("❌ Cancelar", use_container_width=True):
                    st.session_state.show_reset_fields = False
                    st.rerun()





