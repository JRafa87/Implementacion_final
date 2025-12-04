import streamlit as st
import authentication as auth_module  # Import correcto

# -----------------------------------------------------------
# 1. Configuración de página (DEBE SER LO PRIMERO)
# -----------------------------------------------------------
st.set_page_config(page_title="App Deserción Work", layout="wide")

# Debug opcional
# st.write("Contenido de auth_module:", dir(auth_module))

# -----------------------------------------------------------
# 2. Inicialización de Estado de Sesión
# -----------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if "user_role" not in st.session_state:
    st.session_state["user_role"] = "guest"

if "user_id" not in st.session_state:
    st.session_state["user_id"] = None

# -----------------------------------------------------------
# 3. Función principal
# -----------------------------------------------------------
def main_app():
    with st.sidebar:
        st.title("Menú")
        st.write(f"**Usuario:** {st.session_state.get('user_id', 'Desconocido')}")
        st.write(f"**Rol:** {st.session_state.get('user_role', 'guest')}")

        st.markdown("---")
        if st.button("Cerrar Sesión"):
            auth_module.handle_logout()

    st.title("App Deserción Laboral 📊")

    if st.session_state["user_role"] == "supervisor":
        st.success("👋 Bienvenido, Supervisor. Aquí tienes acceso a los datos sensibles.")
        st.metric(label="Tasa de Deserción", value="12%", delta="-2%")
    else:
        st.info("👋 Bienvenido. Estás viendo la vista estándar.")
        st.write("Aquí puedes ver información general sobre deserción laboral.")

# -----------------------------------------------------------
# 4. Control de acceso
# -----------------------------------------------------------
if st.session_state["authenticated"]:
    main_app()
else:
    auth_module.render_auth_page()
