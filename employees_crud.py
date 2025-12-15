import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
from datetime import date
import time # Añadido para simular páginas de perfil/dashboard si es necesario

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

# -----------------------------------
# 2. FUNCIONES CRUD (Se mantienen)
# -----------------------------------

def fetch_employees():
    """Obtiene todos los empleados de la tabla 'empleados' que no tienen fecha de salida."""
    try:
        # Aquí es donde se JALA toda la información de la tabla 'empleados'
        response = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
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

# -----------------------------------
# 3. FUNCIONES DE UI Y CACHÉ
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
            'employeenumber': 'ID',
            'jobrole': 'Puesto',
            'department': 'Depto',
            'monthlyincome': 'Salario Mensual',
            'fechaingreso': 'F. Ingreso',
            'tipocontrato': 'T. Contrato'
        }, inplace=True)
        
        # Asegurar tipos y manejar NaNs
        for col in ['numerotardanzas', 'numerofaltas', 'age', 'totalworkingyears', 'yearsatcompany']:
             df[col] = df.get(col, pd.Series([0] * len(df))).fillna(0).astype(int)
        
        # Llenar valores faltantes comunes
        df['overtime'] = df['overtime'].fillna('No')
        df['maritalstatus'] = df['maritalstatus'].fillna('Single')
        df['gender'] = df['gender'].fillna('Male')
        return df
    return pd.DataFrame()


def get_unique_options(df: pd.DataFrame, column_name: str, default_options: list) -> list:
    """Obtiene valores únicos de una columna del DF, limpiando NaNs y ordenando."""
    # El DF aquí usa las claves en MINÚSCULA
    if df.empty or column_name not in df.columns:
        return default_options
        
    unique_vals = df[column_name].dropna().unique().tolist()
    
    # Aseguramos que todas las opciones sean strings limpias
    unique_vals = [str(v).strip() for v in unique_vals if v is not None]
    
    # Añadimos las opciones por defecto si faltan y ordenamos
    for opt in default_options:
        if str(opt).strip() not in unique_vals:
            unique_vals.append(str(opt).strip())
    
    unique_vals.sort()
    return unique_vals

def get_safe_index(options_list: list, current_value: str, default_index=0):
    """Busca el índice de un valor en una lista de opciones. Devuelve 0 si no se encuentra."""
    try:
        # Strip() asegura que no haya espacios en los datos de la base de datos
        return options_list.index(current_value.strip())
    except ValueError:
        return default_index

# -----------------------------------
# 4. PÁGINAS DE STREAMLIT
# -----------------------------------

def render_edit_employee_form(emp_id: int, df_all_employees: pd.DataFrame):
    """Formulario de edición de empleado."""
    employee_data = fetch_employee_by_id(emp_id) # Carga los datos del empleado específico
    
    if employee_data:
        st.header(f"Editar Empleado ID: {emp_id}")
        
        # 1. Definición de Opciones Dinámicas jaladas de Supabase/DataFrame
        dept_options = get_unique_options(df_all_employees, "department", ["HR", "Tech", "Finance", "Marketing"])
        jobrole_options = get_unique_options(df_all_employees, "jobrole", ["Manager", "Developer", "Analyst", "Support"])
        tipocontrato_options = get_unique_options(df_all_employees, "tipocontrato", ["Fijo", "Temporal", "Servicios"])
        
        # Opciones Estáticas (para campos con valores predefinidos)
        travel_options = ["Non-Travel", "Travel_Rarely", "Travel_Frequently"]

        with st.form("edit_employee_form", clear_on_submit=False):
            
            # --- Conversiones iniciales de valores ---
            def get_val(key, default_val):
                """Obtiene el valor del diccionario o el valor por defecto."""
                val = employee_data.get(key)
                if val is None:
                    return default_val
                
                if isinstance(default_val, int):
                    return int(val) if val else default_val
                if isinstance(default_val, float):
                    return float(val) if val else default_val
                if isinstance(default_val, date) or isinstance(default_val, str) and 'date' in key.lower():
                    # Intenta convertir a date.date si es posible
                    try:
                        return date.fromisoformat(str(val)[:10])
                    except (TypeError, ValueError):
                        return default_val
                
                if isinstance(default_val, str):
                    return str(val).strip()
                
                return val
            
            # -----------------------------------------------
            
            st.subheader("Datos de Empleo y Salario")
            col1, col2 = st.columns(2)

            with col1:
                # SELECTBOX DINÁMICO: Department
                current_dept = get_val("department", "HR")
                new_department = st.selectbox(
                    "Department", 
                    dept_options, 
                    index=get_safe_index(dept_options, current_dept)
                )
                
                # SELECTBOX DINÁMICO: JobRole
                current_jobrole = get_val("jobrole", "Manager")
                new_jobrole = st.selectbox(
                    "JobRole", 
                    jobrole_options, 
                    index=get_safe_index(jobrole_options, current_jobrole)
                )
                new_monthlyincome = st.number_input("MonthlyIncome", min_value=0, value=get_val("monthlyincome", 0))
                new_joblevel = st.number_input("JobLevel", min_value=1, max_value=5, value=get_val("joblevel", 1))
            
            with col2:
                # SELECTBOX DINÁMICO: Tipocontrato
                current_contrato = get_val("tipocontrato", "Fijo")
                new_tipocontrato = st.selectbox(
                    "Tipocontrato", 
                    tipocontrato_options, 
                    index=get_safe_index(tipocontrato_options, current_contrato)
                )
                
                # SELECTBOX ESTÁTICO: BusinessTravel
                current_travel = get_val("businesstravel", "Non-Travel")
                new_businesstravel = st.selectbox(
                    "BusinessTravel", 
                    travel_options, 
                    index=get_safe_index(travel_options, current_travel)
                )
                new_overtime = st.radio("OverTime", ("Yes", "No"), index=["Yes", "No"].index(get_val("overtime", "No")))
                new_performancerating = st.number_input("PerformanceRating (1-4)", min_value=1, max_value=4, value=get_val("performancerating", 3))

            st.subheader("Historial Interno y Ausencias")
            col3, col4 = st.columns(2)
            with col3:
                new_yearsatcompany = st.number_input("YearsAtCompany", min_value=0, value=get_val("yearsatcompany", 0))
                new_yearsincurrentrole = st.number_input("YearsInCurrentRole", min_value=0, value=get_val("yearsincurrentrole", 0))
                new_yearswithcurrmanager = st.number_input("YearsWithCurrManager", min_value=0, value=get_val("yearswithcurrmanager", 0))
                new_yearssincelastpromotion = st.number_input("YearsSinceLastPromotion", min_value=0, value=get_val("yearssincelastpromotion", 0))
                new_trainingtimeslastyear = st.number_input("TrainingTimesLastYear", min_value=0, max_value=6, value=get_val("trainingtimeslastyear", 0))
            with col4:
                new_numerotardanzas = st.number_input("NumeroTardanzas", min_value=0, value=get_val("numerotardanzas", 0))
                new_numerofaltas = st.number_input("NumeroFaltas", min_value=0, value=get_val("numerofaltas", 0))
                
                st.info(f"Fecha de Ingreso: {get_val('fechaingreso', 'N/A')}")
                current_fecha_salida = get_val("fechasalida", None) 
                
                fecha_salida_value = current_fecha_salida if current_fecha_salida else None
                
                new_fechasalida = st.date_input(
                    "FechaSalida (Opcional)", 
                    value=fecha_salida_value, 
                    min_value=get_val("fechaingreso", date(1900, 1, 1))
                )

            
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.form_submit_button("💾 Guardar Cambios"):
                    # Lógica para GUARDAR
                    update_data = {
                        "businesstravel": new_businesstravel,
                        "department": new_department,
                        "joblevel": int(new_joblevel),
                        "jobrole": new_jobrole,
                        "monthlyincome": int(new_monthlyincome),
                        "overtime": new_overtime,
                        "performancerating": int(new_performancerating),
                        "totalworkingyears": get_val("totalworkingyears", 0),
                        "trainingtimeslastyear": int(new_trainingtimeslastyear),
                        "yearsatcompany": int(new_yearsatcompany),
                        "yearsincurrentrole": int(new_yearsincurrentrole),
                        "yearssincelastpromotion": int(new_yearssincelastpromotion),
                        "yearswithcurrmanager": int(new_yearswithcurrmanager),
                        "tipocontrato": new_tipocontrato,
                        "numerotardanzas": int(new_numerotardanzas),
                        "numerofaltas": int(new_numerofaltas),
                        "fechasalida": new_fechasalida.isoformat() if new_fechasalida else None 
                    }
                    
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

