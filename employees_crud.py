import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. MAPEOS Y TRADUCCIONES (ESTRICTO)
# =================================================================

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

# Diccionario completo para asegurar que NINGÚN campo falte en el envío a Supabase
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

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key)

supabase = get_supabase()

# -----------------------------------
# 2. LÓGICA DE DATOS
# -----------------------------------

def fetch_employees():
    res = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
    return [{k.lower(): v for k, v in r.items()} for r in res.data]

# -----------------------------------
# 3. INTERFAZ DE USUARIO
# -----------------------------------

def render_employee_management_page():
    st.title("👥 Gestión Integral de Personal")

    if "edit_id" not in st.session_state: st.session_state.edit_id = None
    if "show_add" not in st.session_state: st.session_state.show_add = False

    # --- TABLA SUPERIOR ---
    raw_data = fetch_employees()
    if raw_data:
        df = pd.DataFrame(raw_data)
        # CORRECCIÓN I+D / DESARROLLO EN TABLA
        df['department'] = df['department'].replace(MAPEO_DEPTOS)
        df['jobrole'] = df['jobrole'].replace(MAPEO_ROLES)
        
        st.subheader("Listado de Colaboradores")
        view_cols = ['employeenumber', 'age', 'department', 'jobrole', 'monthlyincome']
        st.dataframe(
            df[view_cols].rename(columns={
                'employeenumber': 'ID', 'age': 'Edad', 'department': 'Departamento', 
                'jobrole': 'Puesto', 'monthlyincome': 'Sueldo'
            }), 
            use_container_width=True, hide_index=True
        )

    st.divider()

    # --- BUSCADOR Y ACCIONES ---
    c_s, c_a = st.columns([2, 2])
    with c_s:
        search_id = st.number_input("Ingrese ID para buscar:", min_value=1, value=1)
    with c_a:
        st.write("Acciones")
        ca1, ca2, ca3 = st.columns(3)
        with ca1:
            if st.button("✏️ Editar"):
                st.session_state.edit_id = search_id
                st.session_state.show_add = False
                st.rerun()
        with ca2:
            if st.button("🗑️ Borrar"):
                supabase.table("empleados").delete().eq("EmployeeNumber", search_id).execute()
                st.rerun()
        with ca3:
            if st.button("➕ Nuevo"):
                st.session_state.show_add = True
                st.session_state.edit_id = None
                st.rerun()

    # --- FORMULARIO COMPLETO (AL FINAL) ---
    if st.session_state.show_add or st.session_state.edit_id:
        es_edit = st.session_state.edit_id is not None
        p = {} # Datos previos
        
        if es_edit:
            res_ind = supabase.table("empleados").select("*").eq("EmployeeNumber", st.session_state.edit_id).execute()
            if res_ind.data:
                p = {k.lower(): v for k, v in res_ind.data[0].items()}
            else:
                st.error(f"ID {st.session_state.edit_id} no encontrado.")
                st.session_state.edit_id = None
                st.rerun()

        st.subheader("📋 Formulario con Todos los Campos")
        
        with st.form("full_form"):
            # FILA 1: BÁSICOS
            f1_1, f1_2, f1_3, f1_4 = st.columns(4)
            with f1_1:
                age = st.number_input("Edad", 0, 100, int(p.get('age', 25)), disabled=es_edit)
                gender = st.selectbox("Género", list(TRADUCCIONES_FIJAS["gender"].values()))
            with f1_2:
                marital = st.selectbox("Estado Civil", list(TRADUCCIONES_FIJAS["maritalstatus"].values()))
                income = st.number_input("Sueldo", 0, 50000, int(p.get('monthlyincome', 3000)))
            with f1_3:
                dept = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()))
                role = st.selectbox("Puesto", list(MAPEO_ROLES.values()))
            with f1_4:
                contract = st.selectbox("Contrato", ["Fijo", "Temporal", "Servicios"])
                f_ing = st.date_input("Ingreso", date.today())

            # FILA 2: SATISFACCIÓN Y ENTORNO (CAMPOS ANTES OMITIDOS)
            st.write("**Satisfacción y Nivel (1-4)**")
            f2_1, f2_2, f2_3, f2_4 = st.columns(4)
            with f2_1:
                env_sat = st.slider("Satisfacción Entorno", 1, 4, int(p.get('environmentsatisfaction', 3)))
                job_sat = st.slider("Satisfacción Trabajo", 1, 4, int(p.get('jobsatisfaction', 3)))
            with f2_2:
                job_inv = st.slider("Involucramiento", 1, 4, int(p.get('jobinvolvement', 3)))
                rel_sat = st.slider("Satis. Relaciones", 1, 4, int(p.get('relationshipsatisfaction', 3)))
            with f2_3:
                job_lvl = st.slider("Nivel de Puesto", 1, 5, int(p.get('joblevel', 1)))
                perf = st.slider("Desempeño", 1, 4, int(p.get('performancerating', 3)))
            with f2_4:
                overtime = st.radio("Horas Extra", list(TRADUCCIONES_FIJAS["overtime"].values()))
                travel = st.selectbox("Viajes", list(TRADUCCIONES_FIJAS["businesstravel"].values()))

            # FILA 3: TRAYECTORIA
            st.write("**Trayectoria y Faltas**")
            f3_1, f3_2, f3_3, f3_4 = st.columns(4)
            with f3_1:
                dist = st.number_input("Distancia Km", 0, 100, int(p.get('distancefromhome', 5)))
                ed_lvl = st.number_input("Nivel Educ.", 1, 5, int(p.get('education', 3)))
            with f3_2:
                ed_field = st.selectbox("Campo Estudio", list(MAPEO_EDUCACION.values()))
                num_comp = st.number_input("Empresas Prev.", 0, 20, int(p.get('numcompaniesworked', 1)))
            with f3_3:
                y_total = st.number_input("Años Exp. Total", 0, 50, int(p.get('totalworkingyears', 5)))
                y_comp = st.number_input("Años Empresa", 0, 50, int(p.get('yearsatcompany', 0)))
            with f3_4:
                tardanzas = st.number_input("Tardanzas", 0, 100, int(p.get('numerotardanzas', 0)))
                faltas = st.number_input("Faltas", 0, 100, int(p.get('numerofaltas', 0)))

            # RESTO DE CAMPOS TÉCNICOS
            y_role = int(p.get('yearsincurrentrole', 0))
            y_promo = int(p.get('yearssincelastpromotion', 0))
            y_mgr = int(p.get('yearswithcurrmanager', 0))
            training = int(p.get('trainingtimeslastyear', 2))

            # --- VALIDACIÓN DE EDAD (BLOQUEO REAL) ---
            es_menor = age < 18
            if es_menor:
                st.error("🚫 ACCESO DENEGADO: El colaborador debe ser mayor de 18 años.")
            
            b_save, b_cancel = st.columns(2)
            with b_save:
                # El botón se desactiva físicamente
                guardar = st.form_submit_button("💾 GUARDAR TODO", disabled=es_menor)
            with b_cancel:
                if st.form_submit_button("❌ CANCELAR"):
                    st.session_state.edit_id = None
                    st.session_state.show_add = False
                    st.rerun()

            if guardar and not es_menor:
                def to_eng(d, v): return [k for k, val in d.items() if val == v][0]
                
                payload = {
                    "age": age, "monthlyincome": income, "distancefromhome": dist,
                    "education": ed_lvl, "environmentsatisfaction": env_sat,
                    "jobinvolvement": job_inv, "joblevel": job_lvl,
                    "jobsatisfaction": job_sat, "numcompaniesworked": num_comp,
                    "performancerating": perf, "relationshipsatisfaction": rel_sat,
                    "totalworkingyears": y_total, "trainingtimeslastyear": training,
                    "yearsatcompany": y_comp, "yearsincurrentrole": y_role,
                    "yearssincelastpromotion": y_promo, "yearswithcurrmanager": y_mgr,
                    "numerotardanzas": tardanzas, "numerofaltas": faltas,
                    "fechaingreso": f_ing.isoformat(), "tipocontrato": contract,
                    "department": to_eng(MAPEO_DEPTOS, dept),
                    "jobrole": to_eng(MAPEO_ROLES, role),
                    "educationfield": to_eng(MAPEO_EDUCACION, ed_field),
                    "gender": to_eng(TRADUCCIONES_FIJAS["gender"], gender),
                    "maritalstatus": to_eng(TRADUCCIONES_FIJAS["maritalstatus"], marital),
                    "overtime": to_eng(TRADUCCIONES_FIJAS["overtime"], overtime),
                    "businesstravel": to_eng(TRADUCCIONES_FIJAS["businesstravel"], travel)
                }

                db_data = {COLUMN_MAPPING[k]: v for k, v in payload.items() if k in COLUMN_MAPPING}

                if es_edit:
                    supabase.table("empleados").update(db_data).eq("EmployeeNumber", st.session_state.edit_id).execute()
                else:
                    l_res = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
                    new_id = (l_res.data[0]['EmployeeNumber'] + 1) if l_res.data else 1
                    db_data["EmployeeNumber"] = new_id
                    supabase.table("empleados").insert(db_data).execute()

                st.session_state.edit_id = None
                st.session_state.show_add = False
                st.rerun()

if __name__ == "__main__":
    render_employee_management_page()











