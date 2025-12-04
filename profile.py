import streamlit as st
import datetime
from typing import Optional
import base64

# --- Función de Actualización (Asumiendo que es la misma que ya funciona) ---
def update_user_profile(new_name: str, new_dob: datetime.date, avatar_bytes: Optional[bytes], user_id: str, supabase):
    """Actualiza nombre, fecha de nacimiento y avatar del usuario en Supabase."""
    data_to_update = {}

    # Nombre
    if new_name != st.session_state.get("full_name"):
        data_to_update["full_name"] = new_name

    # Fecha de nacimiento
    if new_dob and (new_dob != st.session_state.get("date_of_birth")):
        data_to_update["date_of_birth"] = new_dob.strftime("%Y-%m-%d") if new_dob else None
    elif new_dob is None and st.session_state.get("date_of_birth") is not None:
        data_to_update["date_of_birth"] = None # Permitir guardar fecha nula si se desea

    # Manejo del Avatar:
    # 1. Si hay bytes de imagen nuevos (subida o se mantiene la cargada), la guardamos.
    if avatar_bytes:
        # Convertimos bytes a base64 para guardar como string en Supabase
        # Nota: Usamos 'image/png' por defecto, ajusta si es necesario
        avatar_base64 = f"data:image/png;base64,{base64.b64encode(avatar_bytes).decode()}"
        if avatar_base64 != st.session_state.get("avatar_url"):
            data_to_update["avatar_url"] = avatar_base64
            st.session_state["avatar_image"] = avatar_bytes # Actualiza el estado de la imagen
    
    # 2. Si se ha borrado la imagen (avatar_bytes es None/vacío) y hay una URL actual, se elimina en DB
    elif avatar_bytes is None and st.session_state.get("avatar_url"):
        data_to_update["avatar_url"] = None

    if data_to_update:
        try:
            # Aquí se asume la conexión con Supabase (supabase.table("profiles")...)
            # Descomenta y usa esto en tu código real:
            # supabase.table("profiles").update(data_to_update).eq("id", user_id).execute()
            
            # --- Simulación de Actualización ---
            st.session_state.update({k: v for k, v in data_to_update.items()})
            st.session_state["full_name"] = new_name # Asegurar que el nombre se actualice en el state
            st.session_state["date_of_birth"] = new_dob # Asegurar que la DOB se actualice en el state
            # -----------------------------------

            st.success("¡Perfil actualizado con éxito!")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error al actualizar el perfil: {e}")
    else:
        st.info("No se detectaron cambios para guardar.")

# --- Renderización de la Página de Perfil Modificada ---
def render_profile_page(supabase, request_password_reset):
    """Renderiza el perfil del usuario y permite actualizarlo."""
    user_id = st.session_state.get("user_id")
    current_name = st.session_state.get("full_name", "")
    current_dob = st.session_state.get("date_of_birth")
    
    # Intenta obtener la imagen: 1. Desde st.session_state["avatar_image"] (bytes) 2. Desde st.session_state["avatar_url"] (base64 string) 3. Placeholder
    avatar_bytes = st.session_state.get("avatar_image")
    avatar_url = st.session_state.get("avatar_url", None)
    
    if not user_id:
        st.error("No se pudo cargar el ID del usuario.")
        return

    col_avatar, col_details = st.columns([1, 2])

    # === Columna de Detalles (Incluye el formulario principal) ===
    with col_details:
        st.header("Datos Personales y de Cuenta")
        with st.form("profile_form", clear_on_submit=False):
            # Campos de datos personales
            new_name = st.text_input("Nombre completo", value=current_name)
            
            # Convierte la fecha de nacimiento actual a datetime.date si es string
            dob_value = None
            if current_dob:
                try:
                    if isinstance(current_dob, str):
                        dob_value = datetime.datetime.strptime(current_dob, "%Y-%m-%d").date()
                    elif isinstance(current_dob, datetime.date):
                        dob_value = current_dob
                except ValueError:
                    dob_value = datetime.date(2000, 1, 1) # Valor por defecto si falla la conversión

            new_dob = st.date_input("Fecha de nacimiento", value=dob_value or datetime.date(2000, 1, 1))

            st.markdown("---")
            st.subheader("Datos de Cuenta (Solo Lectura)")
            st.text_input("Rol de Usuario", value=st.session_state.get("user_role", "guest").capitalize(), disabled=True)
            st.text_input("Correo Electrónico", value=st.session_state.get("user_email", "N/A"), disabled=True)
            
            st.markdown("---")

            # --- Manejo del Avatar dentro del formulario ---
            with col_avatar:
                st.subheader("Foto de Perfil")
                
                # Mostrar avatar actual, bytes o placeholder
                display_image = avatar_bytes or avatar_url or "https://placehold.co/200x200/A0A0A0/ffffff?text=U"
                st.image(display_image, width=150)
                
                # Opción para subir/actualizar
                uploaded_file = st.file_uploader("Subir/Cambiar Foto", type=["png","jpg","jpeg"], key="avatar_uploader")
                
                # Si se sube un archivo, lo usamos para la previsualización y guardado
                if uploaded_file:
                    # Lee el archivo en memoria (bytes)
                    new_avatar_bytes = uploaded_file.read()
                    # Actualiza el estado para el submit y previsualización
                    st.session_state["temp_avatar_bytes"] = new_avatar_bytes 
                    st.image(new_avatar_bytes, width=150) # Muestra la previsualización
                
                # Opción para Quitar
                if st.button("❌ Quitar Foto Actual", help="Elimina la foto de perfil al guardar."):
                    # Señalamos que se quiere eliminar el avatar
                    st.session_state["temp_avatar_bytes"] = None
                    st.session_state["avatar_image"] = None
                    st.session_state["avatar_url"] = None
                    # Forzar un rerun para que el placeholder se muestre inmediatamente
                    st.experimental_rerun()
            # --- Fin del manejo del Avatar ---
            
            # El botón de Guardar Cambios está al final del formulario en col_details
            if st.form_submit_button("💾 Guardar Cambios"):
                # Determinamos qué bytes vamos a guardar: lo nuevo subido, lo ya cargado, o None si se quitó.
                final_avatar_bytes = st.session_state.get("temp_avatar_bytes")
                
                # Si no hay un temp_avatar_bytes, mantenemos el avatar_bytes original si existe
                if final_avatar_bytes is None and st.session_state.get("avatar_image"):
                    final_avatar_bytes = st.session_state.get("avatar_image")

                update_user_profile(new_name, new_dob, final_avatar_bytes, user_id, supabase)

    # Botón de cambio de contraseña fuera del form (como lo tenías)
    st.markdown("---")
    if st.button("🔒 Cambiar Contraseña", use_container_width=True):
        request_password_reset(st.session_state.get("user_email"))




