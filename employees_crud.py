import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS DE TRADUCCIÓN
# =================================================================

# Diccionarios para traducir datos crudos de la BD a la interfaz
TRADUCCIONES = {
    "businesstravel": {"Non-Travel": "No viaja", "Travel_Rarely": "Viaja raramente", "Travel_Frequently": "Viaja frecuentemente"},
    "department": {"Sales": "Ventas", "Research & Development": "I+D / Desarrollo", "Human Resources": "Recursos Humanos", "Tech": "Tecnología", "Finance": "Finanzas", "Marketing": "Marketing"},
    "educationfield": {"Life Sciences": "Ciencias de la Vida", "Medical": "Médico", "Marketing": "Marketing", "Technical Degree": "Grado Técnico", "Human Resources": "Recursos Humanos", "Other": "Otros"},
    "gender": {"Male": "Masculino", "Female": "Femenino"},
    "maritalstatus": {"Single": "Soltero/a", "Married": "Casado/a", "Divorced": "Divorciado/a"},
    "overtime": {"Yes": "Sí", "No": "No"}
}

# Mapeo inverso para guardar en la BD (Español -> Inglés)
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
    "educationfield": "EducationField", "environmentsatisfaction": "EnvironmentSatisfaction",
    "gender": "Gender", "jobinvolvement": "JobInvolvement", "joblevel": "JobLevel",
    "jobrole": "JobRole", "jobsatisfaction": "JobSatisfaction", "maritalstatus": "MaritalStatus",
    "monthlyincome": "MonthlyIncome", "numcompaniesworked": "NumCompaniesWorked", "overtime": "OverTime",
    "performancerating": "PerformanceRating", "relationshipsatisfaction": "RelationshipSatisfaction",
    "totalworkingyears": "TotalWorkingYears", "trainingtimeslastyear": "TrainingTimesLastyear",
    "yearsatcompany": "YearsAtCompany", "yearsincurrentrole": "YearsInCurrentRole",
    "yearssincelastpromotion": "YearsSinceLastPromotion", "yearswithcurrmanager": "YearsWithCurrManager",
    "tipocontrato": "Tipocontrato", "numerotardanzas": "NumeroTardanzas", "numerofaltas": "NumeroFaltas",
    "fechaingreso": "FechaIngreso", "fechasalida": "FechaSalida",
}

# -----------------------------------
# 2. FUNCIONES CRUD (Sin cambios en lógica)
# -----------------------------------

def fetch_employees():
    try:
        response = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
        return [{k.lower(): v for k, v in record.items()} for record in response.data]
    except Exception as e:
        st.error(f"Error: {e}")
        return []

def add_employee(employee_data: dict):
    pg_data = {COLUMN_MAPPING[k]: v for k, v in employee_data.items() if k in COLUMN_MAPPING}
    supabase.table("empleados").insert(pg_data).execute()

# -----------------------------------
# 3. INTERFAZ Y TRADUCCIÓN VISUAL
# -----------------------------------

@st.cache_data(ttl=600) 
def get_employees_data():
    data = fetch_employees() 
    if not data: return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # TRADUCCIÓN DE LOS DATOS EN LA TABLA
    for col, mapa in TRADUCCIONES.items():
        if col in df.columns:
            df[col] = df[col].map(mapa).fillna(df[col])

    # Renombrar encabezados de la tabla
    return df.rename(columns={
        'employeenumber': 'ID', 'age': 'Edad', 'businesstravel': 'Viajes',
        'department': 'Depto', 'distancefromhome': 'Distancia Km',
        'education': 'Educación', 'educationfield': 'Campo Estudio',
        'gender': 'Género', 'joblevel': 'Nivel', 'jobrole': 'Puesto',
        'maritalstatus': 'Estado Civil', 'monthlyincome': 'Sueldo'
    })

def render_employee_management_page():
    st.title("👥 Gestión de Empleados")

    if st.button("➕ Añadir Nuevo"):
        st.session_state["show_add_form"] = True

    if st.session_state.get("show_add_form"):
        with st.form("add_form"):
            st.subheader("1. Datos Clave")
            c1, c2, c3 = st.columns(3)
            with c1:
                age = st.number_input("Edad", 18, 70, 30)
                # Selectbox con opciones en ESPAÑOL
                gender = st.selectbox("Género", list(TRADUCCIONES["gender"].values()))
            with c2:
                marital = st.selectbox("Estado Civil", list(TRADUCCIONES["maritalstatus"].values()))
                income = st.number_input("Ingreso Mensual", 0, 50000, 3000)
            with c3:
                contract = st.selectbox("Tipo de Contrato", ["Fijo", "Temporal", "Servicios"])
                overtime = st.radio("Horas Extra", list(TRADUCCIONES["overtime"].values()))

            st.subheader("2. Experiencia y Puesto")
            c4, c5, c6 = st.columns(3)
            with c4:
                dept = st.selectbox("Departamento", list(TRADUCCIONES["department"].values()))
                travel = st.selectbox("Viajes de Negocios", list(TRADUCCIONES["businesstravel"].values()))
            with c5:
                ed_field = st.selectbox("Campo de Educación", list(TRADUCCIONES["educationfield"].values()))
                dist = st.number_input("Distancia al Hogar (km)", 1, 100, 10)
            with c6:
                total_y = st.number_input("Años Experiencia Total", 0, 50, 5)
                training = st.number_input("Capacitaciones Año Pasado", 0, 10, 2)

            if st.form_submit_button("💾 Guardar"):
                # Convertimos de vuelta a INGLÉS para la BD
                new_data = {
                    "employeenumber": 999, # Lógica de ID omitida por brevedad
                    "age": age,
                    "gender": get_raw_value("gender", gender),
                    "maritalstatus": get_raw_value("maritalstatus", marital),
                    "monthlyincome": income,
                    "tipocontrato": contract,
                    "overtime": get_raw_value("overtime", overtime),
                    "department": get_raw_value("department", dept),
                    "businesstravel": get_raw_value("businesstravel", travel),
                    "educationfield": get_raw_value("educationfield", ed_field),
                    "distancefromhome": dist,
                    "totalworkingyears": total_y,
                    "trainingtimeslastyear": training,
                    "fechaingreso": date.today().isoformat()
                }
                add_employee(new_data)
                st.session_state["show_add_form"] = False
                st.cache_data.clear()
                st.rerun()

    # Mostrar la tabla ya traducida
    df = get_employees_data()
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    if "user_role" not in st.session_state: st.session_state["user_role"] = "admin"
    render_employee_management_page()














