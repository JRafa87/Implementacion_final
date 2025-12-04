import streamlit as st
import auth as auth_module # Importa tu módulo de autenticación

# ============================================================
# 1. Configuración y Chequeo de Sesión Único
# ============================================================
st.set_page_config(page_title="App Deserción Work", layout="wide")

# Llama a la función de control de sesión UNIFICADA. 
# Esto establece el estado de st.session_state en cada ejecución.
session_is_active = auth_module.check_session_state_hybrid()

# app.py

def main_app():
    # Sidebar
    with st.sidebar:
        st.title("Menú")
        st.write(f"**Email:** {st.session_state.get('user_email', 'Desconocido')}")
        
        # Como no hay roles, la información es más simple
        st.write(f"**Estado:** Autenticado") 
        
        st.markdown("---")
        if st.button("Cerrar Sesión"):
            auth_module.handle_logout()

    # Contenido principal
    st.title("App Deserción Laboral 📊")

    # Muestra el mismo contenido para TODOS los usuarios autenticados
    st.success(f"👋 Bienvenido, {st.session_state['user_email']}. Tienes acceso completo a la aplicación.")
    st.metric(label="Tasa de Deserción", value="12%", delta="-2%")
    # ... (el resto de tu contenido)



