# profile.py
import streamlit as st
import datetime
from typing import Optional
import base64

def update_user_profile(new_name: str,
                        new_dob: datetime.date,
                        avatar_bytes: Optional[bytes],
                        user_id: str,
                        supabase):
    """
    Actualiza nombre, fecha de nacimiento y avatar del usuario en Supabase.
    El avatar se guarda como Base64.
    """
    data_to_update = {}

    # Nombre
    if new_name != st.session_state.get("full_name"):
        data_to_update["full_name"] = new_name

    # Fecha de nacimiento
    if new_dob != st.session_state.get("date_of_birth"):
        data_to_update["date_of_birth"] = new_dob.strftime("%Y-%m-%d") if new_dob else None

    # Avatar
    if avatar_bytes:
        data_to_update["avatar_url"] = f"data:image/png;base64,{base64.b64encode(avatar_bytes).decode()}"

    if data_to_update:
        try:
            supabase.table("profiles").update(data_to_update).eq("id", user_id).execute()
            st.session_state.update({k: v for k, v in data_to_update.items()})
            st.success("¡Perfil actualizado con éxito!")
        except Exception as e:
            st.error(f"Error al actualizar el perfil: {e}")
    else:
        st.info("No se detectaron cambios para guardar.")


def render_profile_page(supabase, request_password_reset_func):
    """
    Renderiza el perfil del usuario y permite actualizarlo.
    - supabase: cliente Supabase
    - request_password_reset_func: función para enviar correo de cambio de contraseña
    """
    user_id = st.session_state.get("user_id")
    current_name = st.session_state.get("full_name", "")
    current_dob = st.session_state.get("date_of_birth")
    current_avatar = st.session_state.get("avatar_url", None)

    if not user_id:
        st.error("No se pudo cargar el ID del usuario.")
        return

    # Convertir dob si viene como string
    if isinstance(current_dob, str):
        current_dob = datetime.datetime.strptime(current_dob, "%Y-%m-%d").date()

    col_avatar, col_details = st.columns([1, 2])

    # -----------------------------
    # Columna Avatar
    # -----------------------------
    with col_avatar:
        st.subheader("Foto de Perfil")

        # Mostrar avatar actual
        if "avatar_image" in st.session_state:
            st.image(st.session_state["avatar_image"], width=150)
        elif current_avatar:
            st.image(current_avatar, width=150)
        else:
            st.image("https://placehold.co/200x200/A0A0A0/ffffff?text=U", width=150)

        # Subir nueva imagen
        uploaded_file = st.file_uploader("Subir nueva foto", type=["png", "jpg", "jpeg"])
        if uploaded_file:
            avatar_bytes = uploaded_file.read()
            st.session_state["avatar_image"] = avatar_bytes
            st.image(avatar_bytes, width=150)

    # -----------------------------
    # Columna Datos Personales
    # -----------------------------
    with col_details:
        st.header("Datos Personales y de Cuenta")
        with st.form("profile_form", clear_on_submit=False):
            new_name = st.text_input("Nombre completo", value=current_name)
            new_dob = st.date_input("Fecha de nacimiento", value=current_dob or datetime.date(2000, 1, 1))

            st.markdown("---")
            st.subheader("Datos de Cuenta (Solo Lectura)")
            st.text_input("Rol de Usuario",
                          value=st.session_state.get("user_role", "guest").capitalize(),
                          disabled=True)
            st.text_input("Correo Electrónico",
                          value=st.session_state.get("user_email", "N/A"),
                          disabled=True)

            col_save, col_password = st.columns([1, 1])
            with col_save:
                if st.form_submit_button("💾 Guardar Cambios"):
                    avatar_bytes = st.session_state.get("avatar_image")
                    update_user_profile(new_name, new_dob, avatar_bytes, user_id, supabase)

            with col_password:
                st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
                if st.button("🔒 Cambiar Contraseña", use_container_width=True):
                    request_password_reset_func(st.session_state.get("user_email"))



