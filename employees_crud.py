import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS PRECISOS
# =================================================================

# Mapeo exacto solicitado: I+D / Desarrollo
MAPEO_DEPTOS = {
    "Sales": "Ventas", 
    "Research & Development": "I+D / Desarrollo", 
    "Human Resources": "Recursos Humanos"
}

MAPEO_EDUCACION = {
    "Life Sciences": "Ciencias de la Vida", "Other": "Otros", "Medical": "Médico", 
    "Marketing": "Marketing", "Technical Degree": "Grado Técnico", "Human Resources": "Recursos Humanos"
}

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

# -----------------------------------
# 2. FUNCIONES DE BÚSQUEDA Y DATOS
# -----------------------------------

def fetch_employees():
    res = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
    return [{k.lower(): v for k, v in r.items()} for r in res.data]

# -----------------------------------
# 3. INTERFAZ DE USUARIO
# -----------------------------------

def render_employee_management_page():
    st.title("👥 Panel de Gestión Humana")

    # Estados de la sesión
    if "edit_id" not in st.session_state: st.session_state.edit_id = None
    if "show_add" not in st.session_state: st.session_state.show_add = False

    # --- TABLA SUPERIOR ---
    raw_data = fetch_employees()
    if raw_data:
        df = pd.DataFrame(raw_data)
        # Aplicar traducción de I+D / Desarrollo y otros para la vista
        df['dept_v'] = df['department'].replace(MAPEO_DEPTOS)
        df['role_v'] = df['jobrole'].replace(MAPEO_ROLES)
        
        st.subheader("Colaboradores Registrados")
        st.dataframe(
            df[['employeenumber', 'age', 'dept_v', 'role_v', 'monthlyincome']].rename(columns={
                'employeenumber': 'ID', 'age': 'Edad', 'dept_v': 'Departamento', 
                'role_v': 'Puesto', 'monthlyincome': 'Sueldo'
            }), 
            use_container_width=True, hide_index=True
        )

    st.divider()

    # --- BUSCADOR Y ACCIONES ---
    st.subheader("🔍 Buscar y Gestionar")
    col_search, col_actions = st.columns([2, 2])
    
    with col_search:
        search_id = st.number_input("Buscar por ID de Empleado", min_value=1, step=1, value=1)
        
    with col_actions:
        st.write("Acciones rápidas:")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("✏️ Editar"):
                st.session_state.edit_id = search_id
                st.session_state.show_add = False
        with c2:
            if st.button("🗑️ Borrar"):
                supabase.table("empleados").delete().eq("EmployeeNumber", search_id).execute()
                st.rerun()
        with c3:
            if st.button("➕ Nuevo"):
                st.session_state.show_add = True
                st.session_state.edit_id = None

    # --- FORMULARIO AL FINAL ---
    if st.session_state.show_add or st.session_state.edit_id:
        st.divider()
        es_edit = st.session_state.edit_id is not None
        prev_data = {}
        
        if es_edit:
            res_ind = supabase.table("empleados").select("*").eq("EmployeeNumber", st.session_state.edit_id).execute()
            if res_ind.data:
                prev_data = {k.lower(): v for k, v in res_ind.data[0].items()}
            else:
                st.warning(f"No existe el ID {st.session_state.edit_id}")
                st.session_state.edit_id = None
                st.rerun()

        st.subheader("📄 Formulario de Datos (Modo: " + ("Edición" if es_edit else "Creación") + ")")
        
        with st.form("main_form", clear_on_submit=True):
            # 1. BLOQUE PERSONAL
            c1, c2, c3 = st.columns(3)
            with c1:
                # RESTRICCIÓN: Edad bloqueada en edición (gris)
                age = st.number_input("Edad", 0, 100, int(prev_data.get('age', 25)), disabled=es_edit)
                gender_s = st.selectbox("Género", list(TRADUCCIONES_FIJAS["gender"].values()))
            with c2:
                marital_s = st.selectbox("Estado Civil", list(TRADUCCIONES_FIJAS["maritalstatus"].values()))
                income = st.number_input("Sueldo Mensual", 0, 50000, int(prev_data.get('monthlyincome', 2500)))
            with c3:
                dept_s = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()))
                role_s = st.selectbox("Puesto de Trabajo", list(MAPEO_ROLES.values()))

            # 2. BLOQUE MÉTRICAS (TODOS LOS CAMPOS)
            st.write("**Detalles Laborales y Trayectoria**")
            m1, m2, m3 = st.columns(3)
            with m1:
                travel_s = st.selectbox("Viajes", list(TRADUCCIONES_FIJAS["businesstravel"].values()))
                dist = st.number_input("Distancia Km", 0, 100, int(prev_data.get('distancefromhome', 1)))
                over_s = st.radio("Horas Extra", list(TRADUCCIONES_FIJAS["overtime"].values()), horizontal=True)
            with m2:
                ed_s = st.selectbox("Educación", list(MAPEO_EDUCACION.values()))
                y_total = st.number_input("Años Exp. Total", 0, 50, int(prev_data.get('totalworkingyears', 1)))
                perf = st.number_input("Desempeño (1-4)", 1, 4, int(prev_data.get('performancerating', 3)))
            with m3:
                tardanzas = st.number_input("N° Tardanzas", 0, 100, int(prev_data.get('numerotardanzas', 0)))
                faltas = st.number_input("N° Faltas", 0, 100, int(prev_data.get('numerofaltas', 0)))
                f_ing = st.date_input("Fecha de Ingreso", date.today())

            # --- LÓGICA DE RESTRICCIÓN DE EDAD ---
            # Si es nuevo y edad < 18, bloqueamos. En edición ya está bloqueado el campo edad.
            es_menor = age < 18
            if es_menor:
                st.error("❌ RESTRICCIÓN: El empleado debe ser mayor de 18 años para ser registrado.")
            
            # Botones del Formulario
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                # El botón GUARDAR se deshabilita si es menor de 18
                submitted = st.form_submit_button("💾 GUARDAR CAMBIOS", disabled=es_menor)
            with f_col2:
                if st.form_submit_button("❌ CANCELAR"):
                    st.session_state.edit_id = None
                    st.session_state.show_add = False
                    st.rerun()

            if submitted and not es_menor:
                # Función para volver al inglés
                def to_eng(dic, val): return [k for k, v in dic.items() if v == val][0]
                
                payload = {
                    "age": age, "monthlyincome": income, "distancefromhome": dist,
                    "totalworkingyears": y_total, "performancerating": perf,
                    "numerotardanzas": tardanzas, "numerofaltas": faltas,
                    "fechaingreso": f_ing.isoformat(),
                    "department": to_eng(MAPEO_DEPTOS, dept_s),
                    "jobrole": to_eng(MAPEO_ROLES, role_s),
                    "educationfield": to_eng(MAPEO_EDUCACION, ed_s),
                    "gender": to_eng(TRADUCCIONES_FIJAS["gender"], gender_s),
                    "maritalstatus": to_eng(TRADUCCIONES_FIJAS["maritalstatus"], marital_s),
                    "overtime": to_eng(TRADUCCIONES_FIJAS["overtime"], over_s),
                    "businesstravel": to_eng(TRADUCCIONES_FIJAS["businesstravel"], travel_s)
                }

                if es_edit:
                    db_ready = {COLUMN_MAPPING[k]: v for k, v in payload.items() if k in COLUMN_MAPPING}
                    supabase.table("empleados").update(db_ready).eq("EmployeeNumber", st.session_state.edit_id).execute()
                    st.success("¡Datos actualizados correctamente!")
                else:
                    last_res = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
                    new_id = (last_res.data[0]['EmployeeNumber'] + 1) if last_res.data else 1
                    payload["employeenumber"] = new_id
                    db_ready = {COLUMN_MAPPING[k]: v for k, v in payload.items() if k in COLUMN_MAPPING}
                    supabase.table("empleados").insert(db_ready).execute()
                    st.success("¡Nuevo colaborador registrado!")

                st.session_state.edit_id = None
                st.session_state.show_add = False
                st.rerun()

if __name__ == "__main__":
    render_employee_management_page()











