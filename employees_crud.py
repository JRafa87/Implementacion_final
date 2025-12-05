import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional

# Conexión a Supabase (asegúrate de tener tus credenciales)
@st.cache_resource
def get_supabase() -> Client:
    """Inicializa y cachea el cliente de Supabase."""
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("ERROR: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml. La autenticación fallará.")
        st.stop()  # Detenemos el script si las credenciales no están
    return create_client(url, key)

supabase = get_supabase()

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

# Funciones CRUD
def fetch_employees():
    """Obtiene todos los empleados de la tabla 'empleados' que no tienen fecha de salida."""
    try:
        response = supabase.table("empleados").select("*").is_("FechaSalida", None).order("EmployeeNumber").execute()
        data = [{k.lower(): v for k, v in record.items()} for record in response.data]
        return data
    except Exception as e:
        st.error(f"Error al cargar empleados: {e}")
        return []

def fetch_employee_by_id(employee_number: int) -> Optional[dict]:
    """
    Obtiene un único empleado por su EmployeeNumber.
    AGREGADA PARA CORREGIR EL NAMERROR EN LA EDICIÓN.
    """
    try:
        response = supabase.table("empleados").select("*").eq("EmployeeNumber", employee_number).single().execute()
        # Mapea las claves de PostgreSQL a minúsculas (Python)
        if response.data:
            return {k.lower(): v for k, v in response.data.items()}
        return None
    except Exception as e:
        # Esto atrapará errores como 'no se encontró el registro' o problemas de Supabase
        # st.error(f"Error al obtener empleado {employee_number}: {e}") # Comentado para evitar errores repetitivos en la UI
        return None

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

