import streamlit as st
import datetime
from typing import Optional
import base64
import time

# ====================================================================
# === 1. FUNCIÓN CALLBACK PARA MANEJAR SUBIDA DE ARCHIVO (CORREGIDA) ===
# ====================================================================

def handle_file_upload():
    """
    Maneja la subida de un archivo del uploader, guarda los bytes temporalmente
    y fuerza el rerun para actualizar el display.
    """
    uploaded_file = st.session_state.get("avatar_uploader_widget")
    
    if uploaded_file is not None:
        # 1. Leer los bytes
        uploaded_file.seek(0)
        new_avatar_bytes = uploaded_file.read()
        
        # 2. Guardar los bytes en el estado temporal para el display y submit
        st.session_state["temp_avatar_bytes"] = new_avatar_bytes 
        
        # 3. Borrar el estado de la imagen guardada para que el display use la temporal
        # y forzar que el uploader se resetee al rerenderizar.
        if "avatar_image" in st.session_state:
            del st.session_state["avatar_image"]
        if "avatar_url" in st.session_state:
            del st.session_state["avatar_url"]
        
    

# --- FUNCIÓN DE ACTUALIZACIÓN ---
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
    # Se usa 'avatar_bytes' (el valor final de la lógica del form) para determinar qué hacer.
    if avatar_bytes is not None and avatar_bytes != st.session_state.get("avatar_image"):
        # Hay bytes nuevos o diferentes a los guardados -> Actualizar.
        avatar_base64 = f"data:image/png;base64,{base64.b64encode(avatar_bytes).decode()}"
        data_to_update["avatar_url"] = avatar_base64
        st.session_state["avatar_image"] = avatar_bytes # Guardar los bytes de la nueva imagen
            
    elif avatar_bytes is None and st.session_state.get("avatar_url"):
        # Se quiere eliminar la foto.
        data_to_update["avatar_url"] = None
        st.session_state["avatar_image"] = None # Eliminar los bytes de la imagen guardada

    if data_to_update:
        try:
            # Aquí se ejecutaría la lógica real de Supabase
            # supabase.table("profiles").update(data_to_update).eq("id", user_id).execute()
            
            # --- Actualización del estado (Simulación) ---
            st.session_state.update({k: v for k, v in data_to_update.items()})
            st.session_state["full_name"] = new_name
            st.session_state["date_of_birth"] = dob_str # Guardamos el string
            
            # Limpiar el estado temporal después de un guardado exitoso
            if "temp_avatar_bytes" in st.session_state:
                del st.session_state["temp_avatar_bytes"]
            # -----------------------------------

            st.success("¡Perfil actualizado con éxito!")
            st.rerun() 
        except Exception as e:
            st.error(f"Error al actualizar el perfil: {e}")
    else:
        st.info("No se detectaron cambios para guardar.")


# ====================================================================
# === 2. RENDERIZADO CORREGIDO (Lógica de display simplificada) ===
# ====================================================================

def render_profile_page(supabase, request_password_reset):
    """Renderiza el perfil del usuario y permite actualizarlo."""
    user_id = st.session_state.get("user_id")
    current_name = st.session_state.get("full_name", "")
    current_dob_str = st.session_state.get("date_of_birth")
    
    # Bytes de la imagen guardada
    avatar_bytes_saved = st.session_state.get("avatar_image")
    avatar_url = st.session_state.get("avatar_url", None)
    
    # Bytes de la imagen temporal (la que el usuario subió y aún no ha guardado)
    temp_bytes = st.session_state.get("temp_avatar_bytes")

    if not user_id:
        st.error("No se pudo cargar el ID del usuario.")
        return

    col_avatar, col_details = st.columns([1, 2])

    with col_details:
        st.header("Datos Personales y de Cuenta")
        with st.form("profile_form", clear_on_submit=False):
            
            # 1. --- Manejo de la Foto de Perfil (Columna Izquierda) ---
            with col_avatar:
                st.subheader("Foto de Perfil")
                
                # --- Lógica de REEMPLAZO: Muestra la imagen temporal (subida), sino la guardada, sino el placeholder. ---
                if temp_bytes is not None:
                    # Usar la imagen recién subida/marcada para eliminación
                    display_image = temp_bytes 
                elif avatar_bytes_saved is not None:
                    # Usar la imagen guardada en memoria
                    display_image = avatar_bytes_saved
                elif avatar_url is not None:
                    # Usar la URL guardada (si es base64 o una URL externa)
                    display_image = avatar_url
                else:
                    # Placeholder
                    display_image = "https://placehold.co/200x200/A0A0A0/ffffff?text=U"
                        
                st.image(display_image, width=150)
                
                # Subir/Cambiar Foto: Usamos el callback para limpiar el widget al hacer st.rerun()
                st.file_uploader(
                    "Subir/Cambiar Foto", 
                    type=["png","jpg","jpeg"], 
                    key="avatar_uploader_widget", # Clave para el widget
                    on_change=handle_file_upload # Llama a la función de manejo
                )
                
                # Opción para Quitar
                # Solo mostrar el botón si hay una foto actualmente visible (guardada o temporal)
                if temp_bytes is not None or avatar_bytes_saved is not None or avatar_url is not None:
                    if st.button("❌ Quitar Foto Actual", help="Elimina la foto de perfil al guardar."):
                        # 1. Marcar el estado temporal como nulo (para que update_user_profile sepa que debe eliminar)
                        st.session_state["temp_avatar_bytes"] = None 
                        
                        # 2. Eliminar las claves guardadas para que el display_image caiga en el 'else' (placeholder).
                        if "avatar_image" in st.session_state:
                            del st.session_state["avatar_image"]
                        if "avatar_url" in st.session_state:
                            del st.session_state["avatar_url"]
                        
                        st.rerun() # Forzar rerun para mostrar el placeholder
                        
            # -------------------------------------------------------------
            
            # 2. Campos de datos personales (Columna Derecha)
            new_name = st.text_input("Nombre completo", value=current_name)
            
            dob_value = None
            if current_dob_str:
                try:
                    dob_value = datetime.datetime.strptime(current_dob_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    pass
            
            new_dob = st.date_input("Fecha de nacimiento", value=dob_value or datetime.date(2000, 1, 1))

            st.markdown("---")
            st.subheader("Datos de Cuenta (Solo Lectura)")
            st.text_input("Rol de Usuario", value=st.session_state.get("user_role", "guest").capitalize(), disabled=True)
            st.text_input("Correo Electrónico", value=st.session_state.get("user_email", "N/A"), disabled=True)

            st.markdown("<br>", unsafe_allow_html=True)
            
            # 3. Botón de Guardar
            if st.form_submit_button("💾 Guardar Cambios"):
                
                final_avatar_bytes = st.session_state.get("temp_avatar_bytes")
                
                # Si el estado temporal no está seteado (ni subida ni eliminación),
                # y SÍ había una imagen guardada previamente, la conservamos.
                if final_avatar_bytes is None and "temp_avatar_bytes" not in st.session_state:
                    final_avatar_bytes = st.session_state.get("avatar_image")
                
                update_user_profile(new_name, new_dob, final_avatar_bytes, user_id, supabase)

    # Botón de cambio de contraseña fuera del form
    st.markdown("---")
    if st.button("🔒 Cambiar Contraseña", use_container_width=True):
        request_password_reset(st.session_state.get("user_email"))




