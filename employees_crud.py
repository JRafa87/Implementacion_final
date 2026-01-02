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
        st.error("ERROR: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml. La autenticación fallará.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

# Mapeo de claves de Python (minúscula) a claves de PostgreSQL (CamelCase/PascalCase)
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
# 2. FUNCIONES CRUD
# -----------------------------------

def fetch_employees():
    """Obtiene todos los empleados de la tabla 'empleados'."""
    try:
        response = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
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

# -----------------------------------
# 3. FUNCIONES DE UI Y UTILIDAD
# -----------------------------------

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
            'employeenumber': 'ID', 'jobrole': 'Puesto', 'department': 'Depto',
            'monthlyincome': 'Salario Mensual', 'fechaingreso': 'F. Ingreso', 'tipocontrato': 'T. Contrato'
        }, inplace=True)
        
        for col in ['numerotardanzas', 'numerofaltas', 'age', 'totalworkingyears', 'yearsatcompany']:
             df[col] = df.get(col, pd.Series([0] * len(df))).fillna(0).astype(int)
        
        df['overtime'] = df['overtime'].fillna('No')
        df['maritalstatus'] = df['maritalstatus'].fillna('Single')
        df['gender'] = df['gender'].fillna('Male')
        return df
    return pd.DataFrame()

def get_unique_options(df: pd.DataFrame, column_name: str, default_options: list) -> list:
    if df.empty or column_name not in df.columns:
        return default_options
        
    unique_vals = df[column_name].dropna().unique().tolist()
    unique_vals = [str(v).strip() for v in unique_vals if v is not None]
    
    for opt in default_options:
        if str(opt).strip() not in unique_vals:
            unique_vals.append(str(opt).strip())
    
    unique_vals.sort()
    return unique_vals

def get_safe_index(options_list: list, current_value: str, default_index=0):
    try:
        return options_list.index(current_value.strip())
    except ValueError:
        return default_index

# -----------------------------------
# 4. PÁGINAS DE STREAMLIT
# -----------------------------------

