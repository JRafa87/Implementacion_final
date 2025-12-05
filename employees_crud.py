import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date, datetime

# ===========================================
# Función para inicializar y cachear el cliente de Supabase
# ===========================================
# Importante: Las credenciales deben estar en un archivo .streamlit/secrets.toml
# Ejemplo:
# SUPABASE_URL="tu_url"
# SUPABASE_KEY="tu_key"

@st.cache_resource
def get_supabase() -> Client:
    """Inicializa y cachea el cliente de Supabase."""
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("ERROR: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml. La autenticación fallará.")
        # Usar un valor de ejemplo o levantar excepción si es vital.
        # Por ahora, simplemente paramos el script.
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
    # Usamos st.cache_data para evitar llamadas repetidas a la DB al interactuar con la UI
    @st.cache_data(ttl=60) # Cacha los datos por 60 segundos
    def load_data():
        try:
            # Filtrar empleados activos (sin fecha de salida)
            # Nota: 'is_("FechaSalida", None)' es la forma correcta en Supabase-py
            response = supabase.table("empleados").select("*").is_("FechaSalida", None).order("EmployeeNumber").execute()
            # Convertir claves de PostgreSQL (ej: EmployeeNumber) a minúsculas de Python (ej: employeenumber)
            data = [{k.lower(): v for k, v in record.items()} for record in response.data]
            return data
        except Exception as e:
            st.error(f"Error al cargar empleados: {e}")
            return []
    
    return load_data()


def add_employee(employee_data: dict):
    """Agrega un nuevo empleado a la tabla 'empleados'."""
    pg_data = {}
    for py_key, pg_key in COLUMN_MAPPING.items():
        if py_key in employee_data:
            # Conversión de tipos si es necesaria, aunque Supabase suele manejarlo
            pg_data[pg_key] = employee_data[py_key]
    
    try:
        supabase.table("empleados").insert(pg_data).execute()
        st.success(f"Empleado con ID {employee_data['employeenumber']} añadido con éxito.")
        st.cache_data.clear() # Limpia la caché después de una operación de escritura
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
        st.cache_data.clear() # Limpia la caché después de una operación de escritura
    except Exception as e:
        st.error(f"Error al actualizar empleado: {e}")

def delete_employee_record(employee_number: int):
    """Elimina (borrado suave o 'soft delete') un empleado, estableciendo la fecha de salida."""
    try:
        # **RECOMENDADO:** Borrado suave (soft delete) en lugar de eliminación física
        soft_delete_data = {
            "FechaSalida": date.today().isoformat() # Usar la fecha actual
        }
        supabase.table("empleados").update(soft_delete_data).eq("EmployeeNumber", employee_number).execute()
        st.success(f"Empleado {employee_number} dado de baja con éxito.")
        st.cache_data.clear() # Limpia la caché después de una operación de escritura
    except Exception as e:
        st.error(f"Error al dar de baja empleado: {e}")

# ============================
# Función para preparar datos de empleados
# ============================

