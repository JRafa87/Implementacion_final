import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
from datetime import date # Necesario para manejar inputs de fecha

# Conexión a Supabase (asegúrate de tener tus credenciales)
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

# Mapeo de claves de Python (minúscula) a claves de PostgreSQL (CamelCase/PascalCase)
COLUMN_MAPPING = {
    "employeenumber": "EmployeeNumber",
    "age": "Age",
    "businesstravel": "BusinessTravel",
    "department": "Department",
    "distancefromhome": "DistanceFromHome",
    "education": "Education",
    "educationfield": "EducationField",
    "environmentsatisfaction": "EnvironmentSatisfaction", # No está en tu lista, pero lo mantengo por si acaso
    "gender": "Gender", # No está en tu lista de edición, pero lo mantengo
    "jobinvolvement": "JobInvolvement", # No está en tu lista, pero lo mantengo por si acaso
    "joblevel": "JobLevel",
    "jobrole": "JobRole",
    "jobsatisfaction": "JobSatisfaction", # No está en tu lista, pero lo mantengo por si acaso
    "maritalstatus": "MaritalStatus", # No está en tu lista de edición, pero lo mantengo
    "monthlyincome": "MonthlyIncome",
    "numcompaniesworked": "NumCompaniesWorked",
    "overtime": "OverTime",
    "performancerating": "PerformanceRating",
    "relationshipsatisfaction": "RelationshipSatisfaction", # No está en tu lista, pero lo mantengo por si acaso
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

# --- (Las funciones CRUD como fetch_employees, add_employee, update_employee_record, etc. se mantienen igual) ---

def fetch_employees():
    """Obtiene todos los empleados de la tabla 'empleados' que no tienen fecha de salida."""
    try:
        response = supabase.table("empleados").select("*").is_("FechaSalida", None).order("EmployeeNumber").execute()
        # Mapea las claves de PostgreSQL a minúsculas (Python)
        data = [{k.lower(): v for k, v in record.items()} for record in response.data]
        return data
    except Exception as e:
        st.error(f"Error al cargar empleados: {e}")
        return []

def fetch_employee_by_id(employee_number: int) -> Optional[dict]:
    """Obtiene un único empleado por su EmployeeNumber."""
    try:
        response = supabase.table("empleados").select("*").eq("EmployeeNumber", employee_number).single().execute()
        if response.data:
            return {k.lower(): v for k, v in response.data.items()}
        return None
    except Exception as e:
        return None

def get_next_employee_number() -> int:
    """Consulta el máximo EmployeeNumber y devuelve el siguiente número disponible."""
    try:
        response = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
        if response.data and response.data[0]['EmployeeNumber'] is not None:
            max_id = response.data[0]['EmployeeNumber']
            return max_id + 1
        return 1
    except Exception as e:
        return 1

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

# --- (Las funciones de UI y caché se mantienen igual) ---

def clear_cache_and_rerun():
    """Función para limpiar la caché y recargar la página."""
    st.cache_data.clear()
    st.rerun()

@st.cache_data(ttl=600) 
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
        
        # Asegurar tipos y manejar NaNs (Mantenemos esta limpieza para la tabla)
        df['numerotardanzas'] = df.get('numerotardanzas', pd.Series([0] * len(df))).fillna(0).astype(int)
        df['numerofaltas'] = df.get('numerofaltas', pd.Series([0] * len(df))).fillna(0).astype(int)
        df['age'] = df.get('age', pd.Series([0] * len(df))).fillna(0).astype(int)
        df['totalworkingyears'] = df.get('totalworkingyears', pd.Series([0] * len(df))).fillna(0).astype(int)
        df['yearsatcompany'] = df.get('yearsatcompany', pd.Series([0] * len(df))).fillna(0).astype(int)
        df['overtime'] = df['overtime'].fillna('No')
        df['maritalstatus'] = df['maritalstatus'].fillna('Single')
        df['gender'] = df['gender'].fillna('Male')
        return df
    return pd.DataFrame()

# -----------------------------------
# PÁGINAS DE STREAMLIT (CORREGIDAS)
# -----------------------------------

def render_employee_management_page():
    """Página de Gestión de Empleados (CRUD con Streamlit)."""
    st.title("👥 Gestión de Empleados")
    st.markdown("Administración de perfiles y estados de los colaboradores de la empresa.")

    if "user_role" not in st.session_state or st.session_state.get("user_role") not in ["admin", "supervisor"]:
        st.error("🚫 Acceso Denegado. Solo administradores y supervisores pueden gestionar empleados.")
        return

    # Inicialización de estados
    if "show_add_form" not in st.session_state:
        st.session_state["show_add_form"] = False
    if "employee_to_edit" not in st.session_state:
        st.session_state["employee_to_edit"] = None

    # Botones de acción global
    col_add, col_refresh = st.columns([1, 1])
    
    with col_add:
        if st.button("➕ Añadir Nuevo"):
            st.session_state["show_add_form"] = True
            st.session_state["employee_to_edit"] = None # Ocultar edición
            st.rerun()
    
    with col_refresh:
        if st.button("🔄 Recargar Datos"):
            clear_cache_and_rerun()

    # =================================================================
    # FORMULARIO DE ADICIÓN DE EMPLEADO (Todos los campos)
    # =================================================================
    if st.session_state["show_add_form"]:
        st.header("Formulario de Nuevo Empleado")
        
        next_id = get_next_employee_number()
        
        with st.form("add_employee_form", clear_on_submit=True):
            st.subheader("Datos Clave")
            col1, col2, col3 = st.columns(3)
            with col1:
                new_employee_number = st.number_input("EmployeeNumber (ID)", min_value=1, step=1, value=next_id, disabled=True, key="add_id")
                new_gender = st.selectbox("Gender", ["Male", "Female"], key="add_gender")
                new_joblevel = st.number_input("JobLevel", min_value=1, max_value=5, key="add_joblevel", value=1)
            with col2:
                new_age = st.number_input("Age", min_value=18, max_value=100, key="add_age", value=30)
                new_maritalstatus = st.selectbox("MaritalStatus", ["Single", "Married", "Divorced"], key="add_marital")
                new_monthlyincome = st.number_input("MonthlyIncome", min_value=0, key="add_income", value=4000)
            with col3:
                new_fechaingreso = st.date_input("FechaIngreso", value=date.today(), key="add_f_ingreso")
                new_tipocontrato = st.selectbox("Tipocontrato", ["Fijo", "Temporal", "Servicios"], key="add_contrato")
                new_overtime = st.radio("OverTime", ("Yes", "No"), key="add_overtime", index=1)
            
            st.subheader("Experiencia y Puesto")
            col4, col5, col6 = st.columns(3)
            with col4:
                new_department = st.selectbox("Department", ["HR", "Tech", "Finance", "Marketing"], key="add_dept")
                new_jobrole = st.selectbox("JobRole", ["Manager", "Developer", "Analyst", "Support", "Sales Executive", "Research Scientist", "Laboratory Technician", "Manufacturing Director", "Healthcare Representative"], key="add_job")
                new_businesstravel = st.selectbox("BusinessTravel", ["Non-Travel", "Travel_Rarely", "Travel_Frequently"], key="add_travel")
            with col5:
                new_education = st.number_input("Education (1-5)", min_value=1, max_value=5, key="add_education", value=3)
                new_educationfield = st.selectbox("EducationField", ["Life Sciences", "Medical", "Marketing", "Technical Degree", "Human Resources", "Other"], key="add_ed_field")
                new_totalworkingyears = st.number_input("TotalWorkingYears", min_value=0, key="add_total_years", value=5)
            with col6:
                new_numcompaniesworked = st.number_input("NumCompaniesWorked", min_value=0, key="add_num_comp", value=1)
                new_distancefromhome = st.number_input("DistanceFromHome", min_value=1, key="add_distance", value=10)
                new_trainingtimeslastyear = st.number_input("TrainingTimesLastYear", min_value=0, max_value=6, key="add_training", value=3)

            st.subheader("Evaluación y Trayectoria Interna")
            col7, col8 = st.columns(2)
            with col7:
                new_yearsatcompany = st.number_input("YearsAtCompany", min_value=0, key="add_years_comp", value=5)
                new_yearsincurrentrole = st.number_input("YearsInCurrentRole", min_value=0, key="add_years_role", value=3)
                new_yearswithcurrmanager = st.number_input("YearsWithCurrManager", min_value=0, key="add_years_manager", value=2)
            with col8:
                new_performancerating = st.number_input("PerformanceRating (1-4)", min_value=1, max_value=4, key="add_perf_rating", value=3)
                new_yearssincelastpromotion = st.number_input("YearsSinceLastPromotion", min_value=0, key="add_last_promo", value=1)
                new_numerotardanzas = st.number_input("NumeroTardanzas", min_value=0, key="add_tardanzas", value=0)
                new_numerofaltas = st.number_input("NumeroFaltas", min_value=0, key="add_faltas", value=0)

            
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.form_submit_button("💾 Guardar Nuevo Empleado"):
                    # Verificación de campos obligatorios (simples)
                    if new_employee_number and new_monthlyincome:
                        employee_data = {
                            "employeenumber": int(new_employee_number),
                            "age": int(new_age),
                            "gender": new_gender,
                            "department": new_department,
                            "jobrole": new_jobrole,
                            "joblevel": int(new_joblevel),
                            "monthlyincome": int(new_monthlyincome),
                            "maritalstatus": new_maritalstatus,
                            "overtime": new_overtime,
                            "businesstravel": new_businesstravel,
                            "distancefromhome": int(new_distancefromhome),
                            "education": int(new_education),
                            "educationfield": new_educationfield,
                            "numcompaniesworked": int(new_numcompaniesworked),
                            "performancerating": int(new_performancerating),
                            "totalworkingyears": int(new_totalworkingyears),
                            "trainingtimeslastyear": int(new_trainingtimeslastyear),
                            "yearsatcompany": int(new_yearsatcompany),
                            "yearsincurrentrole": int(new_yearsincurrentrole),
                            "yearssincelastpromotion": int(new_yearssincelastpromotion),
                            "yearswithcurrmanager": int(new_yearswithcurrmanager),
                            "tipocontrato": new_tipocontrato,
                            "numerotardanzas": int(new_numerotardanzas),
                            "numerofaltas": int(new_numerofaltas),
                            "fechaingreso": new_fechaingreso.isoformat() if new_fechaingreso else None
                            # FechaSalida no se añade aquí
                        }
                        add_employee(employee_data)
                        st.session_state["show_add_form"] = False
                        clear_cache_and_rerun()
                    else:
                        st.error("Por favor, complete al menos EmployeeNumber y MonthlyIncome.")
            with col_cancel:
                if st.form_submit_button("❌ Cancelar"):
                    st.session_state["show_add_form"] = False
                    st.rerun()

    # Mostrar empleados existentes (Se mantiene igual)
    # ...
    
    df = get_employees_data()
    if not df.empty:
        st.header("Lista de Empleados")
        st.dataframe(df, use_container_width=True, hide_index=True)

        employee_ids_list = df['ID'].tolist()
        
        # Lógica para mostrar/ocultar el selector según si el formulario de edición está abierto
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
                        st.session_state["show_add_form"] = False
                        st.rerun()
                with col_delete:
                    if st.button("❌ Eliminar Registro"):
                        delete_employee_record(emp_id)
                        clear_cache_and_rerun()
                        
    else:
        st.warning("No hay empleados registrados en la base de datos.")

    # Mostrar formulario de edición si un ID está en el estado de la sesión
    if st.session_state.get("employee_to_edit"):
        render_edit_employee_form(st.session_state["employee_to_edit"])


def render_edit_employee_form(emp_id):
    """Formulario de edición de empleado (Campos específicos para edición)."""
    employee_data = fetch_employee_by_id(emp_id)
    
    if employee_data:
        st.header(f"Editar Empleado ID: {emp_id}")
        st.caption("Solo se muestran los campos que tienen un propósito de gestión o que cambian con el tiempo.")
        
        with st.form("edit_employee_form", clear_on_submit=False):
            
            # --- Conversiones iniciales para los valores ---
            def get_val(key, default_val):
                """Obtiene el valor del diccionario o el valor por defecto, manejando NaNs."""
                val = employee_data.get(key)
                if val is None:
                    return default_val
                
                # Manejo de tipos específicos
                if isinstance(default_val, int):
                    return int(val) if val else default_val
                if isinstance(default_val, float):
                    return float(val) if val else default_val
                if isinstance(default_val, date):
                    try:
                        return date.fromisoformat(val[:10])
                    except (TypeError, ValueError):
                        return default_val
                
                return val
            
            # -----------------------------------------------
            
            st.subheader("Datos de Empleo y Salario")
            col1, col2 = st.columns(2)
            with col1:
                new_department = st.selectbox("Department", ["HR", "Tech", "Finance", "Marketing"], index=["HR", "Tech", "Finance", "Marketing"].index(get_val("department", "HR")))
                new_jobrole = st.selectbox("JobRole", ["Manager", "Developer", "Analyst", "Support", "Sales Executive", "Research Scientist"], index=["Manager", "Developer", "Analyst", "Support", "Sales Executive", "Research Scientist"].index(get_val("jobrole", "Manager")))
                new_monthlyincome = st.number_input("MonthlyIncome", min_value=0, value=get_val("monthlyincome", 0))
                new_joblevel = st.number_input("JobLevel", min_value=1, max_value=5, value=get_val("joblevel", 1))
            with col2:
                new_tipocontrato = st.selectbox("Tipocontrato", ["Fijo", "Temporal", "Servicios"], index=["Fijo", "Temporal", "Servicios"].index(get_val("tipocontrato", "Fijo")))
                new_businesstravel = st.selectbox("BusinessTravel", ["Non-Travel", "Travel_Rarely", "Travel_Frequently"], index=["Non-Travel", "Travel_Rarely", "Travel_Frequently"].index(get_val("businesstravel", "Non-Travel")))
                new_overtime = st.radio("OverTime", ("Yes", "No"), index=["Yes", "No"].index(get_val("overtime", "No")))
                new_performancerating = st.number_input("PerformanceRating (1-4)", min_value=1, max_value=4, value=get_val("performancerating", 3))

            st.subheader("Historial Interno y Ausencias")
            col3, col4 = st.columns(2)
            with col3:
                # Variables de tiempo
                new_yearsatcompany = st.number_input("YearsAtCompany", min_value=0, value=get_val("yearsatcompany", 0))
                new_yearsincurrentrole = st.number_input("YearsInCurrentRole", min_value=0, value=get_val("yearsincurrentrole", 0))
                new_yearswithcurrmanager = st.number_input("YearsWithCurrManager", min_value=0, value=get_val("yearswithcurrmanager", 0))
                new_yearssincelastpromotion = st.number_input("YearsSinceLastPromotion", min_value=0, value=get_val("yearssincelastpromotion", 0))
                new_trainingtimeslastyear = st.number_input("TrainingTimesLastYear", min_value=0, max_value=6, value=get_val("trainingtimeslastyear", 0))
            with col4:
                # Variables de faltas/tardanzas
                new_numerotardanzas = st.number_input("NumeroTardanzas", min_value=0, value=get_val("numerotardanzas", 0))
                new_numerofaltas = st.number_input("NumeroFaltas", min_value=0, value=get_val("numerofaltas", 0))
                # Fecha de Ingreso y Salida (Campos clave de registro)
                st.info(f"Fecha de Ingreso: {get_val('fechaingreso', 'N/A')}")
                # Usamos el valor actual o None
                current_fecha_salida = get_val("fechasalida", None) 
                new_fechasalida = st.date_input("FechaSalida (Opcional)", value=current_fecha_salida, min_value=get_val("fechaingreso", date(1900, 1, 1)))

            
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.form_submit_button("💾 Guardar Cambios"):
                    update_data = {
                        "businesstravel": new_businesstravel,
                        "department": new_department,
                        "joblevel": int(new_joblevel),
                        "jobrole": new_jobrole,
                        "monthlyincome": int(new_monthlyincome),
                        "overtime": new_overtime,
                        "performancerating": int(new_performancerating),
                        "totalworkingyears": get_val("totalworkingyears", 0), # Se mantiene, asumido que no cambia aquí
                        "trainingtimeslastyear": int(new_trainingtimeslastyear),
                        "yearsatcompany": int(new_yearsatcompany),
                        "yearsincurrentrole": int(new_yearsincurrentrole),
                        "yearssincelastpromotion": int(new_yearssincelastpromotion),
                        "yearswithcurrmanager": int(new_yearswithcurrmanager),
                        "tipocontrato": new_tipocontrato,
                        "numerotardanzas": int(new_numerotardanzas),
                        "numerofaltas": int(new_numerofaltas),
                        # La fecha de salida debe ser None si se deja vacía
                        "fechasalida": new_fechasalida.isoformat() if new_fechasalida else None 
                    }
                    
                    # Filtramos los campos que son solo de lectura o irrelevantes para la edición si es necesario
                    # (En este caso, se asume que todos los campos del formulario son editables o necesarios)
                    
                    update_employee_record(emp_id, update_data)
                    st.session_state["employee_to_edit"] = None
                    clear_cache_and_rerun()
            
            with col_cancel:
                if st.form_submit_button("❌ Cancelar Edición"):
                    st.session_state["employee_to_edit"] = None
                    st.rerun()
    else:
        st.warning(f"No se pudo encontrar el empleado con ID {emp_id} o hubo un error de conexión.")
        st.session_state["employee_to_edit"] = None
        st.rerun()












