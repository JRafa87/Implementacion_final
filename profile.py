import streamlit as st
import datetime
import base64
import time
import re
from supabase import Client 

# ==========================================================
# UTILIDADES DE FORMATO Y DATOS
# ========================== ================================

def format_datetime_local(iso_str, use_now_if_none=False, date_only=False):
    """Detecta la hora del sistema de forma dinámica sin forzar una zona horaria fija."""
    if not iso_str:
        if use_now_if_none:
            now = datetime.datetime.now()
            return now.strftime("%Y-%m-%d") if date_only else now.strftime("%Y-%m-%d %H:%M")
        return "N/A"
    try:
        # Convertimos el ISO de Supabase a un objeto datetime local
        dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        # .astimezone(None) convierte a la hora local del sistema donde se visualiza
        dt_local = dt.astimezone(None)
        return dt_local.strftime("%Y-%m-%d") if date_only else dt_local.strftime("%Y-%m-%d %H:%M")
    except:
        return "N/A"

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
# ACCIONES DE ACTUALIZACIÓN
# ==========================================================

def update_profile(name, dob, phone, address, avatar):
    supabase = st.session_state["supabase"]
    user_id = st.session_state["user_id"]
    
    payload = {
        # .title() asegura que se guarde como "Nombre Apellido" (Mayúsculas iniciales)
        "full_name": name.strip().title(), 
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
        st.error(f"❌ Error al guardar en la base de datos: {e}")

# ==========================================================
# RENDER PRINCIPAL (SIN CONFLICTO DE ARGUMENTOS)
# ==========================================================

def render_profile_page(supabase_client, request_password_reset_func=None):
    st.session_state["supabase"] = supabase_client
    user_id = st.session_state.get("user_id")

    if not user_id:
        st.warning("⚠️ No se encontró una sesión activa. Por favor, inicie sesión.")
        return

    # Carga automática de perfil si no está en sesión
    if not st.session_state.get("profile_loaded", False):
        profile = load_user_profile_data(user_id)
        hydrate_session(profile)
        st.rerun()

    # Feedback de operaciones previas
    if st.session_state.get("update_status_message"):
        t, msg = st.session_state.pop("update_status_message")
        if t == "success": st.success(msg)
        else: st.error(msg)

    col_img, col_data = st.columns([1, 2])

    with col_img:
        st.subheader("Foto de Perfil")
        avatar_display = (st.session_state.get("temp_avatar_bytes") or 
                          st.session_state.get("avatar_url") or 
                          "https://placehold.co/200x200?text=Perfil")
        st.image(avatar_display, width=150)
        
        file = st.file_uploader("Subir imagen", type=["png", "jpg", "jpeg"])
        if file:
            st.session_state["temp_avatar_bytes"] = file.read()

    with col_data:
        st.header("Información Personal")
        
        # --- INPUTS ---
        name = st.text_input("👤 Nombre completo", st.session_state["full_name"])
        phone = st.text_input("📞 Teléfono Móvil", st.session_state["phone_number"], max_chars=9)
        address = st.text_area("🏠 Dirección de Residencia", st.session_state["address"])
        
        # Fecha de Nacimiento
        initial_dob = st.session_state.get("date_of_birth")
        try:
            dob_val = datetime.date.fromisoformat(initial_dob) if initial_dob else datetime.date(2000, 1, 1)
        except: dob_val = datetime.date(2000, 1, 1)
        dob = st.date_input("🗓️ Fecha de nacimiento", value=dob_val)

        # --- VALIDACIONES DE SEGURIDAD ---
        submit_disabled = False
        
        if name:
            # Bloquea si hay números o símbolos. Permite letras con tildes y espacios.
            if not re.match(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$", name):
                st.error("❌ El nombre no puede contener números ni caracteres especiales.")
                submit_disabled = True
            elif len(name.strip()) < 3:
                st.error("❌ Ingrese un nombre válido (mínimo 3 letras).")
                submit_disabled = True
        
        if phone and not re.match(r"^9\d{8}$", phone):
            st.error("❌ El teléfono debe tener 9 dígitos y empezar con 9.")
            submit_disabled = True

        with st.form("profile_edit_form"):
            st.markdown("---")
            if st.form_submit_button("💾 Actualizar mis Datos", disabled=submit_disabled, use_container_width=True):
                update_profile(name, dob, phone, address, st.session_state.get("temp_avatar_bytes"))

    # --- INFORMACIÓN DE CUENTA ---
    st.divider()
    st.subheader("ℹ️ Detalles de la Cuenta")
    c1, c2 = st.columns(2)
    with c1:
        st.text_input("📅 Fecha de Registro", value=format_datetime_local(st.session_state["created_at"], date_only=True), disabled=True)
        st.text_input("📧 Email de acceso", value=st.session_state["user_email"], disabled=True)
    with c2:
        st.text_input("⏰ Último Ingreso", value=format_datetime_local(st.session_state.get("last_sign_in_at"), use_now_if_none=True), disabled=True)
        st.text_input("🏷️ Rol Asignado", value=st.session_state["user_role"].upper(), disabled=True)

    # --- SECCIÓN DE SEGURIDAD ---
    st.markdown("---")
    st.subheader("🔒 Gestión de Seguridad")
    
    if not st.session_state.get("show_reset_fields", False):
        if st.button("Cambiar mi contraseña de acceso", use_container_width=True):
            supabase_client.auth.reset_password_for_email(st.session_state["user_email"])
            st.session_state.show_reset_fields = True
            st.info(f"Se ha enviado un código de verificación a {st.session_state['user_email']}")
            time.sleep(1)
            st.rerun()
    else:
        with st.form("otp_reset_auth_form"):
            st.markdown("#### Confirmación de Cambio")
            otp_code = st.text_input("Ingrese el código recibido")
            new_pw = st.text_input("Nueva contraseña (8+ caracteres)", type="password")
            conf_pw = st.text_input("Confirme su nueva contraseña", type="password")
            
            b_save, b_cancel = st.columns(2)
            with b_save:
                if st.form_submit_button("✅ Validar y Cambiar", use_container_width=True):
                    if new_pw == conf_pw and len(new_pw) >= 8:
                        try:
                            supabase_client.auth.verify_otp({
                                "email": st.session_state["user_email"], 
                                "token": otp_code.strip(), 
                                "type": "recovery"
                            })
                            supabase_client.auth.update_user({"password": new_pw})
                            st.success("✅ Contraseña actualizada con éxito.")
                            
                            # CUMPLIMIENTO DE REGLA: Dirigir a login limpiando el estado
                            st.session_state.clear()
                            time.sleep(2)
                            st.rerun()
                        except Exception:
                            st.error("El código es inválido o ya ha expirado.")
                    else:
                        st.error("Las contraseñas no coinciden o no cumplen con el mínimo de 8 caracteres.")
            with b_cancel:
                if st.form_submit_button("❌ Cancelar", use_container_width=True):
                    st.session_state.show_reset_fields = False
                    st.rerun()





