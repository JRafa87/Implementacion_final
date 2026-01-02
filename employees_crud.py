import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS DE TRADUCCIÓN
# =================================================================

# Diccionarios para traducir datos de la BD (Inglés) -> Interfaz (Español)
TRADUCCIONES = {
    "businesstravel": {"Non-Travel": "No viaja", "Travel_Rarely": "Viaja raramente", "Travel_Frequently": "Viaja frecuentemente"},
    "department": {"Sales": "Ventas", "Research & Development": "I+D / Desarrollo", "Human Resources": "Recursos Humanos", "Tech": "Tecnología", "Finance": "Finanzas"},
    "educationfield": {"Life Sciences": "Ciencias de la Vida", "Medical": "Médico", "Marketing": "Marketing", "Technical Degree": "Grado Técnico", "Human Resources": "Recursos Humanos", "Other": "Otros"},
    "gender": {"Male": "Masculino", "Female": "Femenino"},
    "maritalstatus": {"Single": "Soltero/a", "Married": "Casado/a", "Divorced": "Divorciado/a"},
    "overtime": {"Yes": "Sí", "No": "No"},
    "jobrole": {
        "Manager": "Gerente", "Developer": "Desarrollador", "Analyst": "Analista", 
        "Sales Executive": "Ejecutivo de Ventas", "Research Scientist": "Científico de Investigación",
        "Laboratory Technician": "Técnico de Laboratorio", "Manufacturing Director": "Director de Manufactura",
        "Healthcare Representative": "Representante de Salud", "Human Resources": "Recursos Humanos"
    }
}

def get_raw_value(category, display_value):
    """Convierte el valor en español de la UI al valor original en inglés para la BD."""
    inv_map = {v: k for k, v in TRADUCCIONES.get(category, {}).items()}
    return inv_map.get(display_value, display_value)

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key)

supabase = get_supabase()

# Mapeo estricto a nombres originales de la base de datos
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

def get_next_id():
    resp = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
    return (resp.data[0]['EmployeeNumber'] + 1) if resp.data else 1

def add_employee(employee_data: dict):
    pg_data = {COLUMN_MAPPING[k]: v for k, v in employee_data.items() if k in COLUMN_MAPPING}
    supabase.table("empleados").insert(pg_data).execute()

# -----------------------------------
# 3. INTERFAZ DE USUARIO
# -----------------------------------

@st.cache_data(ttl=600) 
def get_employees_data():
    try:
        response = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
        data = [{k.lower(): v for k, v in record.items()} for record in response.data]
        if not data: return pd.DataFrame()
        
        df = pd.DataFrame(data)
        # Traducir contenido de las celdas para la vista de tabla
        for col, mapa in TRADUCCIONES.items():
            if col in df.columns:
                df[col] = df[col].map(mapa).fillna(df[col])
        return df
    except: return pd.DataFrame()