def get_employees_data():
    """Carga los datos de empleados y los prepara para el display."""
    data = fetch_employees()
    if data:
        df = pd.DataFrame(data)
        # Renombrar columnas para display en Streamlit
        df.rename(columns={
            'employeenumber': 'ID',
            'jobrole': 'Puesto',
            'department': 'Depto',
            'monthlyincome': 'Salario Mensual',
            'fechaingreso': 'F. Ingreso',
            'tipocontrato': 'T. Contrato'
        }, inplace=True)
        
        # Conversión de tipos y manejo de NaN para display
        for col in ['numerotardanzas', 'numerofaltas', 'age', 'totalworkingyears', 'yearsatcompany']:
            df[col] = df.get(col, 0).fillna(0).astype(int)
            
        # Relleno de valores por defecto si son nulos (útil para el formulario de edición)
        df['overtime'] = df['overtime'].fillna('No')
        df['maritalstatus'] = df['maritalstatus'].fillna('Single')
        df['gender'] = df['gender'].fillna('Male')
        
        # Formato de Salario para mejor visualización
        df['Salario Mensual'] = df['Salario Mensual'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
        
        return df
    return pd.DataFrame()


# ============================
# Funciones de Formulario de CRUD (Separadas para Control de Flujo)
# ============================

# Opciones predefinidas para los selectbox
DEPARTMENTS = ["Research & Development", "Sales", "Human Resources"]
JOB_ROLES = ["Sales Executive", "Research Scientist", "Laboratory Technician", "Manufacturing Director", 
             "Healthcare Representative", "Manager", "Sales Representative", "Research Manager", "Human Resources"]

def render_edit_form(emp_id: int, df: pd.DataFrame):
    """Renderiza el formulario de edición para un empleado específico."""
    # Obtener los datos actuales del empleado
    selected_row = df[df['ID'] == emp_id].iloc[0].to_dict()
    
    st.header(f"✏️ Editar Empleado ID: {emp_id}")
    st.markdown("---")
    
    with st.form("edit_employee_data_form"):
        # Campo no editable: ID
        st.text_input("EmployeeNumber (ID)", value=emp_id, disabled=True)
        
        # Campos editables
        # Aseguramos que el índice sea el correcto para el valor actual
        default_dept = selected_row.get('Depto', DEPARTMENTS[0])
        default_role = selected_row.get('Puesto', JOB_ROLES[0])
        
        edit_department = st.selectbox("Department", DEPARTMENTS, 
                                        index=DEPARTMENTS.index(default_dept) if default_dept in DEPARTMENTS else 0)
        edit_jobrole = st.selectbox("JobRole", JOB_ROLES, 
                                     index=JOB_ROLES.index(default_role) if default_role in JOB_ROLES else 0)
        
        # Limpiamos el formato del salario para el input numérico
        current_salary = float(selected_row.get('Salario Mensual', '$0.00').replace('$', '').replace(',', ''))
        edit_monthlyincome = st.number_input("MonthlyIncome", value=current_salary, min_value=0.0, step=100.0)
        
        # Botones de Acción
        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.form_submit_button("✅ Guardar Cambios"):
                update_data = {
                    "department": edit_department,
                    "jobrole": edit_jobrole,
                    "monthlyincome": edit_monthlyincome,
                }
                update_employee_record(emp_id, update_data)
                
                # Al guardar, limpiamos el estado para volver a la tabla
                st.session_state["employee_to_edit"] = None
                st.experimental_rerun()
                
        with col_cancel:
            if st.form_submit_button("↩️ Cancelar Edición"):
                # Limpiamos el estado para volver a la tabla
                st.session_state["employee_to_edit"] = None
                st.experimental_rerun()


def render_add_form():
    """Renderiza el formulario para añadir un nuevo empleado."""
    st.header("➕ Añadir Nuevo Empleado")
    st.markdown("---")
    
    with st.form("add_employee_data_form"):
        # Campos obligatorios/iniciales
        new_id = st.number_input("EmployeeNumber (ID) Único", min_value=1, step=1)
        new_department = st.selectbox("Department", DEPARTMENTS)
        new_jobrole = st.selectbox("JobRole", JOB_ROLES)
        new_monthlyincome = st.number_input("MonthlyIncome", min_value=0.0, step=100.0)
        new_fecha_ingreso = st.date_input("Fecha de Ingreso", value=date.today())
        
        # Un campo simple para demostrar la adición
        new_gender = st.selectbox("Gender", ["Male", "Female"])
        
        # Botones de Acción
        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.form_submit_button("➕ Añadir Empleado"):
                if new_id > 0:
                    add_data = {
                        "employeenumber": int(new_id),
                        "department": new_department,
                        "jobrole": new_jobrole,
                        "monthlyincome": new_monthlyincome,
                        "fechaingreso": new_fecha_ingreso.isoformat(),
                        "gender": new_gender,
                        # Puedes añadir valores por defecto para los demás campos si son obligatorios en DB
                    }
                    add_employee(add_data)
                    
                    # Al añadir, limpiamos el estado para volver a la tabla
                    st.session_state["show_add_form"] = False
                    st.experimental_rerun()
                else:
                    st.error("El EmployeeNumber debe ser un ID único y mayor a 0.")
        with col_cancel:
            if st.form_submit_button("↩️ Cancelar"):
                st.session_state["show_add_form"] = False
                st.experimental_rerun()


# ================================
# Página de Gestión de Empleados (Controlador Principal)
# ================================

def render_employee_management_page():
    """Página de Gestión de Empleados. Controla el flujo de la tabla, adición y edición."""
    st.title("👥 Gestión de Empleados")
    
    # 1. Control de Acceso (Asegurar que el rol se establezca en el login de la app principal)
    # st.session_state.get("user_role") debe ser 'admin' o 'supervisor'
    #if st.session_state.get("user_role") not in ["admin", "supervisor"]:
        #st.error("🚫 Acceso Denegado. Solo administradores y supervisores pueden gestionar empleados.")
        #return

    # Cargamos los datos para usarlos en todos los modos
    #df = get_employees_data()

    # 2. Flujo de Formulario (Retorno Temprano - Solo mostramos UN formulario a la vez)
    
    # Priorizar la Edición
    if "employee_to_edit" in st.session_state and st.session_state["employee_to_edit"] is not None:
        emp_id = st.session_state["employee_to_edit"]
        if not df.empty and emp_id in df['ID'].tolist():
             render_edit_form(emp_id, df)
             return # Sale aquí para que solo se muestre el formulario de edición

    # Priorizar la Adición
    if st.session_state.get("show_add_form", False):
        render_add_form()
        return # Sale aquí para que solo se muestre el formulario de adición


    # 3. Flujo de Vista Principal (Solo se ejecuta si no estamos editando o añadiendo)
    st.markdown("Administración de perfiles y estados de los colaboradores de la empresa.")
    
    # Botones de Acción
    col_add, col_refresh, col_spacer = st.columns([1, 1, 5])
    with col_add:
        # Iniciamos el modo de adición
        if st.button("➕ Añadir Nuevo"):
            st.session_state["show_add_form"] = True
            st.session_state["employee_to_edit"] = None
            st.experimental_rerun()
            
    with col_refresh:
        # Forzamos la recarga desde la base de datos
        if st.button("🔄 Recargar Datos"):
            st.cache_data.clear() # Limpia la caché para obtener los datos más recientes
            st.experimental_rerun()
    
    # Mostrar tabla
    if df.empty:
        st.warning("No hay empleados activos registrados en la base de datos.")
        return
    
    employee_ids_list = df['ID'].tolist()
    selected_id = st.selectbox("Selecciona un Empleado para editar o dar de baja:", options=[""] + employee_ids_list, index=0)

    # Columnas a mostrar en la tabla de resumen
    display_df = df[['ID', 'Puesto', 'Depto', 'Salario Mensual', 'F. Ingreso', 'T. Contrato', 'age', 'maritalstatus', 'gender', 'overtime']]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    
    # Lógica de Edición y Eliminación
    if selected_id:
        emp_id = selected_id
        col_edit, col_delete, col_spacer = st.columns([1, 1, 4])
        
        with col_edit:
            if st.button("✏️ Editar Registro"):
                st.session_state["employee_to_edit"] = emp_id
                st.session_state["employee_to_delete"] = None
                st.session_state["show_add_form"] = False
                st.experimental_rerun()
        
        with col_delete:
            # Activamos el estado de confirmación de eliminación (Soft Delete)
            if st.button("🚪 Dar de Baja"):
                st.session_state["employee_to_delete"] = emp_id
                st.session_state["employee_to_edit"] = None
                st.experimental_rerun()
        
        st.info(f"Seleccionado Empleado ID: **{emp_id}**.")
        
        # 4. Lógica de Confirmación de Eliminación (Soft Delete)
        if "employee_to_delete" in st.session_state and st.session_state["employee_to_delete"] == emp_id:
             st.warning(f"⚠️ ¿Estás seguro de que quieres dar de baja (Soft Delete) al empleado ID {emp_id}?")
             col_confirm, col_cancel_del = st.columns(2)
             with col_confirm:
                 if st.button("✅ Confirmar Baja"):
                     delete_employee_record(emp_id) # Usa la función de soft delete
                     st.session_state["employee_to_delete"] = None
                     st.experimental_rerun()
             with col_cancel_del:
                 if st.button("🚫 Cancelar Baja"):
                     st.session_state["employee_to_delete"] = None
                     st.experimental_rerun()
