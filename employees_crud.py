import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. MAPEOS Y TRADUCCIONES
# =================================================================

MAPEO_DEPTOS = {
    "Sales": "Ventas", 
    "Research & Development": "I+D / Desarrollo", 
    "Human Resources": "Recursos Humanos"
}

MAPEO_ROLES = {
    "Sales Executive": "Ejecutivo de Ventas", "Research Scientist": "Científico de Investigación",
    "Laboratory Technician": "Técnico de Laboratorio", "Manufacturing Director": "Director de Manufactura",
    "Healthcare Representative": "Representante de Salud", "Manager": "Gerente",
    "Sales Representative": "Representante de Ventas", "Research Director": "Director de Investigación",
    "Human Resources": "Recursos Humanos"
}

TRADUCCIONES_FIJAS = {
    "businesstravel": {"Non-Travel": "No viaja", "Travel_Rarely": "Viaja raramente", "Travel_Frequently": "Viaja frecuentemente"},
    "gender": {"Male": "Masculino", "Female": "Femenino"},
    "maritalstatus": {"Single": "Soltero/a", "Married": "Casado/a", "Divorced": "Divorciado/a"},
    "overtime": {"Yes": "Sí", "No": "No"}
}

COLUMN_MAPPING = {
    "employeenumber": "EmployeeNumber", "age": "Age", "businesstravel": "BusinessTravel",
    "department": "Department", "distancefromhome": "DistanceFromHome", "monthlyincome": "MonthlyIncome",
    "jobrole": "JobRole", "gender": "Gender", "maritalstatus": "MaritalStatus"
    # ... (demás mapeos se mantienen igual internamente)
}

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key)

supabase = get_supabase()

def fetch_employees():
    res = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
    return [{k.lower(): v for k, v in r.items()} for r in res.data]

# =================================================================
# 2. INTERFAZ DE USUARIO
# =================================================================

def render_employee_management_page():
    st.title("👥 Gestión de Colaboradores")

    if "edit_id" not in st.session_state: st.session_state.edit_id = None
    if "show_add" not in st.session_state: st.session_state.show_add = False

    # --- TABLA GENERAL (I+D / Desarrollo) ---
    raw_data = fetch_employees()
    if raw_data:
        df = pd.DataFrame(raw_data)
        # Reemplazo forzado para la visualización
        df['department'] = df['department'].replace(MAPEO_DEPTOS)
        df['jobrole'] = df['jobrole'].replace(MAPEO_ROLES)
        
        st.subheader("Listado General de Personal")
        st.dataframe(
            df[['employeenumber', 'age', 'department', 'jobrole', 'monthlyincome']].rename(columns={
                'employeenumber': 'ID', 'age': 'Edad', 'department': 'Departamento', 
                'jobrole': 'Puesto', 'monthlyincome': 'Sueldo'
            }), 
            use_container_width=True, hide_index=True
        )

    st.divider()

    # --- CONTENEDOR ÚNICO DE BÚSQUEDA ---
    with st.container():
        st.subheader("🔍 Localizar por ID")
        lista_ids = [e['employeenumber'] for e in raw_data] if raw_data else []
        
        # Unimos la lógica en un solo bloque de selección
        col1, col2 = st.columns([2, 1])
        with col1:
            id_seleccionado = st.selectbox("Seleccione ID de la lista o escriba el número:", 
                                         options=[None] + lista_ids, 
                                         format_func=lambda x: "Seleccione..." if x is None else f"ID: {x}")
        with col2:
            id_manual = st.number_input("Búsqueda Rápida (Número)", min_value=0, value=0)

        # Determinar el ID final
        id_final = id_seleccionado if id_seleccionado else (id_manual if id_manual > 0 else None)

        c_btn1, c_btn2, c_btn3 = st.columns(3)
        with c_btn1:
            if st.button("✏️ Editar Selección", use_container_width=True) and id_final:
                st.session_state.edit_id = id_final
                st.session_state.show_add = False
                st.rerun()
        with c_btn2:
            if st.button("🗑️ Eliminar Selección", use_container_width=True) and id_final:
                supabase.table("empleados").delete().eq("EmployeeNumber", id_final).execute()
                st.rerun()
        with c_btn3:
            if st.button("➕ Nuevo Registro", use_container_width=True):
                st.session_state.show_add = True
                st.session_state.edit_id = None
                st.rerun()

    # --- FORMULARIO CON RESTRICCIÓN DE EDAD ---
    if st.session_state.show_add or st.session_state.edit_id:
        st.divider()
        es_edicion = st.session_state.edit_id is not None
        prev_data = {}
        
        if es_edicion:
            res = supabase.table("empleados").select("*").eq("EmployeeNumber", st.session_state.edit_id).execute()
            if res.data:
                prev_data = {k.lower(): v for k, v in res.data[0].items()}

        st.subheader("📋 Datos del Colaborador")
        with st.form("main_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                # La edad bloquea el proceso si es < 18
                edad_input = st.number_input("Edad (Mínimo 18 años)", 0, 100, int(prev_data.get('age', 25)))
                depto_form = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()))
            with col_b:
                sueldo_form = st.number_input("Sueldo Mensual", 0, 50000, int(prev_data.get('monthlyincome', 2500)))
                puesto_form = st.selectbox("Puesto", list(MAPEO_ROLES.values()))

            # RESTRICCIÓN DE EDAD: Lógica de bloqueo total
            if edad_input < 18:
                st.error("⚠️ RESTRICCIÓN: No se puede registrar a menores de 18 años.")
                # No mostramos el botón de guardar si la edad es inválida
                can_submit = False
            else:
                can_submit = True

            st.write("---")
            b_guardar, b_cancelar = st.columns(2)
            
            with b_guardar:
                # Solo se procesa si can_submit es True
                if can_submit:
                    btn_save = st.form_submit_button("💾 GUARDAR CAMBIOS")
                else:
                    st.form_submit_button("💾 GUARDAR (BLOQUEADO)", disabled=True)
                    btn_save = False

            with b_cancelar:
                if st.form_submit_button("❌ CANCELAR"):
                    st.session_state.edit_id = None
                    st.session_state.show_add = False
                    st.rerun()

            if btn_save:
                # Lógica de guardado (Insert o Update)
                # ... (aquí va la lógica de Supabase explicada anteriormente)
                st.success("¡Datos guardados correctamente!")
                st.session_state.edit_id = None
                st.session_state.show_add = False
                st.rerun()

if __name__ == "__main__":
    render_employee_management_page()











