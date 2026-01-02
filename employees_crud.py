import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS
# =================================================================

MAPEO_DEPTOS = {"Sales": "Ventas", "Research & Development": "I+D / Desarrollo", "Human Resources": "Recursos Humanos"}
MAPEO_EDUCACION = {"Life Sciences": "Ciencias de la Vida", "Other": "Otros", "Medical": "Médico", "Marketing": "Marketing", "Technical Degree": "Grado Técnico", "Human Resources": "Recursos Humanos"}
MAPEO_ROLES = {
    "Sales Executive": "Ejecutivo de Ventas", "Research Scientist": "Científico de Investigación",
    "Laboratory Technician": "Técnico de Laboratorio", "Manufacturing Director": "Director de Manufactura",
    "Healthcare Representative": "Representante de Salud", "Manager": "Gerente",
    "Sales Representative": "Representante de Ventas", "Research Director": "Director de Investigación",
    "Human Resources": "Recursos Humanos"
}
TRADUCCIONES_FIJAS = {
    "businesstravel": {"Non-Travel": "No viaja", "Travel_Rarely": "Viaja raramente", "Travel_Frequently": "Viaja frecuentemente"},
    "gender": {"Male": "Masculino", "Female": "Femenino"},
    "maritalstatus": {"Single": "Soltero/a", "Married": "Casado/a", "Divorced": "Divorciado/a"},
    "overtime": {"Yes": "Sí", "No": "No"}
}

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

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key)

supabase = get_supabase()

def fetch_employees():
    response = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
    return [{k.lower(): v for k, v in record.items()} for record in response.data]

# =================================================================
# 2. INTERFAZ PRINCIPAL
# =================================================================