# Función para limpiar la caché y recargar la página
def clear_cache_and_rerun():
    st.cache_data.clear()  # Limpiar la caché de datos
    st.rerun()  # Recargar la aplicación

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

    if "user_role" not in st.session_state or st.session_state.get("user_role") not in ["admin", "supervisor"]:
        st.error("🚫 Acceso Denegado. Solo administradores y supervisores pueden gestionar empleados.")
        return

    # Botones de acción global
    col_add, col_refresh = st.columns([1, 1])
    
    # Inicializa el estado para el formulario de adición si no existe
    if "show_add_form" not in st.session_state:
        st.session_state["show_add_form"] = False

    with col_add:
        if st.button("➕ Añadir Nuevo"):
            st.session_state["show_add_form"] = True 
            # Asegurar que el formulario de edición esté oculto al abrir el de adición
            st.session_state["employee_to_edit"] = None 
            st.rerun() # Refresca para mostrar el formulario de adición inmediatamente
    
    with col_refresh:
        if st.button("🔄 Recargar Datos"):
            clear_cache_and_rerun()  # Limpiar la caché de datos y recargar

    # Formulario de adición de empleado
    if st.session_state["show_add_form"]:
        st.header("Formulario de Nuevo Empleado")
        with st.form("add_employee_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                # Asegurar un valor inicial para evitar errores de tipo
                new_employee_number = st.number_input("EmployeeNumber (ID)", min_value=1, step=1, key="add_id")
                new_age = st.number_input("Age", min_value=18, max_value=100, key="add_age", value=30)
                new_department = st.selectbox("Department", ["HR", "Tech", "Finance", "Marketing"], key="add_dept")
            with col2:
                new_jobrole = st.selectbox("JobRole", ["Manager", "Developer", "Analyst", "Support"], key="add_job")
                new_monthlyincome = st.number_input("MonthlyIncome", min_value=0, key="add_income")
                new_maritalstatus = st.selectbox("MaritalStatus", ["Single", "Married", "Divorced"], key="add_marital")
            
            st.subheader("Otros Datos del Empleado")
            new_overtime = st.radio("OverTime", ("Yes", "No"), key="add_overtime")
            
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.form_submit_button("💾 Guardar Nuevo Empleado"):
                    if new_employee_number and new_monthlyincome:
                        employee_data = {
                            "employeenumber": int(new_employee_number),
                            "age": int(new_age),
                            "department": new_department,
                            "jobrole": new_jobrole,
                            "monthlyincome": float(new_monthlyincome),
                            "maritalstatus": new_maritalstatus,
                            "overtime": new_overtime
                        }
                        add_employee(employee_data)
                        st.session_state["show_add_form"] = False
                        clear_cache_and_rerun()  # Limpiar la caché y recargar
                    else:
                        st.error("Por favor, complete al menos EmployeeNumber y MonthlyIncome.")
            with col_cancel:
                if st.form_submit_button("❌ Cancelar"):
                    st.session_state["show_add_form"] = False
                    st.rerun() # CORRECCIÓN: Un solo clic cierra la ventana.

    # Mostrar empleados existentes
    df = get_employees_data()
    if not df.empty:
        st.header("Lista de Empleados")
        st.dataframe(df, use_container_width=True, hide_index=True)

        employee_ids_list = df['ID'].tolist()
        
        # Ocultar el selector y los botones si el formulario de edición está visible
        if st.session_state.get("employee_to_edit"):
            st.session_state["show_select_box"] = False
        else:
            st.session_state["show_select_box"] = True

        if st.session_state["show_select_box"]:
            selected_id = st.selectbox(
                "Selecciona un Empleado para editar o eliminar:", 
                options=[""] + employee_ids_list, 
                key="select_employee"
            )

            if selected_id:
                emp_id = selected_id
                col_edit, col_delete = st.columns([1, 1])
                with col_edit:
                    if st.button("✏️ Editar Registro"):
                        st.session_state["employee_to_edit"] = emp_id
                        st.session_state["show_add_form"] = False # Asegura que el de adición esté oculto
                        st.rerun() # Recarga para mostrar el formulario de edición
                with col_delete:
                    if st.button("❌ Eliminar Registro"):
                        # Podrías añadir una confirmación aquí antes de eliminar
                        delete_employee_record(emp_id)
                        clear_cache_and_rerun()
                        
    else:
        st.warning("No hay empleados registrados en la base de datos.")

    # Mostrar formulario de edición si un ID está en el estado de la sesión
    if st.session_state.get("employee_to_edit"):
        render_edit_employee_form(st.session_state["employee_to_edit"])

# Página de edición de empleado
def render_edit_employee_form(emp_id):
    """Formulario de edición de empleado."""
    employee_data = fetch_employee_by_id(emp_id)
    
    if employee_data:
        st.header(f"Editar Empleado ID: {emp_id}")
        with st.form("edit_employee_form", clear_on_submit=True):
            # Usar valores de la base de datos como valor inicial (value)
            
            # Conversiones para asegurar tipos correctos para los widgets
            current_age = int(employee_data.get("age") or 0)
            current_income = float(employee_data.get("monthlyincome") or 0.0)
            current_dept = employee_data.get("department") or "HR"
            current_job = employee_data.get("jobrole") or "Manager"
            current_marital = employee_data.get("maritalstatus") or "Single"
            current_overtime = employee_data.get("overtime") or "No"

            new_age = st.number_input("Age", min_value=18, max_value=100, value=current_age)
            
            department_options = ["HR", "Tech", "Finance", "Marketing"]
            new_department = st.selectbox(
                "Department", 
                department_options, 
                index=department_options.index(current_dept) if current_dept in department_options else 0
            )
            jobrole_options = ["Manager", "Developer", "Analyst", "Support"]
            new_jobrole = st.selectbox(
                "JobRole", 
                jobrole_options, 
                index=jobrole_options.index(current_job) if current_job in jobrole_options else 0
            )
            new_monthlyincome = st.number_input("MonthlyIncome", min_value=0.0, value=current_income)
            marital_status_options = ["Single", "Married", "Divorced"]
            new_maritalstatus = st.selectbox(
                "MaritalStatus", 
                marital_status_options, 
                index=marital_status_options.index(current_marital) if current_marital in marital_status_options else 0
            )
            new_overtime = st.radio("OverTime", ("Yes", "No"), index=["Yes", "No"].index(current_overtime))

            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.form_submit_button("💾 Guardar Cambios"):
                    update_data = {
                        "age": int(new_age),
                        "department": new_department,
                        "jobrole": new_jobrole,
                        "monthlyincome": float(new_monthlyincome),
                        "maritalstatus": new_maritalstatus,
                        "overtime": new_overtime
                    }
                    update_employee_record(emp_id, update_data)
                    st.session_state["employee_to_edit"] = None # Ocultar el formulario después de guardar
                    clear_cache_and_rerun()  # Limpiar caché y recargar
            with col_cancel:
                if st.form_submit_button("❌ Cancelar Edición"):
                    st.session_state["employee_to_edit"] = None
                    st.rerun() # CORRECCIÓN: Un solo clic cierra la ventana.
    else:
        st.warning(f"No se pudo encontrar el empleado con ID {emp_id} o hubo un error de conexión.")
        st.session_state["employee_to_edit"] = None
        st.rerun()