def render_employee_management_page():
    """Página de Gestión de Empleados (CRUD con Streamlit)."""
    st.title("👥 Gestión de Empleados")
    
    # ... (Lógica de verificación de rol y botones de Añadir/Recargar) ...

    # Inicialización de estados (asumimos que ya existen)
    if "user_role" not in st.session_state or st.session_state.get("user_role") not in ["admin", "supervisor"]:
        st.error("🚫 Acceso Denegado. Solo administradores y supervisores pueden gestionar empleados.")
        return

    if "show_add_form" not in st.session_state:
        st.session_state["show_add_form"] = False
    if "employee_to_edit" not in st.session_state:
        st.session_state["employee_to_edit"] = None

    col_add, col_refresh = st.columns([1, 1])
    
    with col_add:
        if st.button("➕ Añadir Nuevo"):
            st.session_state["show_add_form"] = True
            st.session_state["employee_to_edit"] = None
            st.rerun()
    
    with col_refresh:
        if st.button("🔄 Recargar Datos"):
            clear_cache_and_rerun()

    # Formulario de adición de empleado (Se mantiene el formato completo de todos los campos)
    # ... (código del formulario de adición, omitido aquí por espacio, asumiendo que ya tiene todos los campos) ...
    if st.session_state["show_add_form"]:
        # ... (código del formulario 'add_employee_form' con todos los campos) ...
        st.header("Formulario de Nuevo Empleado (Completo)")
        # ... (código del formulario 'add_employee_form' con todos los campos) ...
        # NOTE: Asegúrate de que este formulario tiene todos los campos de la tabla `empleados` mapeados.
        pass # Placeholder para el formulario de adición

    # 1. Cargar datos (DataFrame maestro)
    df = get_employees_data() 

    # 2. Mostrar empleados existentes
    if not df.empty:
        st.header("Lista de Empleados")
        st.dataframe(df, use_container_width=True, hide_index=True)

        employee_ids_list = df['ID'].tolist()
        
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

    # 3. Mostrar formulario de edición (AQUÍ se pasa el DF)
    if st.session_state.get("employee_to_edit"):
        render_edit_employee_form(st.session_state["employee_to_edit"], df) # **CORRECCIÓN CLAVE**


# Si este fuera el archivo principal, se llamaría así:
# if __name__ == '__main__':
#     st.set_page_config(layout="wide", page_title="Gestión de Empleados")
#     # Nota: Aquí deberías inicializar el st.session_state["user_role"]
#     if "user_role" not in st.session_state:
#         st.session_state["user_role"] = "admin" # Valor de prueba
#     render_employee_management_page()












