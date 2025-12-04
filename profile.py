import streamlit as st
import datetime
from typing import Optional
import base64

# ====================================================================
# === 1. FUNCIÓN DE ACTUALIZACIÓN (AJUSTADA) ===
# ====================================================================

def update_user_profile(new_name: str, new_dob: datetime.date, avatar_bytes: Optional[bytes], user_id: str, supabase):
    """Actualiza nombre, fecha de nacimiento y avatar del usuario en Supabase."""
    data_to_update = {}

    # Nombre
    if new_name != st.session_state.get("full_name"):
        data_to_update["full_name"] = new_name

    # Fecha de nacimiento (Manejo de formato string 'YYYY-MM-DD')
    dob_str = new_dob.strftime("%Y-%m-%d") if new_dob else None
    current_dob_str = st.session_state.get("date_of_birth")

    if dob_str != current_dob_str:
        data_to_update["date_of_birth"] = dob_str 

    # Manejo del Avatar:
    if avatar_bytes:
        avatar_base64 = f"data:image/png;base64,{base64.b64encode(avatar_bytes).decode()}"
        if avatar_base64 != st.session_state.get("avatar_url"):
            data_to_update["avatar_url"] = avatar_base64
            st.session_state["avatar_image"] = avatar_bytes # Guardar los bytes de la nueva imagen
            
    elif avatar_bytes is None and st.session_state.get("avatar_url"):
        # Se quiere eliminar la foto
        data_to_update["avatar_url"] = None
        st.session_state["avatar_image"] = None # Eliminar los bytes de la imagen guardada

    if data_to_update:
        try:
            # Aquí se ejecutaría la lógica real de Supabase
            # st.write("Simulación de guardado en Supabase:", data_to_update)
            # supabase.table("profiles").update(data_to_update).eq("id", user_id).execute()
            
            # --- Actualización del estado (Simulación) ---
            st.session_state.update({k: v for k, v in data_to_update.items()})
            st.session_state["full_name"] = new_name
            st.session_state["date_of_birth"] = dob_str
            
            # Limpiar el estado temporal después de un guardado exitoso
            if "temp_avatar_bytes" in st.session_state:
                del st.session_state["temp_avatar_bytes"]
            # -----------------------------------

            st.success("¡Perfil actualizado con éxito!")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error al actualizar el perfil: {e}")
    else:
        st.info("No se detectaron cambios para guardar.")


# ====================================================================
# === 2. RENDERIZADO CORREGIDO (SOLUCIÓN DEL REEMPLAZO) ===
# ====================================================================

def render_profile_page(supabase, request_password_reset):
    """Renderiza el perfil del usuario y permite actualizarlo."""
    user_id = st.session_state.get("user_id")
    current_name = st.session_state.get("full_name", "")
    current_dob_str = st.session_state.get("date_of_birth") # Usar el string guardado
    
    # Bytes de la imagen guardada
    avatar_bytes_saved = st.session_state.get("avatar_image")
    avatar_url = st.session_state.get("avatar_url", None)
    
    # Bytes de la imagen temporal (la que el usuario subió y aún no ha guardado)
    temp_bytes = st.session_state.get("temp_avatar_bytes")

    if not user_id:
        st.error("No se pudo cargar el ID del usuario.")
        return

    col_avatar, col_details = st.columns([1, 2])

    # === Columna de Detalles (Contiene el formulario principal) ===
    with col_details:
        st.header("Datos Personales y de Cuenta")
        with st.form("profile_form", clear_on_submit=False):
            
            # 1. --- Manejo de la Foto de Perfil (Columna Izquierda) ---
            with col_avatar:
                st.subheader("Foto de Perfil")
                
                # --- Lógica de REEMPLAZO: Mostrar la imagen temporal (si existe), sino la guardada, sino el placeholder. ---
                if temp_bytes is not None:
                    display_image = temp_bytes
                elif avatar_bytes_saved is not None:
                    display_image = avatar_bytes_saved
                elif avatar_url is not None: # Usar URL si no tenemos los bytes
                    display_image = avatar_url
                else:
                    display_image = "https://placehold.co/200x200/A0A0A0/ffffff?text=U"
                    
                # SOLO UNA LLAMADA A ST.IMAGE - Esto asegura que el widget se reutilice
                st.image(display_image, width=150)
                
                # Subir/Cambiar Foto
                uploaded_file = st.file_uploader("Subir/Cambiar Foto", type=["png","jpg","jpeg"], key="avatar_uploader")
                
                # Si se sube un nuevo archivo, lo guardamos en el estado temporal y forzamos un rerun
                if uploaded_file:
                    # Lee los bytes del archivo. El f-uploader solo se dispara si es un archivo nuevo.
                    uploaded_file.seek(0)
                    new_avatar_bytes = uploaded_file.read()
                    
                    # Usamos un marcador de estado para la previsualización y el submit
                    st.session_state["temp_avatar_bytes"] = new_avatar_bytes 
                    
                    # **IMPORTANTE:** Forzar el rerun para que la lógica de 'display_image' de arriba use 'temp_bytes'
                    st.rerun()
                
                # Opción para Quitar
                if st.button("❌ Quitar Foto Actual", help="Elimina la foto de perfil al guardar."):
                    st.session_state["temp_avatar_bytes"] = None # Marcar para eliminación
                    st.rerun() # Forzar rerun para mostrar el placeholder inmediatamente
            # -------------------------------------------------------------
            
            # 2. Campos de datos personales (Columna Derecha)
            new_name = st.text_input("Nombre completo", value=current_name)
            
            dob_value = None
            if current_dob_str:
                try:
                    dob_value = datetime.datetime.strptime(current_dob_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    pass # Dejar como None si falla
            
            new_dob = st.date_input("Fecha de nacimiento", value=dob_value or datetime.date(2000, 1, 1))

            st.markdown("---")
            st.subheader("Datos de Cuenta (Solo Lectura)")
            st.text_input("Rol de Usuario", value=st.session_state.get("user_role", "guest").capitalize(), disabled=True)
            st.text_input("Correo Electrónico", value=st.session_state.get("user_email", "N/A"), disabled=True)

            st.markdown("<br>", unsafe_allow_html=True)
            
            # 3. Botón de Guardar
            if st.form_submit_button("💾 Guardar Cambios"):
                
                # Si la imagen temporal está presente (subida o se marcó para quitar, y ya se hizo el rerun)
                final_avatar_bytes = temp_bytes 
                
                # Si el usuario NO interactuó con el file_uploader o el botón de quitar, conservamos el guardado
                if final_avatar_bytes is None and st.session_state.get("avatar_image") is not None and uploaded_file is None:
                    final_avatar_bytes = st.session_state.get("avatar_image")

                # Si el file_uploader tiene un archivo, debemos leerlo aquí por si el usuario no hizo rerun previo
                if uploaded_file and final_avatar_bytes is None:
                    uploaded_file.seek(0)
                    final_avatar_bytes = uploaded_file.read()
                
                update_user_profile(new_name, new_dob, final_avatar_bytes, user_id, supabase)

    # Botón de cambio de contraseña fuera del form
    st.markdown("---")
    if st.button("🔒 Cambiar Contraseña", use_container_width=True):
        request_password_reset(st.session_state.get("user_email"))




