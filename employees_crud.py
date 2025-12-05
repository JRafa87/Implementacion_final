import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional

# Conexión a Supabase (asegúrate de tener tus credenciales)
# Código Corregido para forzar el error
@st.cache_resource
def get_supabase() -> Client:
    """Inicializa y cachea el cliente de Supabase."""
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    
    if not url or not key:
        error_msg = "Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml. ¡No se puede conectar a Supabase!"
        st.error(f"FATAL: {error_msg}") # Muestra el error en Streamlit
        raise Exception(error_msg) # <--- **Esto forzará que el script falle visiblemente.**
        
    return create_client(url, key)

# Mapeo de claves de Python (minúscula) a claves de PostgreSQL (CamelCase/PascalCase)
COLUMN_MAPPING = {
    "employeenumber": "EmployeeNumber",
    "age": "Age",
    "businesstravel": "BusinessTravel",
    "department": "Department",
    "distancefromhome": "DistanceFromHome",
    "education": "Education",
    "educationfield": "EducationField",
    "environmentsatisfaction": "EnvironmentSatisfaction",
    "gender": "Gender",
    "jobinvolvement": "JobInvolvement",
    "joblevel": "JobLevel",
    "jobrole": "JobRole",
    "jobsatisfaction": "JobSatisfaction",
    "maritalstatus": "MaritalStatus",
    "monthlyincome": "MonthlyIncome",
    "numcompaniesworked": "NumCompaniesWorked",
    "overtime": "OverTime",
    "performancerating": "PerformanceRating",
    "relationshipsatisfaction": "RelationshipSatisfaction",
    "totalworkingyears": "TotalWorkingYears",
    "trainingtimeslastyear": "TrainingTimesLastYear",
    "yearsatcompany": "YearsAtCompany",
    "yearsincurrentrole": "YearsInCurrentRole",
    "yearssincelastpromotion": "YearsSinceLastPromotion",
    "yearswithcurrmanager": "YearsWithCurrManager",
    "tipocontrato": "Tipocontrato",
    "numerotardanzas": "NumeroTardanzas",
    "numerofaltas": "NumeroFaltas",
    "fechaingreso": "FechaIngreso",
    "fechasalida": "FechaSalida",
}

# Listas de selección (ejemplos)
DEPARTMENTS = ['HR', 'Finance', 'Engineering', 'Sales']
JOB_ROLES = ['Manager', 'Engineer', 'Salesperson']
MARITAL_STATUS = ['Single', 'Married', 'Divorced']
GENDERS = ['Male', 'Female', 'Other']

# Funciones CRUD
def fetch_employees():
    """Obtiene todos los empleados de la tabla 'empleados'."""
    try:
        response = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
        data = [{k.lower(): v for k, v in record.items()} for record in response.data]
        return data
    except Exception as e:
        st.error(f"Error al cargar empleados: {e}")
        return []

def add_employee(employee_data: dict):
    """Agrega un nuevo empleado a la tabla 'empleados', mapeando las claves de Python a PostgreSQL."""
    pg_data = {}
    for py_key, pg_key in COLUMN_MAPPING.items():
        if py_key in employee_data:
            pg_data[pg_key] = employee_data[py_key]
    
    try:
        supabase.table("empleados").insert(pg_data).execute()
        st.success(f"Empleado con ID {employee_data['employeenumber']} añadido con éxito.")
    except Exception as e:
        st.error(f"Error al añadir empleado: {e}")

def update_employee_record(employee_number: int, update_data: dict):
    """Actualiza un empleado existente por su EmployeeNumber (PK), mapeando las claves de Python a PostgreSQL."""
    pg_update_data = {}
    for py_key, pg_key in COLUMN_MAPPING.items():
        if py_key in update_data:
            pg_update_data[pg_key] = update_data[py_key]
    
    try:
        supabase.table("empleados").update(pg_update_data).eq("EmployeeNumber", employee_number).execute()
        st.success(f"Empleado {employee_number} actualizado con éxito.")
    except Exception as e:
        st.error(f"Error al actualizar empleado: {e}")

def delete_employee_record(employee_number: int):
    """Elimina un empleado por su EmployeeNumber (PK)."""
    try:
        supabase.table("empleados").delete().eq("EmployeeNumber", employee_number).execute()
        st.success(f"Empleado {employee_number} eliminado con éxito.")
    except Exception as e:
        st.error(f"Error al eliminar empleado: {e}")