def render_employee_management_page():
    st.title("👥 Gestión de Personal")

    # Inicializar estados si no existen
    if "edit_id" not in st.session_state: st.session_state.edit_id = None
    if "show_add" not in st.session_state: st.session_state.show_add = False

    # --- SECCIÓN TABLA ---
    raw_data = fetch_employees()
    if raw_data:
        df = pd.DataFrame(raw_data)
        # Traducir para la vista
        df['department_vista'] = df['department'].map(MAPEO_DEPTOS)
        df['jobrole_vista'] = df['jobrole'].map(MAPEO_ROLES)
        
        df_display = df[['employeenumber', 'age', 'department_vista', 'jobrole_vista', 'monthlyincome']].rename(columns={
            'employeenumber': 'ID', 'age': 'Edad', 'department_vista': 'Departamento', 
            'jobrole_vista': 'Puesto', 'monthlyincome': 'Sueldo'
        })
        
        st.subheader("Lista de Empleados")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # Acciones de fila
        sel_id = st.selectbox("Seleccione ID para Editar o Eliminar", [None] + [e['employeenumber'] for e in raw_data])
        c_ed, c_del, c_new = st.columns([1, 1, 2])
        with c_ed:
            if st.button("✏️ Editar Seleccionado") and sel_id:
                st.session_state.edit_id = sel_id
                st.session_state.show_add = False
                st.rerun()
        with c_del:
            if st.button("🗑️ Eliminar Seleccionado") and sel_id:
                supabase.table("empleados").delete().eq("EmployeeNumber", sel_id).execute()
                st.rerun()
        with c_new:
            if st.button("➕ Crear Nuevo Registro"):
                st.session_state.show_add = True
                st.session_state.edit_id = None
                st.rerun()
    
    st.divider()

    # --- SECCIÓN FORMULARIO (DEBAJO) ---
    if st.session_state.show_add or st.session_state.edit_id:
        es_edit = st.session_state.edit_id is not None
        prev = {}
        if es_edit:
            res = supabase.table("empleados").select("*").eq("EmployeeNumber", st.session_state.edit_id).single().execute()
            prev = {k.lower(): v for k, v in res.data.items()}

        st.subheader("📝 Formulario de Detalle" if not es_edit else f"📝 Editando ID: {st.session_state.edit_id}")
        
        with st.form("form_gestion"):
            # CAMPOS PERSONALES
            col1, col2, col3 = st.columns(3)
            with col1:
                # RESTRICCIÓN: Edad en gris si es edición, activa si es nuevo
                age = st.number_input("Edad", 0, 100, int(prev.get('age', 25)), disabled=es_edit)
                gender_s = st.selectbox("Género", list(TRADUCCIONES_FIJAS["gender"].values()))
                marital_s = st.selectbox("Estado Civil", list(TRADUCCIONES_FIJAS["maritalstatus"].values()))
            with col2:
                income = st.number_input("Sueldo", 0, 50000, int(prev.get('monthlyincome', 3000)))
                overtime_s = st.radio("Horas Extra", list(TRADUCCIONES_FIJAS["overtime"].values()), horizontal=True)
                contract = st.selectbox("Contrato", ["Fijo", "Temporal", "Servicios"])
            with col3:
                dept_s = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()))
                role_s = st.selectbox("Puesto", list(MAPEO_ROLES.values()))
                ed_s = st.selectbox("Educación", list(MAPEO_EDUCACION.values()))

            # CAMPOS DE MÉTRICAS (TODOS LOS CAMPOS)
            st.write("---")
            col4, col5, col6 = st.columns(3)
            with col4:
                dist = st.number_input("Distancia Km", 0, 100, int(prev.get('distancefromhome', 5)))
                y_total = st.number_input("Años Exp. Total", 0, 50, int(prev.get('totalworkingyears', 5)))
                y_comp = st.number_input("Años en Empresa", 0, 50, int(prev.get('yearsatcompany', 0)))
            with col5:
                perf = st.number_input("Desempeño (1-4)", 1, 4, int(prev.get('performancerating', 3)))
                training = st.number_input("Capacitaciones", 0, 10, int(prev.get('trainingtimeslastyear', 2)))
                tardanzas = st.number_input("Tardanzas", 0, 100, int(prev.get('numerotardanzas', 0)))
            with col6:
                faltas = st.number_input("Faltas", 0, 100, int(prev.get('numerofaltas', 0)))
                f_ingreso = st.date_input("Fecha Ingreso", date.today())
                travel_s = st.selectbox("Viajes", list(TRADUCCIONES_FIJAS["businesstravel"].values()))

            # LÓGICA DE BLOQUEO DE EDAD
            bloqueado = age < 18
            if bloqueado:
                st.error("❗ ERROR: No se permiten menores de 18 años. Guardado bloqueado.")

            b1, b2 = st.columns(2)
            with b1:
                # Botón desactivado físicamente si edad < 18
                submit = st.form_submit_button("CONFIRMAR Y GUARDAR", disabled=bloqueado)
            with b2:
                if st.form_submit_button("CANCELAR"):
                    st.session_state.edit_id = None
                    st.session_state.show_add = False
                    st.rerun()

            if submit and not bloqueado:
                # Reversión de nombres para la base de datos
                def rev(d, v): return [k for k, val in d.items() if val == v][0]
                
                payload = {
                    "age": age, "monthlyincome": income, "tipocontrato": contract,
                    "distancefromhome": dist, "totalworkingyears": y_total, "yearsatcompany": y_comp,
                    "performancerating": perf, "trainingtimeslastyear": training,
                    "numerotardanzas": tardanzas, "numerofaltas": faltas, "fechaingreso": f_ingreso.isoformat(),
                    "gender": rev(TRADUCCIONES_FIJAS["gender"], gender_s),
                    "maritalstatus": rev(TRADUCCIONES_FIJAS["maritalstatus"], marital_s),
                    "overtime": rev(TRADUCCIONES_FIJAS["overtime"], overtime_s),
                    "department": rev(MAPEO_DEPTOS, dept_s),
                    "jobrole": rev(MAPEO_ROLES, role_s),
                    "educationfield": rev(MAPEO_EDUCACION, ed_s),
                    "businesstravel": rev(TRADUCCIONES_FIJAS["businesstravel"], travel_s)
                }

                if es_edit:
                    final_data = {COLUMN_MAPPING[k]: v for k, v in payload.items() if k in COLUMN_MAPPING}
                    supabase.table("empleados").update(final_data).eq("EmployeeNumber", st.session_state.edit_id).execute()
                else:
                    # Generar ID correlativo
                    last_id_res = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
                    new_id = (last_id_res.data[0]['EmployeeNumber'] + 1) if last_id_res.data else 1
                    payload["employeenumber"] = new_id
                    final_data = {COLUMN_MAPPING[k]: v for k, v in payload.items() if k in COLUMN_MAPPING}
                    supabase.table("empleados").insert(final_data).execute()

                st.session_state.edit_id = None
                st.session_state.show_add = False
                st.rerun()

if __name__ == "__main__":
    render_employee_management_page()












