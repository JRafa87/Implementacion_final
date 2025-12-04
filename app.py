# app.py

import streamlit as st
import authentication_module as auth_module  # Importa tu módulo de autenticación

# ============================================================
# 1️⃣ Configuración de página
# ============================================================
st.set_page_config(
    page_title="App Deserción Laboral",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 2️⃣ Verificación de sesión
# ============================================================
session_is_active = auth_module.check_session_state_hybrid()

# Si no está autenticado, muestra la página de login y detiene la app
if not session_is_active:
    st.warning("No estás autenticado. Por favor inicia sesión.")
    auth_module.render_auth_page()
    st.stop()

# ============================================================
# 3️⃣ Función para el contenido principal
# ============================================================
def render_main_content():
    st.title("App Deserción Laboral 📊")
    
    email = st.session_state.get("user_email", "Desconocido")
    role = st.session_state.get("user_role", "guest")
    
    st.success(f"👋 Bienvenido, {email}. Tu rol: {role}. Tienes acceso completo a la aplicación.")
    
    # Ejemplo de métricas
    st.metric(label="Tasa de Deserción", value="12%", delta="-2%")
    st.metric(label="Empleados Activos", value="128", delta="+5%")
    
    # Aquí puedes agregar tus gráficos, tablas o dashboards con Plotly/Altair
    st.subheader("Gráfico de ejemplo")
    st.bar_chart({"Departamentos": [20, 15, 30], "Deserción": [5, 2, 8]})

# ============================================================
# 4️⃣ Sidebar
# ============================================================
def render_sidebar():
    with st.sidebar:
        st.title("Menú")
        st.write(f"**Email:** {st.session_state.get('user_email', 'Desconocido')}")
        st.write(f"**Rol:** {st.session_state.get('user_role', 'guest')}")
        st.write(f"**Estado:** {'Autenticado' if session_is_active else 'No autenticado'}")
        
        st.markdown("---")
        
        if st.button("Cerrar Sesión"):
            auth_module.handle_logout()

# ============================================================
# 5️⃣ Función principal
# ============================================================
def main_app():
    render_sidebar()
    render_main_content()

# ============================================================
# 6️⃣ Ejecutar la app
# ============================================================
if __name__ == "__main__":
    main_app()




