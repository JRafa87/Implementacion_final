import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y CONEXIÓN A SUPABASE
# =================================================================

@st.cache_resource
def get_supabase() -> Client:
    """Inicializa y cachea el cliente de Supabase."""
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("ERROR: Faltan credenciales en secrets.toml.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

# Mapeo de claves de Python (minúscula) a PostgreSQL (Mantener original)
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
# 2. FUNCIONES CRUD (Lógica interna)
# -----------------------------------

def fetch_employees():
    try:
        response = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
        return [{k.lower(): v for k, v in record.items()} for record in response.data]
    except Exception as e:
        st.error(f"Error al cargar: {e}")
        return []

def fetch_employee_by_id(employee_number: int) -> Optional[dict]:
    try:
        response = supabase.table("empleados").select("*").eq("EmployeeNumber", employee_number).single().execute()
        return {k.lower(): v for k, v in response.data.items()} if response.data else None
    except Exception:
        return None

def get_next_employee_number() -> int:
    try:
        response = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
        return response.data[0]['EmployeeNumber'] + 1 if response.data else 1
    except Exception:
        return 1

def add_employee(employee_data: dict):
    pg_data = {COLUMN_MAPPING[k]: v for k, v in employee_data.items() if k in COLUMN_MAPPING}
    try:
        supabase.table("empleados").insert(pg_data).execute()
        st.success("✅ Registro guardado con éxito.")
    except Exception as e:
        st.error(f"Error al añadir: {e}")

def update_employee_record(employee_number: int, update_data: dict):
    pg_update_data = {COLUMN_MAPPING[k]: v for k, v in update_data.items() if k in COLUMN_MAPPING}
    try:
        supabase.table("empleados").update(pg_update_data).eq("EmployeeNumber", employee_number).execute()
        st.success(f"✅ Empleado {employee_number} actualizado.")
    except Exception as e:
        st.error(f"Error al actualizar: {e}")

def delete_employee_record(employee_number: int):
    try:
        supabase.table("empleados").delete().eq("EmployeeNumber", employee_number).execute()
        st.success(f"🗑️ Empleado {employee_number} eliminado.")
    except Exception as e:
        st.error(f"Error al eliminar: {e}")

# -----------------------------------
# 3. UTILIDADES DE INTERFAZ
# -----------------------------------

def clear_cache_and_rerun():
    st.cache_data.clear()
    st.rerun()

@st.cache_data(ttl=600)
def get_employees_data():
    """Prepara el DataFrame con nombres en español para la UI."""
    data = fetch_employees()
    if not data: return pd.DataFrame()
    df = pd.DataFrame(data)
    
    # Renombrado para la tabla visual
    df_visual = df.rename(columns={
        'employeenumber': 'ID', 'age': 'Edad', 'jobrole': 'Puesto', 'department': 'Departamento',
        'monthlyincome': 'Salario Mensual', 'fechaingreso': 'F. Ingreso', 'tipocontrato': 'T. Contrato'
    })
    
    # Limpieza de nulos
    for col in ['numerotardanzas', 'numerofaltas', 'Edad']:
        if col in df_visual.columns:
            df_visual[col] = df_visual[col].fillna(0).astype(int)
    
    return df_visual

# -----------------------------------
# 4. COMPONENTES DE LA PÁGINA
# -----------------------------------

def render_employee_management_page():
    st.title("👥 Gestión de Empleados")
    
    if "user_role" not in st.session_state or st.session_state.get("user_role") not in ["admin", "supervisor"]:
        st.error("🚫 Acceso Denegado.")
        return

    # Estados de formulario
    if "show_add_form" not in st.session_state: st.session_state["show_add_form"] = False
    if "employee_to_edit" not in st.session_state: st.session_state["employee_to_edit"] = None

    col_add, col_refresh = st.columns([1, 1])
    with col_add:
        if st.button("➕ Añadir Nuevo Colaborador"):
            st.session_state["show_add_form"] = True
            st.session_state["employee_to_edit"] = None
            st.rerun()
    with col_refresh:
        if st.button("🔄 Recargar Información"):
            clear_cache_and_rerun()

    # FORMULARIO DE ADICIÓN (Variables originales, etiquetas en español)
    if st.session_state["show_add_form"]:
        render_add_employee_form()

    # TABLA DE EMPLEADOS
    df = get_employees_data()
    if not df.empty:
        st.header("Lista de Colaboradores")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        selected_id = st.selectbox("Seleccione un empleado para gestionar:", [""] + df['ID'].tolist())
        if selected_id:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✏️ Editar Datos"):
                    st.session_state["employee_to_edit"] = selected_id
                    st.session_state["show_add_form"] = False
                    st.rerun()
            with c2:
                if st.button("🗑️ Eliminar de Base de Datos"):
                    delete_employee_record(selected_id)
                    clear_cache_and_rerun()
    else:
        st.info("No hay registros disponibles.")

    if st.session_state.get("employee_to_edit"):
        render_edit_employee_form(st.session_state["employee_to_edit"])

# -----------------------------------
# 5. FORMULARIOS EN ESPAÑOL
# -----------------------------------

def render_add_employee_form():
    st.header("Formulario de Registro")
    next_id = get_next_employee_number()
    
    with st.form("add_form", clear_on_submit=True):
        st.subheader("1. Información Personal y Puesto")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input("ID de Empleado", value=next_id, disabled=True)
            gender = st.selectbox("Género", ["Male", "Female"], format_func=lambda x: "Masculino" if x=="Male" else "Femenino")
            age = st.number_input("Edad", 18, 100, 30)
        with c2:
            maritalstatus = st.selectbox("Estado Civil", ["Single", "Married", "Divorced"], format_func=lambda x: {"Single":"Soltero/a", "Married":"Casado/a", "Divorced":"Divorciado/a"}[x])
            department = st.selectbox("Departamento", ["HR", "Tech", "Finance", "Marketing", "Research & Development"])
            jobrole = st.selectbox("Puesto", ["Manager", "Developer", "Analyst", "Sales Executive", "Research Scientist", "Laboratory Technician"])
        with c3:
            monthlyincome = st.number_input("Salario Mensual (USD)", min_value=0, value=3000)
            tipocontrato = st.selectbox("Tipo de Contrato", ["Fijo", "Temporal", "Servicios"])
            overtime = st.radio("Horas Extra", ["Yes", "No"], format_func=lambda x: "Sí" if x=="Yes" else "No")

        st.subheader("2. Historial y Métricas")
        c4, c5 = st.columns(2)
        with c4:
            fechaingreso = st.date_input("Fecha de Ingreso", date.today())
            yearsatcompany = st.number_input("Años en la Empresa", 0, 50, 0)
        with c5:
            numerotardanzas = st.number_input("Número de Tardanzas", 0, 100, 0)
            numerofaltas = st.number_input("Número de Faltas", 0, 100, 0)

        if st.form_submit_button("💾 Guardar Nuevo"):
            new_data = {
                "employeenumber": next_id, "age": age, "gender": gender, "department": department,
                "jobrole": jobrole, "monthlyincome": monthlyincome, "maritalstatus": maritalstatus,
                "overtime": overtime, "tipocontrato": tipocontrato, "fechaingreso": fechaingreso.isoformat(),
                "yearsatcompany": yearsatcompany, "numerotardanzas": numerotardanzas, "numerofaltas": numerofaltas
            }
            add_employee(new_data)
            st.session_state["show_add_form"] = False
            clear_cache_and_rerun()

def render_edit_employee_form(emp_id):
    emp_data = fetch_employee_by_id(emp_id)
    if not emp_data: return
    
    st.header(f"✏️ Editando Empleado: {emp_id}")
    with st.form("edit_form"):
        c1, c2 = st.columns(2)
        with c1:
            # Mantienen variables originales internamente
            new_income = st.number_input("Salario Mensual (USD)", value=int(emp_data.get('monthlyincome', 0)))
            new_dept = st.text_input("Departamento", value=emp_data.get('department', ''))
            new_role = st.text_input("Puesto", value=emp_data.get('jobrole', ''))
        with c2:
            new_tardanzas = st.number_input("Número de Tardanzas", value=int(emp_data.get('numerotardanzas', 0)))
            new_faltas = st.number_input("Número de Faltas", value=int(emp_data.get('numerofaltas', 0)))
            fechasalida = st.date_input("Fecha de Salida (Opcional)", value=None)

        if st.form_submit_button("💾 Actualizar Registro"):
            update_data = {
                "monthlyincome": new_income, "department": new_dept, "jobrole": new_role,
                "numerotardanzas": new_tardanzas, "numerofaltas": new_faltas,
                "fechasalida": fechasalida.isoformat() if fechasalida else None
            }
            update_employee_record(emp_id, update_data)
            st.session_state["employee_to_edit"] = None
            clear_cache_and_rerun()
        
        if st.form_submit_button("❌ Cancelar"):
            st.session_state["employee_to_edit"] = None
            st.rerun()