def render_employee_management_page():
    st.title("👥 Gestión de Colaboradores")

    if "show_add_form" not in st.session_state: st.session_state["show_add_form"] = False

    if st.button("➕ Registrar Nuevo Colaborador"):
        st.session_state["show_add_form"] = True

    if st.session_state["show_add_form"]:
        st.info("Complete todos los campos. La edad mínima legal es 18 años.")
        
        # Formulario con todos los campos originales
        with st.form("form_registro"):
            st.subheader("1. Información Personal y Puesto")
            c1, c2, c3 = st.columns(3)
            with c1:
                age = st.number_input("Edad", 0, 100, 25)
                gender = st.selectbox("Género", list(TRADUCCIONES["gender"].values()))
                marital = st.selectbox("Estado Civil", list(TRADUCCIONES["maritalstatus"].values()))
            with c2:
                dept = st.selectbox("Departamento", list(TRADUCCIONES["department"].values()))
                role = st.selectbox("Puesto de Trabajo", list(TRADUCCIONES["jobrole"].values()))
                level = st.slider("Nivel Laboral", 1, 5, 1)
            with c3:
                income = st.number_input("Ingreso Mensual (USD)", 0, 50000, 2500)
                contract = st.selectbox("Tipo de Contrato", ["Fijo", "Temporal", "Servicios"])
                overtime = st.radio("Horas Extra", list(TRADUCCIONES["overtime"].values()), horizontal=True)

            st.subheader("2. Detalles de Trayectoria")
            c4, c5, c6 = st.columns(3)
            with c4:
                travel = st.selectbox("Frecuencia de Viajes", list(TRADUCCIONES["businesstravel"].values()))
                dist = st.number_input("Distancia al Trabajo (km)", 1, 150, 5)
                education = st.number_input("Nivel Educativo (1-5)", 1, 5, 3)
            with c5:
                ed_field = st.selectbox("Campo de Estudio", list(TRADUCCIONES["educationfield"].values()))
                num_comp = st.number_input("Empresas Anteriores", 0, 20, 1)
                total_exp = st.number_input("Años Totales de Experiencia", 0, 50, 5)
            with c6:
                training = st.number_input("Capacitaciones (Año anterior)", 0, 10, 2)
                perf = st.number_input("Calificación de Desempeño (1-4)", 1, 4, 3)
                f_ingreso = st.date_input("Fecha de Ingreso", date.today())

            st.subheader("3. Estabilidad en la Empresa")
            c7, c8, c9 = st.columns(3)
            with c7:
                y_company = st.number_input("Años en la Empresa", 0, 50, 0)
                y_role = st.number_input("Años en el Puesto Actual", 0, 50, 0)
            with c8:
                y_promo = st.number_input("Años desde último ascenso", 0, 50, 0)
                y_manager = st.number_input("Años con jefe actual", 0, 50, 0)
            with c9:
                tardanzas = st.number_input("Número de Tardanzas", 0, 100, 0)
                faltas = st.number_input("Número de Faltas", 0, 100, 0)

            # --- VALIDACIÓN DE EDAD Y BLOQUEO DE BOTÓN ---
            can_save = True
            if age < 18:
                st.error("⚠️ No se puede registrar: El colaborador debe ser mayor de 18 años.")
                can_save = False

            col_btn1, col_btn2 = st.columns([1, 4])
            with col_btn1:
                submit = st.form_submit_button("💾 Guardar", disabled=not can_save)
            with col_btn2:
                if st.form_submit_button("❌ Cancelar"):
                    st.session_state["show_add_form"] = False
                    st.rerun()

            if submit and can_save:
                new_emp = {
                    "employeenumber": get_next_id(),
                    "age": age, "gender": get_raw_value("gender", gender),
                    "maritalstatus": get_raw_value("maritalstatus", marital),
                    "department": get_raw_value("department", dept),
                    "jobrole": get_raw_value("jobrole", role), "joblevel": level,
                    "monthlyincome": income, "tipocontrato": contract,
                    "overtime": get_raw_value("overtime", overtime),
                    "businesstravel": get_raw_value("businesstravel", travel),
                    "distancefromhome": dist, "education": education,
                    "educationfield": get_raw_value("educationfield", ed_field),
                    "numcompaniesworked": num_comp, "totalworkingyears": total_exp,
                    "trainingtimeslastyear": training, "performancerating": perf,
                    "fechaingreso": f_ingreso.isoformat(), "yearsatcompany": y_company,
                    "yearsincurrentrole": y_role, "yearssincelastpromotion": y_promo,
                    "yearswithcurrmanager": y_manager, "numerotardanzas": tardanzas,
                    "numerofaltas": faltas
                }
                add_employee(new_emp)
                st.session_state["show_add_form"] = False
                st.cache_data.clear()
                st.rerun()

    # Mostrar Tabla Traducida
    df = get_employees_data()
    if not df.empty:
        st.subheader("Listado Actualizado")
        # Mostrar con nombres de columnas originales o amigables según prefieras
        st.dataframe(df, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    render_employee_management_page()