def render_employee_management_page():
    st.title("👥 Gestión de Empleados")
    st.markdown("Administración de perfiles y estados de los colaboradores de la empresa.")

    if "user_role" not in st.session_state or st.session_state.get("user_role") not in ["admin", "supervisor"]:
        st.error("🚫 Acceso Denegado. Solo administradores y supervisores pueden gestionar empleados.")
        return

    if "show_add_form" not in st.session_state: st.session_state["show_add_form"] = False
    if "employee_to_edit" not in st.session_state: st.session_state["employee_to_edit"] = None

    col_add, col_refresh = st.columns([1, 1])
    with col_add:
        if st.button("➕ Añadir Nuevo"):
            st.session_state["show_add_form"] = True
            st.session_state["employee_to_edit"] = None
            st.rerun()
    with col_refresh:
        if st.button("🔄 Recargar Datos"):
            clear_cache_and_rerun()

    # =================================================================
    # FORMULARIO DE ADICIÓN DE EMPLEADO (TEXTOS EN ESPAÑOL)
    # =================================================================
    if st.session_state["show_add_form"]:
        st.header("Formulario de Nuevo Empleado")
        next_id = get_next_employee_number()
        
        with st.form("add_employee_form", clear_on_submit=True):
            st.subheader("1. Datos Clave")
            col1, col2, col3 = st.columns(3)
            with col1:
                new_employee_number = st.number_input("Número de Empleado (ID)", min_value=1, step=1, value=next_id, disabled=True, key="add_id")
                new_gender = st.selectbox("Género", ["Male", "Female"], key="add_gender", format_func=lambda x: "Masculino" if x=="Male" else "Femenino")
                new_joblevel = st.number_input("Nivel Laboral (1-5)", min_value=1, max_value=5, key="add_joblevel", value=1)
            with col2:
                new_age = st.number_input("Edad", min_value=18, max_value=100, key="add_age", value=30)
                new_maritalstatus = st.selectbox("Estado Civil", ["Single", "Married", "Divorced"], key="add_marital", format_func=lambda x: {"Single":"Soltero/a", "Married":"Casado/a", "Divorced":"Divorciado/a"}[x])
                new_monthlyincome = st.number_input("Ingreso Mensual", min_value=0, key="add_income", value=4000)
            with col3:
                new_fechaingreso = st.date_input("Fecha de Ingreso", value=date.today(), key="add_f_ingreso")
                new_tipocontrato = st.selectbox("Tipo de Contrato", ["Fijo", "Temporal", "Servicios"], key="add_contrato")
                new_overtime = st.radio("Horas Extra", ("Yes", "No"), key="add_overtime", index=1, format_func=lambda x: "Sí" if x=="Yes" else "No")
            
            st.subheader("2. Experiencia y Puesto")
            col4, col5, col6 = st.columns(3)
            with col4:
                new_department = st.selectbox("Departamento", ["HR", "Tech", "Finance", "Marketing", "Research & Development"], key="add_dept")
                new_jobrole = st.selectbox("Puesto", ["Manager", "Developer", "Analyst", "Support", "Sales Executive", "Research Scientist", "Laboratory Technician", "Manufacturing Director", "Healthcare Representative"], key="add_job")
                new_businesstravel = st.selectbox("Viajes de Negocios", ["Non-Travel", "Travel_Rarely", "Travel_Frequently"], key="add_travel")
            with col5:
                new_education = st.number_input("Educación (1-5)", min_value=1, max_value=5, key="add_education", value=3)
                new_educationfield = st.selectbox("Campo de Educación", ["Life Sciences", "Medical", "Marketing", "Technical Degree", "Human Resources", "Other"], key="add_ed_field")
                new_totalworkingyears = st.number_input("Años Totales de Experiencia", min_value=0, key="add_total_years", value=5)
            with col6:
                new_numcompaniesworked = st.number_input("Empresas donde trabajó", min_value=0, key="add_num_comp", value=1)
                new_distancefromhome = st.number_input("Distancia al Hogar (km)", min_value=1, key="add_distance", value=10)
                new_trainingtimeslastyear = st.number_input("Capacitaciones el año pasado", min_value=0, max_value=6, key="add_training", value=3)

            st.subheader("3. Trayectoria Interna y Métricas")
            col7, col8 = st.columns(2)
            with col7:
                new_yearsatcompany = st.number_input("Años en la Compañía", min_value=0, key="add_years_comp", value=5)
                new_yearsincurrentrole = st.number_input("Años en el Puesto Actual", min_value=0, key="add_years_role", value=3)
                new_yearswithcurrmanager = st.number_input("Años con el Jefe Actual", min_value=0, key="add_years_manager", value=2)
            with col8:
                new_performancerating = st.number_input("Calificación de Desempeño (1-4)", min_value=1, max_value=4, key="add_perf_rating", value=3)
                new_yearssincelastpromotion = st.number_input("Años desde el último ascenso", min_value=0, key="add_last_promo", value=1)
                new_numerotardanzas = st.number_input("Número de Tardanzas", min_value=0, key="add_tardanzas", value=0)
                new_numerofaltas = st.number_input("Número de Faltas", min_value=0, key="add_faltas", value=0)

            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.form_submit_button("💾 Guardar Nuevo Empleado"):
                    if new_employee_number and new_monthlyincome:
                        employee_data = {
                            "employeenumber": int(new_employee_number), "age": int(new_age), "gender": new_gender,
                            "department": new_department, "jobrole": new_jobrole, "joblevel": int(new_joblevel),
                            "monthlyincome": int(new_monthlyincome), "maritalstatus": new_maritalstatus, "overtime": new_overtime,
                            "businesstravel": new_businesstravel, "distancefromhome": int(new_distancefromhome), "education": int(new_education),
                            "educationfield": new_educationfield, "numcompaniesworked": int(new_numcompaniesworked), "performancerating": int(new_performancerating),
                            "totalworkingyears": int(new_totalworkingyears), "trainingtimeslastyear": int(new_trainingtimeslastyear),
                            "yearsatcompany": int(new_yearsatcompany), "yearsincurrentrole": int(new_yearsincurrentrole),
                            "yearssincelastpromotion": int(new_yearssincelastpromotion), "yearswithcurrmanager": int(new_yearswithcurrmanager),
                            "tipocontrato": new_tipocontrato, "numerotardanzas": int(new_numerotardanzas), "numerofaltas": int(new_numerofaltas),
                            "fechaingreso": new_fechaingreso.isoformat() if new_fechaingreso else None
                        }
                        add_employee(employee_data)
                        st.session_state["show_add_form"] = False
                        clear_cache_and_rerun()
            with col_cancel:
                if st.form_submit_button("❌ Cancelar"):
                    st.session_state["show_add_form"] = False
                    st.rerun()

    df = get_employees_data() 
    if not df.empty:
        st.header("Lista de Empleados")
        st.dataframe(df, use_container_width=True, hide_index=True)
        employee_ids_list = df['ID'].tolist()
        
        if not st.session_state.get("employee_to_edit"):
            selected_id = st.selectbox("Selecciona un Empleado para editar o eliminar:", options=[""] + employee_ids_list, key="select_employee")
            if selected_id:
                col_edit, col_delete = st.columns([1, 1])
                with col_edit:
                    if st.button("✏️ Editar Registro"):
                        st.session_state["employee_to_edit"] = selected_id
                        st.session_state["show_add_form"] = False
                        st.rerun()
                with col_delete:
                    if st.button("❌ Eliminar Registro"):
                        delete_employee_record(selected_id)
                        clear_cache_and_rerun()
    else:
        st.warning("No hay empleados registrados.")

    if st.session_state.get("employee_to_edit"):
        render_edit_employee_form(st.session_state["employee_to_edit"], df)


