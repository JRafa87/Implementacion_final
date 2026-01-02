import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS DE TRADUCCIÓN
# =================================================================

# Listas restringidas según tu solicitud
DEPARTAMENTOS_REQ = ["Sales", "Research & Development", "Human Resources"]
EDUCACION_REQ = ["Life Sciences", "Other", "Medical", "Marketing", "Technical Degree", "Human Resources"]
ROLES_REQ = ["Sales Executive", "Research Scientist", "Laboratory Technician", "Manufacturing Director", "Healthcare Representative", "Manager", "Sales Representative", "Research Director", "Human Resources"]

TRADUCCIONES = {
    "businesstravel": {"Non-Travel": "No viaja", "Travel_Rarely": "Viaja raramente", "Travel_Frequently": "Viaja frecuentemente"},
    "department": {k: ("Ventas" if k == "Sales" else "I+D / Desarrollo" if k == "Research & Development" else "Recursos Humanos") for k in DEPARTAMENTOS_REQ},
    "educationfield": {
        "Life Sciences": "Ciencias de la Vida", "Other": "Otros", "Medical": "Médico", 
        "Marketing": "Marketing", "Technical Degree": "Grado Técnico", "Human Resources": "Recursos Humanos"
    },
    "gender": {"Male": "Masculino", "Female": "Femenino"},
    "maritalstatus": {"Single": "Soltero/a", "Married": "Casado/a", "Divorced": "Divorciado/a"},
    "overtime": {"Yes": "Sí", "No": "No"},
    "jobrole": {k: k for k in ROLES_REQ} # Mantengo nombres de roles para consistencia
}

def get_raw_value(category, display_value):
    inv_map = {v: k for k, v in TRADUCCIONES.get(category, {}).items()}
    return inv_map.get(display_value, display_value)

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key)

supabase = get_supabase()

COLUMN_MAPPING = {
    "employeenumber": "EmployeeNumber", "age": "Age", "businesstravel": "BusinessTravel",
    "department": "Department", "distancefromhome": "DistanceFromHome", "education": "Education",
    "educationfield": "EducationField", "gender": "Gender", "joblevel": "JobLevel",
    "jobrole": "JobRole", "maritalstatus": "MaritalStatus", "monthlyincome": "MonthlyIncome", 
    "numcompaniesworked": "NumCompaniesWorked", "overtime": "OverTime", "performancerating": "PerformanceRating",
    "totalworkingyears": "TotalWorkingYears", "trainingtimeslastyear": "TrainingTimesLastyear",
    "yearsatcompany": "YearsAtCompany", "yearsincurrentrole": "YearsInCurrentRole",
    "yearssincelastpromotion": "YearsSinceLastPromotion", "yearswithcurrmanager": "YearsWithCurrManager",
    "tipocontrato": "Tipocontrato", "numerotardanzas": "NumeroTardanzas", "numerofaltas": "NumeroFaltas",
    "fechaingreso": "FechaIngreso", "fechasalida": "FechaSalida",
}

# -----------------------------------
# 2. FUNCIONES CRUD
# -----------------------------------

def fetch_employees():
    try:
        response = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
        return [{k.lower(): v for k, v in record.items()} for record in response.data]
    except Exception: return []

def update_employee(emp_id, update_data):
    pg_data = {COLUMN_MAPPING[k]: v for k, v in update_data.items() if k in COLUMN_MAPPING}
    supabase.table("empleados").update(pg_data).eq("EmployeeNumber", emp_id).execute()

def delete_employee(emp_id):
    supabase.table("empleados").delete().eq("EmployeeNumber", emp_id).execute()

def get_next_id():
    resp = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
    return (resp.data[0]['EmployeeNumber'] + 1) if resp.data else 1

# -----------------------------------
# 3. INTERFAZ DE USUARIO
# -----------------------------------

