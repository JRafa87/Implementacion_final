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

# Mapeo para persistencia en DB (No cambiar estos nombres)
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

# =================================================================
# 2. FUNCIONES CRUD (Mantienen variables originales)
# =================================================================

def fetch_employees():
    try:
        response = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
        # Normalizamos a minúsculas para manejo interno
        data = [{k.lower(): v for k, v in record.items()} for record in response.data]
        return data
    except Exception as e:
        st.error(f"Error al cargar: {e}")
        return []

def fetch_employee_by_id(employee_number: int) -> Optional[dict]:
    try:
        response = supabase.table("empleados").select("*").eq("EmployeeNumber", employee_number).single().execute()
        if response.data:
            return {k.lower(): v for k, v in response.data.items()}
        return None
    except Exception:
        return None

def add_employee(employee_data: dict):
    pg_data = {COLUMN_MAPPING[k]: v for k, v in employee_data.items() if k in COLUMN_MAPPING}
    try:
        supabase.table("empleados").insert(pg_data).execute()
        st.success("Añadido con éxito.")
    except Exception as e:
        st.error(f"Error: {e}")

def update_employee_record(employee_number: int, update_data: dict):
    pg_update_data = {COLUMN_MAPPING[k]: v for k, v in update_data.items() if k in COLUMN_MAPPING}
    try:
        supabase.table("empleados").update(pg_update_data).eq("EmployeeNumber", employee_number).execute()
        st.success(f"ID {employee_number} actualizado.")
    except Exception as e:
        st.error(f"Error: {e}")

def delete_employee_record(employee_number: int):
    try:
        supabase.table("empleados").delete().eq("EmployeeNumber", employee_number).execute()
        st.success(f"ID {employee_number} eliminado.")
    except Exception as e:
        st.error(f"Error: {e}")

# =================================================================
# 3. FUNCIONES DE INTERFAZ (Traducción visual)
# =================================================================

@st.cache_data(ttl=600) 
def get_employees_data():
    """Prepara el DataFrame para que se vea ordenado en la interfaz."""
    data = fetch_employees() 
    if not data: return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Solo cambiamos las cabeceras para el display del usuario
    display_cols = {
        'employeenumber': 'ID',
        'age': 'Edad',
        'gender': 'Género',
        'jobrole': 'Puesto',
        'department': 'Departamento',
        'monthlyincome': 'Salario Mensual',
        'tipocontrato': 'Tipo de Contrato',
        'fechaingreso': 'F. Ingreso'
    }
    
    # Creamos una versión para mostrar
    df_show = df.rename(columns=display_cols)
    
    # Traducción de valores específicos para que se vea ordenado
    if 'Género' in df_show.columns:
        df_show['Género'] = df_show['Género'].map({'Male': 'Masculino', 'Female': 'Femenino'}).fillna(df_show['Género'])
    
    return df_show

def render_employee_management_page():
    st.title("👥 Gestión de Colaboradores")
    
    if "user_role" not in st.session_state or st.session_state.get("user_role") not in ["admin", "supervisor"]:
        st.error("🚫 Acceso restringido.")
        return

    # Botones de control
    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ Registrar Nuevo"):
            st.session_state["show_add_form"] = True
            st.session_state["edit_id"] = None
    with c2:
        if st.button("🔄 Refrescar Tabla"):
            st.cache_data.clear()
            st.rerun()

    # Formulario de Alta
    if st.session_state.get("show_add_form"):
        render_add_form()

    # Visualización de la Tabla Organizada
    df_view = get_employees_data()
    if not df_view.empty:
        st.subheader("Directorio de Personal")
        st.dataframe(df_view, use_container_width=True, hide_index=True)
        
        # Selección para Editar/Eliminar
        selected_id = st.selectbox("Seleccione ID para acciones:", [""] + df_view['ID'].tolist())
        if selected_id:
            col_e, col_d = st.columns(2)
            with col_e:
                if st.button("✏️ Editar"):
                    st.session_state["edit_id"] = selected_id
                    st.rerun()
            with col_d:
                if st.button("🗑️ Eliminar"):
                    delete_employee_record(selected_id)
                    st.cache_data.clear()
                    st.rerun()

    # Formulario de Edición
    if st.session_state.get("edit_id"):
        render_edit_form(st.session_state["edit_id"])

# =================================================================
# 4. FORMULARIOS (Labels en español, variables originales)
# =================================================================

def render_add_form():
    with st.expander("📝 Formulario de Registro", expanded=True):
        with st.form("new_emp"):
            col1, col2 = st.columns(2)
            with col1:
                # El valor se guarda en la clave original 'age'
                age = st.number_input("Edad", min_value=18, value=30)
                gender = st.selectbox("Género", ["Male", "Female"])
                department = st.selectbox("Departamento", ["Sales", "Tech", "HR", "Finance"])
            with col2:
                monthlyincome = st.number_input("Salario Mensual", min_value=0, value=3000)
                tipocontrato = st.selectbox("Tipo de Contrato", ["Indefinido", "Temporal", "Prácticas"])
                fechaingreso = st.date_input("Fecha de Ingreso", value=date.today())

            if st.form_submit_button("Guardar"):
                # Se mantiene el nombre de la variable original para la DB
                new_data = {
                    "employeenumber": supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute().data[0]['EmployeeNumber'] + 1,
                    "age": age,
                    "gender": gender,
                    "department": department,
                    "monthlyincome": monthlyincome,
                    "tipocontrato": tipocontrato,
                    "fechaingreso": fechaingreso.isoformat()
                }
                add_employee(new_data)
                st.session_state["show_add_form"] = False
                st.cache_data.clear()
                st.rerun()

def render_edit_form(emp_id):
    emp_data = fetch_employee_by_id(emp_id)
    if emp_data:
        st.markdown(f"### Editando ID: {emp_id}")
        with st.form("edit_emp"):
            # Usamos labels en español pero emp_data.get utiliza la variable original
            new_income = st.number_input("Salario Mensual", value=int(emp_data.get('monthlyincome', 0)))
            new_role = st.text_input("Puesto", value=emp_data.get('jobrole', ''))
            
            if st.form_submit_button("Actualizar"):
                update_employee_record(emp_id, {"monthlyincome": new_income, "jobrole": new_role})
                st.session_state["edit_id"] = None
                st.cache_data.clear()
                st.rerun()

if __name__ == "__main__":
    render_employee_management_page()















