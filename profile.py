# profile.py
import streamlit as st
import datetime
from typing import Optional
from supabase import create_client, Client

# ========================
# Inicializar Supabase
# ========================
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

# ========================
# Función para reset de contraseña
# ========================
def request_password_reset(email: str):
    try:
        supabase.auth.reset_password_for_email(email)
        st.success("Correo de recuperación enviado.")
        st.info("⚠️ Revisa tu carpeta de spam si no lo recibes.")
    except Exception as e:
        st.error(f"Error al solicitar recuperación: {e}")


# ========================
# Función para actualizar perfil
# ========================
def update_user_profile(new_name: str, new_dob: datetime.date, new_avatar_path: Optional[str], user_id: str):
    """Actualiza nombre, fecha de nacimiento y avatar del usuario."""
    data_to_update = {}

    # Nombre
    if new_name != st.session_state.get("full_name"):
        data_to_update["full_name"] = new_name

    # Fecha de nacimiento
    if new_dob != st.session_state.get("date_of_birth"):
        data_to_update["date_of_birth"] = new_dob.strftime("%Y-%m-%d") if new_dob else None

    # Avatar local
    if new_avatar_path and new_avatar_path != st.session_state.get("avatar_url"):
        data_to_update["avatar_url"] = new_avatar_path

    if data_to_update:
        try:
            supabase.table("profiles").update(data_to_update).eq("id", user_id).execute()
            st.session_state.update({k: v for k, v in data_to_update.items()})
            st.success("¡Perfil actualizado con éxito!")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error al actualizar el perfil: {e}")
    else:
        st.info("No se detectaron cambios para guardar.")


# ========================
# Renderizado de la página
# ========================
def render_profile_page():
    """Renderiza el perfil del usuario y permite actualizarlo."""
    user_id = st.session_state.get("user_id")
    current_name = st.session_state.get("full_name")
    current_dob = st.session_state.get("date_of_birth")
    current_avatar_path = st.session_state.get("avatar_url", "")

    if not user_id:
        st.error("No se pudo cargar el ID del usuario.")
        return

    col_avatar, col_details = st.columns([1, 2])

    # Columna de la foto
    with col_avatar:
        st.subheader("Foto de Perfil")
        avatar_display = current_avatar_path if current_avatar_path else "default_avatar.png"
        st.image(avatar_display, width=150)

        uploaded_file = st.file_uploader("Cambiar foto de perfil", type=["png", "jpg", "jpeg"])
        if uploaded_file:
            avatar_path = f"avatars/{user_id}_{uploaded_file.name}"
            with open(avatar_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.session_state["avatar_url"] = avatar_path
            st.experimental_rerun()  # Recarga para mostrar la nueva imagen

    # Columna de detalles
    with col_details:
        st.header("Datos Personales y de Cuenta")
        with st.form("profile_form", clear_on_submit=False):
            new_name = st.text_input("Nombre completo", value=current_name)
            new_dob = st.date_input("Fecha de nacimiento", value=current_dob or datetime.date(2000,1,1))

            st.markdown("---")
            st.subheader("Datos de Cuenta (Solo Lectura)")
            st.text_input("Rol de Usuario", value=st.session_state.get("user_role", "guest").capitalize(), disabled=True)
            st.text_input("Correo Electrónico", value=st.session_state.get("user_email", "N/A"), disabled=True)

            col_save, col_password = st.columns([1,1])
            with col_save:
                if st.form_submit_button("💾 Guardar Cambios"):
                    update_user_profile(new_name, new_dob, st.session_state.get("avatar_url"), user_id)

            with col_password:
                st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
                if st.button("🔒 Cambiar Contraseña", use_container_width=True):
                    request_password_reset(st.session_state.get("user_email"))