# Función de caché para obtener datos de empleados
@st.cache_data(ttl=600)  # Caché por 10 minutos
def get_employees_data():
    """Carga los datos de empleados de Supabase y los prepara para el display."""
    data = fetch_employees() 
    if data:
        df = pd.DataFrame(data)
        df.rename(columns={
            'employeenumber': 'ID',
            'jobrole': 'Puesto',
            'department': 'Depto',
            'monthlyincome': 'Salario Mensual',
            'fechaingreso': 'F. Ingreso',
            'tipocontrato': 'T. Contrato'
        }, inplace=True)
        
        df['numerotardanzas'] = df.get('numerotardanzas', 0).fillna(0).astype(int)
        df['numerofaltas'] = df.get('numerofaltas', 0).fillna(0).astype(int)
        df['age'] = df.get('age', 0).fillna(0).astype(int)
        df['totalworkingyears'] = df.get('totalworkingyears', 0).fillna(0).astype(int)
        df['yearsatcompany'] = df.get('yearsatcompany', 0).fillna(0).astype(int)
        df['overtime'] = df['overtime'].fillna('No')
        df['maritalstatus'] = df['maritalstatus'].fillna('Single')
        df['gender'] = df['gender'].fillna('Male')
        return df
    return pd.DataFrame()

# Página de gestión de empleados
def render_employee_management_page():
    """Página de Gestión de Empleados (CRUD con Streamlit)."""
    st.title("👥 Gestión de Empleados")
    st.markdown("Administración de perfiles y estados de los colaboradores de la empresa.")

    if st.session_state.get("user_role") not in ["admin", "supervisor"]:
        st.error("🚫 Acceso Denegado. Solo administradores y supervisores pueden gestionar empleados.")
        return

    # Botones de acción global
    col_add, col_refresh = st.columns([1, 1])
    
    with col_add:
        if st.button("➕ Añadir Nuevo"):
            st.session_state["show_add_form"] = True
            st.experimental_rerun()
    
    with col_refresh:
        if st.button("🔄 Recargar Datos"):
            st.cache_data.clear()  # Limpiar la caché de datos
            st.experimental_rerun()

    # Formulario de adición de empleado
    if st.session_state.get("show_add_form", False):
        st.header("Formulario de Nuevo Empleado")
        with st.form("add_employee_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_employee_number = st.number_input("EmployeeNumber (ID)", min_value=1, step=1)
                new_age = st.number_input("Age", min_value=18, max_value=100)
                new_department = st.selectbox("Department", DEPARTMENTS)
            with col2:
                new_jobrole = st.selectbox("JobRole", JOB_ROLES)
                new_monthlyincome = st.number_input("MonthlyIncome", min_value=0)
                new_maritalstatus = st.selectbox("MaritalStatus", MARITAL_STATUS)
                
            st.subheader("Otros Datos del Empleado")
            new_overtime = st.radio("OverTime", ("Yes", "No"))
            
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.form_submit_button("💾 Guardar Nuevo Empleado"):
                    if new_employee_number and new_monthlyincome:
                        employee_data = {
                            "employeenumber": new_employee_number,
                            "age": new_age,
                            "department": new_department,
                            "jobrole": new_jobrole,
                            "monthlyincome": new_monthlyincome,
                            "maritalstatus": new_maritalstatus,
                            "overtime": new_overtime
                        }
                        add_employee(employee_data)
                        st.session_state["show_add_form"] = False
                        st.cache_data.clear()  # Limpiar la caché
                        st.experimental_rerun()
                    else:
                        st.error("Por favor, complete al menos EmployeeNumber y MonthlyIncome.")
            with col_cancel:
                if st.form_submit_button("❌ Cancelar"):
                    st.session_state["show_add_form"] = False
                    st.experimental_rerun()

    # Mostrar empleados existentes
    df = get_employees_data()
    if not df.empty:
        st.header("Lista de Empleados")
        st.dataframe(df, use_container_width=True, hide_index=True)

        employee_ids_list = df['ID'].tolist()
        selected_id = st.selectbox("Selecciona un Empleado para editar o eliminar:", options=[""] + employee_ids_list)

        if selected_id:
            emp_id = selected_id
            col_edit, col_delete = st.columns([1, 1])
            with col_edit:
                if st.button("✏️ Editar Registro"):
                    st.session_state["employee_to_edit"] = emp_id
                    st.experimental_rerun()
            with col_delete:
                if st.button("❌ Eliminar Registro"):
                    st.session_state["employee_to_delete"] = emp_id
                    st.experimental_rerun()

    else:
        st.warning("No hay empleados registrados en la base de datos.")

# Ejecutar la página de gestión
render_employee_management_page()

