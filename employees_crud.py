import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ===========================================
# Función para inicializar y cachear el cliente de Supabase
# ===========================================
@st.cache_resource
def get_supabase() -> Client:
    """Inicializa y cachea el cliente de Supabase."""
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("ERROR: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml. La autenticación fallará.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

# ================================
# Mapeo de Claves (de Python a PostgreSQL)
# ================================
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

# ===========================
# Funciones CRUD para Empleados
# ===========================

def fetch_employees():
    """Obtiene todos los empleados de la tabla 'empleados' y filtra los activos."""
    try:
        # Filtrar empleados activos (sin fecha de salida)
        response = supabase.table("empleados").select("*").is_("FechaSalida", None).order("EmployeeNumber").execute()
        data = [{k.lower(): v for k, v in record.items()} for record in response.data]
        return data
    except Exception as e:
        st.error(f"Error al cargar empleados: {e}")
        return []

def add_employee(employee_data: dict):
    """Agrega un nuevo empleado a la tabla 'empleados'."""
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
    """Actualiza un empleado existente por su EmployeeNumber (PK)."""
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

# ============================
# Función para preparar datos de empleados
# ============================

def get_employees_data():
    """Carga los datos de empleados y los prepara para el display."""
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

# ================================
# Página de Gestión de Empleados
# ================================

def render_employee_management_page():
    """Página de Gestión de Empleados."""
    st.title("👥 Gestión de Empleados")
    st.markdown("Administración de perfiles y estados de los colaboradores de la empresa.")
    
    # Control de Acceso
    if st.session_state.get("user_role") not in ["admin", "supervisor"]:
        st.error("🚫 Acceso Denegado. Solo administradores y supervisores pueden gestionar empleados.")
        return

    # Botones de Acción
    col_add, col_refresh, col_spacer = st.columns([1, 1, 5])
    with col_add:
        if st.button("➕ Añadir Nuevo"):
            st.session_state["show_add_form"] = True
            st.experimental_rerun()
    with col_refresh:
        if st.button("🔄 Recargar Datos"):
            st.cache_data.clear()
            st.experimental_rerun()
    
    # Mostrar empleados
    df = get_employees_data()
    if df.empty:
        st.warning("No hay empleados registrados en la base de datos.")
        return
    
    employee_ids_list = df['ID'].tolist()
    selected_id = st.selectbox("Selecciona un Empleado para editar o eliminar:", options=[""] + employee_ids_list, index=0)

    display_df = df[['ID', 'Puesto', 'Depto', 'Salario Mensual', 'F. Ingreso', 'T. Contrato', 'age', 'maritalstatus', 'gender', 'overtime']]
    st.dataframe(display_df, use_container_width=True)

    st.markdown("---")
    if selected_id:
        emp_id = selected_id
        col_edit, col_delete, col_spacer = st.columns([1, 1, 4])
        with col_edit:
            if st.button("✏️ Editar Registro"):
                st.session_state["employee_to_edit"] = emp_id
                st.session_state["employee_to_delete"] = None
                st.experimental_rerun()
        with col_delete:
            if st.button("❌ Eliminar Registro"):
                st.session_state["employee_to_delete"] = emp_id
                st.session_state["employee_to_edit"] = None
                st.experimental_rerun()
        
        st.info(f"Seleccionado Empleado ID: **{emp_id}**.")

# Función de edición de empleados
if "employee_to_edit" in st.session_state and st.session_state["employee_to_edit"] is not None:
    emp_id = st.session_state["employee_to_edit"]
    df = get_employees_data()
    selected_row = df[df['ID'] == emp_id].iloc[0].to_dict()
    st.header(f"✏️ Editar Empleado ID: {emp_id}")
    
    with st.form("edit_employee_data_form"):
        st.text_input("EmployeeNumber (ID)", value=selected_row['ID'], disabled=True)
        edit_department = st.selectbox("Department", ["HR", "Sales", "Tech"], index=0)
        edit_jobrole = st.selectbox("JobRole", ["Manager", "Developer", "Analyst"], index=0)
        edit_monthlyincome = st.number_input("MonthlyIncome", value=selected_row['Salario Mensual'], min_value=0)
        
        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.form_submit_button("✅ Guardar Cambios"):
                update_data = {
                    "department": edit_department,
                    "jobrole": edit_jobrole,
                    "monthlyincome": edit_monthlyincome,
                }
                update_employee_record(emp_id, update_data)
                st.session_state["employee_to_edit"] = None
                st.experimental_rerun()
