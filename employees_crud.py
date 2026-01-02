import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y CONEXIÓN
# =================================================================

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
    "totalworkingyears": "TotalWorkingYears", "trainingtimeslastyear": "TrainingTimesLastYear",
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
    except Exception as e:
        st.error(f"Error: {e}")
        return []

def fetch_employee_by_id(emp_id: int):
    try:
        response = supabase.table("empleados").select("*").eq("EmployeeNumber", emp_id).single().execute()
        return {k.lower(): v for k, v in response.data.items()} if response.data else None
    except Exception: return None

def update_employee_record(emp_id: int, update_data: dict):
    pg_update = {COLUMN_MAPPING[k]: v for k, v in update_data.items() if k in COLUMN_MAPPING}
    supabase.table("empleados").update(pg_update).eq("EmployeeNumber", emp_id).execute()

def add_employee(employee_data: dict):
    pg_data = {COLUMN_MAPPING[k]: v for k, v in employee_data.items() if k in COLUMN_MAPPING}
    supabase.table("empleados").insert(pg_data).execute()

# -----------------------------------
# 3. INTERFAZ Y FORMULARIOS COMPLETOS
# -----------------------------------

@st.cache_data(ttl=600)
def get_employees_data():
    data = fetch_employees()
    if not data: return pd.DataFrame()
    df = pd.DataFrame(data)
    # Solo cambiamos el nombre de la columna para la tabla visual
    return df.rename(columns={
        'employeenumber': 'ID', 'age': 'Edad', 'jobrole': 'Puesto', 
        'department': 'Depto', 'monthlyincome': 'Salario Mensual'
    })

def render_employee_management_page():
    st.title("👥 Gestión Completa de Colaboradores")
    
    if "show_add_form" not in st.session_state: st.session_state["show_add_form"] = False
    if "edit_id" not in st.session_state: st.session_state["edit_id"] = None

    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Registrar Nuevo"):
            st.session_state["show_add_form"] = True
            st.session_state["edit_id"] = None
    with col2:
        if st.button("🔄 Actualizar Tabla"):
            st.cache_data.clear()
            st.rerun()

    # --- FORMULARIO DE ADICIÓN COMPLETO ---
    if st.session_state["show_add_form"]:
        with st.form("form_add"):
            st.subheader("Datos del Nuevo Colaborador")
            c1, c2, c3 = st.columns(3)
            with c1:
                age = st.number_input("Edad", 18, 80, 30)
                gender = st.selectbox("Género", ["Male", "Female"], format_func=lambda x: "Masculino" if x=="Male" else "Femenino")
                maritalstatus = st.selectbox("Estado Civil", ["Single", "Married", "Divorced"], format_func=lambda x: "Soltero" if x=="Single" else ("Casado" if x=="Married" else "Divorciado"))
            with c2:
                department = st.selectbox("Departamento", ["HR", "Tech", "Finance", "Sales", "R&D"])
                jobrole = st.selectbox("Puesto", ["Manager", "Developer", "Analyst", "Scientist", "Technician"])
                joblevel = st.slider("Nivel de Puesto", 1, 5, 1)
            with c3:
                monthlyincome = st.number_input("Salario Mensual", 0, 50000, 3000)
                tipocontrato = st.selectbox("Tipo de Contrato", ["Fijo", "Temporal", "Servicios"])
                overtime = st.radio("Horas Extra", ["Yes", "No"], format_func=lambda x: "Sí" if x=="Yes" else "No")

            st.subheader("Trayectoria y Desempeño")
            c4, c5, c6 = st.columns(3)
            with c4:
                businesstravel = st.selectbox("Viajes de Negocio", ["Non-Travel", "Travel_Rarely", "Travel_Frequently"], format_func=lambda x: "No viaja" if x=="Non-Travel" else "Rara vez" if x=="Travel_Rarely" else "Frecuente")
                distancefromhome = st.number_input("Distancia al Hogar (km)", 1, 100, 5)
                education = st.number_input("Nivel Educativo (1-5)", 1, 5, 3)
            with c5:
                numcompaniesworked = st.number_input("Empresas Anteriores", 0, 15, 1)
                totalworkingyears = st.number_input("Total Años Experiencia", 0, 50, 5)
                trainingtimeslastyear = st.number_input("Capacitaciones Año Pasado", 0, 10, 2)
            with c6:
                yearsatcompany = st.number_input("Años en esta Empresa", 0, 50, 0)
                performancerating = st.number_input("Calificación Desempeño (1-4)", 1, 4, 3)
                fechaingreso = st.date_input("Fecha de Ingreso", date.today())

            if st.form_submit_button("💾 Guardar"):
                # Se usan los nombres de variables originales para el diccionario
                new_data = {
                    "employeenumber": (supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute().data[0]['EmployeeNumber'] + 1),
                    "age": age, "gender": gender, "maritalstatus": maritalstatus, "department": department,
                    "jobrole": jobrole, "joblevel": joblevel, "monthlyincome": monthlyincome, "tipocontrato": tipocontrato,
                    "overtime": overtime, "businesstravel": businesstravel, "distancefromhome": distancefromhome,
                    "education": education, "numcompaniesworked": numcompaniesworked, "totalworkingyears": totalworkingyears,
                    "trainingtimeslastyear": trainingtimeslastyear, "yearsatcompany": yearsatcompany, 
                    "performancerating": performancerating, "fechaingreso": fechaingreso.isoformat()
                }
                add_employee(new_data)
                st.session_state["show_add_form"] = False
                st.cache_data.clear()
                st.rerun()

    # --- TABLA Y EDICIÓN ---
    df = get_employees_data()
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        sel_id = st.selectbox("Seleccione ID para Editar:", [""] + df['ID'].tolist())
        if sel_id and st.button("✏️ Abrir Editor"):
            st.session_state["edit_id"] = sel_id
            st.rerun()

    if st.session_state["edit_id"]:
        render_edit_form(st.session_state["edit_id"])

def render_edit_form(emp_id):
    data = fetch_employee_by_id(emp_id)
    if not data: return
    
    with st.form("edit_form"):
        st.header(f"Editando Colaborador ID: {emp_id}")
        c1, c2 = st.columns(2)
        with c1:
            # Labels en español, variables internas originales
            new_income = st.number_input("Salario Mensual", value=int(data.get('monthlyincome', 0)))
            new_role = st.selectbox("Puesto", ["Manager", "Developer", "Analyst", "Scientist"], index=0)
            new_dept = st.selectbox("Departamento", ["HR", "Tech", "Finance", "Sales"], index=0)
        with c2:
            new_tardanzas = st.number_input("Número de Tardanzas", value=int(data.get('numerotardanzas', 0)))
            new_faltas = st.number_input("Número de Faltas", value=int(data.get('numerofaltas', 0)))
            new_salida = st.date_input("Fecha de Salida (Baja)", value=None)

        if st.form_submit_button("✅ Actualizar"):
            update_employee_record(emp_id, {
                "monthlyincome": new_income, "jobrole": new_role, "department": new_dept,
                "numerotardanzas": new_tardanzas, "numerofaltas": new_faltas,
                "fechasalida": new_salida.isoformat() if new_salida else None
            })
            st.session_state["edit_id"] = None
            st.cache_data.clear()
            st.rerun()

if __name__ == "__main__":
    render_employee_management_page()