def render_edit_employee_form(emp_id: int, df_all_employees: pd.DataFrame):
    employee_data = fetch_employee_by_id(emp_id) 
    
    if employee_data:
        st.header(f"Editar Empleado ID: {emp_id}")
        dept_options = get_unique_options(df_all_employees, "department", ["HR", "Tech", "Finance", "Marketing"])
        jobrole_options = get_unique_options(df_all_employees, "jobrole", ["Manager", "Developer", "Analyst", "Support"])
        tipocontrato_options = get_unique_options(df_all_employees, "tipocontrato", ["Fijo", "Temporal", "Servicios"])
        travel_options = ["Non-Travel", "Travel_Rarely", "Travel_Frequently"]

        with st.form("edit_employee_form", clear_on_submit=False):
            def get_val(key, default_val):
                val = employee_data.get(key)
                if val is None: return default_val
                if isinstance(default_val, int): return int(val) if val else default_val
                if isinstance(default_val, float): return float(val) if val else default_val
                if isinstance(default_val, date) or ('fecha' in key.lower() and val):
                    try: return date.fromisoformat(str(val)[:10])
                    except: return default_val
                return str(val).strip() if isinstance(default_val, str) else val

            st.subheader("1. Datos de Empleo y Salario")
            col1, col2 = st.columns(2)
            with col1:
                new_department = st.selectbox("Departamento", dept_options, index=get_safe_index(dept_options, get_val("department", "HR")))
                new_jobrole = st.selectbox("Puesto", jobrole_options, index=get_safe_index(jobrole_options, get_val("jobrole", "Manager")))
                new_monthlyincome = st.number_input("Ingreso Mensual", min_value=0, value=get_val("monthlyincome", 0))
                new_joblevel = st.number_input("Nivel Laboral", min_value=1, max_value=5, value=get_val("joblevel", 1))
            with col2:
                new_tipocontrato = st.selectbox("Tipo de Contrato", tipocontrato_options, index=get_safe_index(tipocontrato_options, get_val("tipocontrato", "Fijo")))
                new_businesstravel = st.selectbox("Viajes de Negocios", travel_options, index=get_safe_index(travel_options, get_val("businesstravel", "Non-Travel")))
                new_overtime = st.radio("Horas Extra", ("Yes", "No"), index=["Yes", "No"].index(get_val("overtime", "No")), format_func=lambda x: "Sí" if x=="Yes" else "No")
                new_performancerating = st.number_input("Calificación de Desempeño (1-4)", min_value=1, max_value=4, value=get_val("performancerating", 3))

            st.subheader("2. Historial Interno y Ausencias")
            col3, col4 = st.columns(2)
            with col3:
                new_yearsatcompany = st.number_input("Años en la Compañía", min_value=0, value=get_val("yearsatcompany", 0))
                new_yearsincurrentrole = st.number_input("Años en el Puesto Actual", min_value=0, value=get_val("yearsincurrentrole", 0))
                new_yearswithcurrmanager = st.number_input("Años con el Jefe Actual", min_value=0, value=get_val("yearswithcurrmanager", 0))
                new_yearssincelastpromotion = st.number_input("Años desde el último ascenso", min_value=0, value=get_val("yearssincelastpromotion", 0))
                new_trainingtimeslastyear = st.number_input("Capacitaciones el año pasado", min_value=0, max_value=6, value=get_val("trainingtimeslastyear", 0))
            with col4:
                new_numerotardanzas = st.number_input("Número de Tardanzas", min_value=0, value=get_val("numerotardanzas", 0))
                new_numerofaltas = st.number_input("Número de Faltas", min_value=0, value=get_val("numerofaltas", 0))
                st.info(f"Fecha de Ingreso original: {get_val('fechaingreso', 'No registrada')}")
                new_fechasalida = st.date_input("Fecha de Salida (Opcional)", value=get_val("fechasalida", None))

            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.form_submit_button("💾 Guardar Cambios"):
                    update_data = {
                        "businesstravel": new_businesstravel, "department": new_department, "joblevel": int(new_joblevel),
                        "jobrole": new_jobrole, "monthlyincome": int(new_monthlyincome), "overtime": new_overtime,
                        "performancerating": int(new_performancerating), "trainingtimeslastyear": int(new_trainingtimeslastyear),
                        "yearsatcompany": int(new_yearsatcompany), "yearsincurrentrole": int(new_yearsincurrentrole),
                        "yearssincelastpromotion": int(new_yearssincelastpromotion), "yearswithcurrmanager": int(new_yearswithcurrmanager),
                        "tipocontrato": new_tipocontrato, "numerotardanzas": int(new_numerotardanzas), "numerofaltas": int(new_numerofaltas),
                        "fechasalida": new_fechasalida.isoformat() if new_fechasalida else None 
                    }
                    update_employee_record(emp_id, update_data)
                    st.session_state["employee_to_edit"] = None
                    clear_cache_and_rerun()
            with col_cancel:
                if st.form_submit_button("❌ Cancelar Edición"):
                    st.session_state["employee_to_edit"] = None
                    st.rerun()














