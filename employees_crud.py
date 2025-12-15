import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional

# =====================================================
# CONEXIÓN SUPABASE
# =====================================================
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("Faltan credenciales Supabase")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

# =====================================================
# COLUMNAS
# =====================================================
ALL_FIELDS = [
    "employeenumber", "age", "businesstravel", "department",
    "distancefromhome", "education", "educationfield", "gender",
    "joblevel", "jobrole", "maritalstatus", "monthlyincome",
    "numcompaniesworked", "overtime", "performancerating",
    "totalworkingyears", "yearsatcompany", "yearsincurrentrole",
    "yearssincelastpromotion", "yearswithcurrmanager",
    "tipocontrato", "numerotardanzas", "numerofaltas",
    "trainingtimeslastyear", "fechaingreso", "fechasalida",
    "percentsalaryhike"
]

COLUMN_MAPPING = {k: k.capitalize() for k in ALL_FIELDS}
COLUMN_MAPPING["percentsalaryhike"] = "PercentSalaryHike"
COLUMN_MAPPING["tipocontrato"] = "Tipocontrato"

# =====================================================
# HELPERS
# =====================================================
def get_next_employee_number() -> int:
    r = supabase.table("empleados").select("EmployeeNumber").order(
        "EmployeeNumber", desc=True).limit(1).execute()
    return (r.data[0]["EmployeeNumber"] + 1) if r.data else 1

def add_employee(data: dict):
    pg = {COLUMN_MAPPING[k]: v for k, v in data.items()}
    supabase.table("empleados").insert(pg).execute()
    st.success("Empleado registrado correctamente")

def fetch_employee_by_id(emp_id: int) -> Optional[dict]:
    r = supabase.table("empleados").select("*").eq(
        "EmployeeNumber", emp_id).single().execute()
    return {k.lower(): v for k, v in r.data.items()} if r.data else None

def update_employee(emp_id: int, data: dict):
    pg = {COLUMN_MAPPING[k]: v for k, v in data.items()}
    supabase.table("empleados").update(pg).eq(
        "EmployeeNumber", emp_id).execute()
    st.success("Empleado actualizado")

# =====================================================
# UI – NUEVO EMPLEADO
# =====================================================
def render_add_employee():
    st.subheader("➕ Nuevo Empleado")

    emp_id = get_next_employee_number()

    with st.form("add_emp"):
        st.number_input("EmployeeNumber", value=emp_id, disabled=True)

        col1, col2 = st.columns(2)

        with col1:
            age = st.number_input("Age", 18, 100, 30)
            gender = st.selectbox("Gender", ["Male", "Female"])
            marital = st.selectbox("MaritalStatus", ["Single", "Married", "Divorced"])
            dept = st.text_input("Department")
            job = st.text_input("JobRole")
            joblevel = st.number_input("JobLevel", 1, 5, 1)
            education = st.number_input("Education", 1, 5, 3)
            educationfield = st.text_input("EducationField")

        with col2:
            income = st.number_input("MonthlyIncome", 0)
            hike = st.number_input("PercentSalaryHike", 0, 100, 10)
            travel = st.selectbox("BusinessTravel", ["Rarely", "Frequently", "Non-Travel"])
            overtime = st.selectbox("OverTime", ["Yes", "No"])
            perf = st.number_input("PerformanceRating", 1, 5, 3)
            distance = st.number_input("DistanceFromHome", 0)
            companies = st.number_input("NumCompaniesWorked", 0)
            tipocontrato = st.selectbox("Tipo Contrato", ["Indefinido", "Temporal"])

        fecha_ing = st.text_input("FechaIngreso (dd/mm/yyyy)")
        fecha_sal = st.text_input("FechaSalida (dd/mm/yyyy)", value="")

        if st.form_submit_button("Guardar"):
            add_employee({
                "employeenumber": emp_id,
                "age": age,
                "gender": gender,
                "maritalstatus": marital,
                "department": dept,
                "jobrole": job,
                "joblevel": joblevel,
                "education": education,
                "educationfield": educationfield,
                "monthlyincome": income,
                "percentsalaryhike": hike,
                "businesstravel": travel,
                "overtime": overtime,
                "performancerating": perf,
                "distancefromhome": distance,
                "numcompaniesworked": companies,
                "tipocontrato": tipocontrato,
                "fechaingreso": fecha_ing,
                "fechasalida": fecha_sal or None
            })

# =====================================================
# UI – EDITAR EMPLEADO
# =====================================================
def render_edit_employee(emp_id: int):
    data = fetch_employee_by_id(emp_id)
    if not data:
        st.error("Empleado no encontrado")
        return

    st.subheader(f"✏️ Editar Empleado {emp_id}")

    with st.form("edit_emp"):
        income = st.number_input(
            "MonthlyIncome", value=int(data.get("monthlyincome", 0))
        )
        hike = st.number_input(
            "PercentSalaryHike", value=int(data.get("percentsalaryhike", 0))
        )

        if st.form_submit_button("Guardar cambios"):
            update_employee(emp_id, {
                "monthlyincome": income,
                "percentsalaryhike": hike
            })

# =====================================================
# MAIN
# =====================================================
def render_employee_management_page():
    st.title("👥 Gestión de Empleados")

    render_add_employee()

    st.divider()
    emp_id = st.number_input("Editar EmployeeNumber", min_value=1, step=1)
    if st.button("Cargar empleado"):
        render_edit_employee(emp_id)