def render_employee_management_page():
    st.title("👥 Gestión de Empleados")

    if "edit_id" not in st.session_state: st.session_state.edit_id = None
    if "show_add" not in st.session_state: st.session_state.show_add = False

    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Nuevo Empleado"):
            st.session_state.show_add = True
            st.session_state.edit_id = None
    with col2:
        if st.button("🔄 Refrescar"): st.rerun()

    # FORMULARIO DE REGISTRO / EDICIÓN
    if st.session_state.show_add or st.session_state.edit_id:
        modo_edit = st.session_state.edit_id is not None
        titulo = f"Editar Empleado {st.session_state.edit_id}" if modo_edit else "Registrar Nuevo Empleado"
        
        # Si es edición, cargar datos previos
        emp_prev = {}
        if modo_edit:
            res = supabase.table("empleados").select("*").eq("EmployeeNumber", st.session_state.edit_id).single().execute()
            emp_prev = {k.lower(): v for k, v in res.data.items()}

        with st.form("form_empleado"):
            st.subheader(titulo)
            c1, c2, c3 = st.columns(3)
            with c1:
                age = st.number_input("Edad", 0, 100, int(emp_prev.get('age', 25)))
                gender = st.selectbox("Género", list(TRADUCCIONES["gender"].values()))
                marital = st.selectbox("Estado Civil", list(TRADUCCIONES["maritalstatus"].values()))
            with c2:
                dept = st.selectbox("Departamento", list(TRADUCCIONES["department"].values()))
                role = st.selectbox("Puesto", ROLES_REQ)
                income = st.number_input("Salario Mensual", 0, 50000, int(emp_prev.get('monthlyincome', 3000)))
            with c3:
                travel = st.selectbox("Viajes", list(TRADUCCIONES["businesstravel"].values()))
                ed_field = st.selectbox("Educación", list(TRADUCCIONES["educationfield"].values()))
                overtime = st.radio("Horas Extra", list(TRADUCCIONES["overtime"].values()), horizontal=True)

            # VALIDACIÓN DE EDAD
            es_valido = age >= 18
            if not es_valido:
                st.error("🚫 La edad debe ser 18 años o más para guardar.")

            cb1, cb2 = st.columns(2)
            with cb1:
                if st.form_submit_button("💾 Guardar", disabled=not es_valido):
                    data = {
                        "age": age, "gender": get_raw_value("gender", gender),
                        "maritalstatus": get_raw_value("maritalstatus", marital),
                        "department": get_raw_value("department", dept),
                        "jobrole": role, "monthlyincome": income,
                        "businesstravel": get_raw_value("businesstravel", travel),
                        "educationfield": get_raw_value("educationfield", ed_field),
                        "overtime": get_raw_value("overtime", overtime)
                    }
                    if modo_edit:
                        update_employee(st.session_state.edit_id, data)
                        st.success("Actualizado correctamente")
                    else:
                        data["employeenumber"] = get_next_id()
                        data["fechaingreso"] = date.today().isoformat()
                        pg_data = {COLUMN_MAPPING[k]: v for k, v in data.items() if k in COLUMN_MAPPING}
                        supabase.table("empleados").insert(pg_data).execute()
                        st.success("Creado correctamente")
                    
                    st.session_state.show_add = False
                    st.session_state.edit_id = None
                    st.rerun()
            with cb2:
                if st.form_submit_button("❌ Cancelar"):
                    st.session_state.show_add = False
                    st.session_state.edit_id = None
                    st.rerun()

    # TABLA Y ACCIONES
    data_raw = fetch_employees()
    if data_raw:
        df = pd.DataFrame(data_raw)
        st.subheader("Listado de Empleados")
        st.dataframe(df[['employeenumber', 'age', 'department', 'jobrole', 'monthlyincome']], use_container_width=True)

        selected_id = st.selectbox("Seleccione ID para Editar/Eliminar", [None] + [e['employeenumber'] for e in data_raw])
        if selected_id:
            ca, cb = st.columns(2)
            with ca:
                if st.button("✏️ Editar"):
                    st.session_state.edit_id = selected_id
                    st.rerun()
            with cb:
                if st.button("🗑️ Eliminar"):
                    delete_employee(selected_id)
                    st.warning(f"Empleado {selected_id} eliminado")
                    st.rerun()
    else:
        st.write("No hay datos disponibles.")

if __name__ == "__main__":
    render_employee_management_page()













