import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. MAPEOS Y TRADUCCIONES
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

def fetch_employees():
    res = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
    return [{k.lower(): v for k, v in r.items()} for r in res.data]

# =================================================================
# 2. INTERFAZ DE USUARIO
# =================================================================

def render_employee_management_page():
    st.title("👥 Sistema de Gestión de Empleados")

    if "edit_id" not in st.session_state: st.session_state.edit_id = None
    if "show_add" not in st.session_state: st.session_state.show_add = False

    # --- VISTA DE TABLA ---
    raw_data = fetch_employees()
    if raw_data:
        df = pd.DataFrame(raw_data)
        # TRADUCCIÓN OBLIGATORIA PARA LA TABLA
        df['department'] = df['department'].map(MAPEO_DEPTOS).fillna(df['department'])
        df['jobrole'] = df['jobrole'].map(MAPEO_ROLES).fillna(df['jobrole'])
        
        st.subheader("Colaboradores en Base de Datos")
        st.dataframe(
            df[['employeenumber', 'age', 'department', 'jobrole', 'monthlyincome']].rename(columns={
                'employeenumber': 'ID', 'age': 'Edad', 'department': 'Departamento', 
                'jobrole': 'Puesto', 'monthlyincome': 'Sueldo'
            }), 
            use_container_width=True, hide_index=True
        )

    st.divider()

    # --- BUSCADOR DUAL (DESPLEGABLE Y NÚMERO) ---
    st.subheader("🔍 Localizar Colaborador")
    lista_ids = [e['employeenumber'] for e in raw_data] if raw_data else []
    
    col_busq1, col_busq2 = st.columns(2)
    with col_busq1:
        id_desde_lista = st.selectbox("Seleccionar de la lista:", [None] + lista_ids)
    with col_busq2:
        id_manual = st.number_input("O escribir ID manualmente:", min_value=0, value=0)

    # El ID final a gestionar
    id_final = id_desde_lista if id_desde_lista else (id_manual if id_manual > 0 else None)

    col_btn1, col_btn2, col_btn3 = st.columns(3)
    with col_btn1:
        if st.button("✏️ Editar ID Seleccionado") and id_final:
            st.session_state.edit_id = id_final
            st.session_state.show_add = False
            st.rerun()
    with col_btn2:
        if st.button("🗑️ Eliminar ID Seleccionado") and id_final:
            supabase.table("empleados").delete().eq("EmployeeNumber", id_final).execute()
            st.rerun()
    with col_btn3:
        if st.button("➕ Registrar Nuevo"):
            st.session_state.show_add = True
            st.session_state.edit_id = None
            st.rerun()

    # --- FORMULARIO AL FINAL ---
    if st.session_state.show_add or st.session_state.edit_id:
        st.divider()
        es_edicion = st.session_state.edit_id is not None
        prev = {}
        
        if es_edicion:
            res_ind = supabase.table("empleados").select("*").eq("EmployeeNumber", st.session_state.edit_id).execute()
            if res_ind.data:
                prev = {k.lower(): v for k, v in res_ind.data[0].items()}
            else:
                st.error("ID no encontrado.")
                st.session_state.edit_id = None
                st.rerun()

        st.subheader("📋 Formulario Completo de Datos")
        with st.form("form_final"):
            # FILA 1
            c1, c2, c3 = st.columns(3)
            with c1:
                # RESTRICCIÓN: Edad en gris si es edición
                age = st.number_input("Edad", 0, 100, int(prev.get('age', 25)), disabled=es_edicion)
                gender = st.selectbox("Género", list(TRADUCCIONES_FIJAS["gender"].values()))
            with c2:
                marital = st.selectbox("Estado Civil", list(TRADUCCIONES_FIJAS["maritalstatus"].values()))
                income = st.number_input("Sueldo Mensual", 0, 50000, int(prev.get('monthlyincome', 3000)))
            with c3:
                dept_label = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()))
                role_label = st.selectbox("Puesto", list(MAPEO_ROLES.values()))

            # FILA 2 (MÉTRICAS Y SATISFACCIÓN)
            st.write("**Satisfacción y Entorno**")
            m1, m2, m3 = st.columns(3)
            with m1:
                env_sat = st.slider("Satisfacción Entorno", 1, 4, int(prev.get('environmentsatisfaction', 3)))
                job_sat = st.slider("Satisfacción Trabajo", 1, 4, int(prev.get('jobsatisfaction', 3)))
                overtime = st.radio("Horas Extra", list(TRADUCCIONES_FIJAS["overtime"].values()), horizontal=True)
            with m2:
                job_inv = st.slider("Involucramiento", 1, 4, int(prev.get('jobinvolvement', 3)))
                rel_sat = st.slider("Satisfacción Relaciones", 1, 4, int(prev.get('relationshipsatisfaction', 3)))
                travel = st.selectbox("Viajes de Negocio", list(TRADUCCIONES_FIJAS["businesstravel"].values()))
            with m3:
                job_lvl = st.slider("Nivel Jerárquico", 1, 5, int(prev.get('joblevel', 1)))
                perf_rat = st.slider("Calificación Desempeño", 1, 4, int(prev.get('performancerating', 3)))
                training = st.number_input("Capacitaciones Año Pasado", 0, 10, int(prev.get('trainingtimeslastyear', 2)))

            # FILA 3 (TRAYECTORIA)
            st.write("**Trayectoria y Faltas**")
            t1, t2, t3 = st.columns(3)
            with t1:
                dist = st.number_input("Distancia al Hogar (Km)", 0, 100, int(prev.get('distancefromhome', 5)))
                ed_field = st.selectbox("Campo Educación", list(MAPEO_EDUCACION.values()))
            with t2:
                y_total = st.number_input("Años Experiencia Total", 0, 50, int(prev.get('totalworkingyears', 5)))
                y_comp = st.number_input("Años en la Empresa", 0, 50, int(prev.get('yearsatcompany', 0)))
            with t3:
                tardanzas = st.number_input("Número de Tardanzas", 0, 100, int(prev.get('numerotardanzas', 0)))
                faltas = st.number_input("Número de Faltas", 0, 100, int(prev.get('numerofaltas', 0)))

            # Otros campos ocultos o por defecto necesarios para la tabla
            f_ing = st.date_input("Fecha de Ingreso", date.today())
            contract = st.selectbox("Tipo Contrato", ["Fijo", "Temporal", "Servicios"])

            # --- LÓGICA DE BLOQUEO DE EDAD ---
            es_menor = age < 18
            if es_menor:
                st.error("🚫 BLOQUEADO: El colaborador debe ser mayor de 18 años para guardar.")

            b_save, b_cancel = st.columns(2)
            with b_save:
                # El botón se inhabilita físicamente si la edad es < 18
                submitted = st.form_submit_button("💾 GUARDAR REGISTRO", disabled=es_menor)
            with b_cancel:
                if st.form_submit_button("❌ CANCELAR"):
                    st.session_state.edit_id = None
                    st.session_state.show_add = False
                    st.rerun()

            if submitted and not es_menor:
                def get_key(d, val): return [k for k, v in d.items() if v == val][0]
                
                payload = {
                    "age": age, "monthlyincome": income, "distancefromhome": dist,
                    "environmentsatisfaction": env_sat, "jobinvolvement": job_inv,
                    "joblevel": job_lvl, "jobsatisfaction": job_sat,
                    "performancerating": perf_rat, "relationshipsatisfaction": rel_sat,
                    "totalworkingyears": y_total, "trainingtimeslastyear": training,
                    "yearsatcompany": y_comp, "numerotardanzas": tardanzas, "numerofaltas": faltas,
                    "fechaingreso": f_ing.isoformat(), "tipocontrato": contract,
                    "department": get_key(MAPEO_DEPTOS, dept_label),
                    "jobrole": get_key(MAPEO_ROLES, role_label),
                    "educationfield": get_key(MAPEO_EDUCACION, ed_field),
                    "gender": get_key(TRADUCCIONES_FIJAS["gender"], gender),
                    "maritalstatus": get_key(TRADUCCIONES_FIJAS["maritalstatus"], marital),
                    "overtime": get_key(TRADUCCIONES_FIJAS["overtime"], overtime),
                    "businesstravel": get_key(TRADUCCIONES_FIJAS["businesstravel"], travel)
                }

                final_db = {COLUMN_MAPPING[k]: v for k, v in payload.items() if k in COLUMN_MAPPING}

                if es_edicion:
                    supabase.table("empleados").update(final_db).eq("EmployeeNumber", st.session_state.edit_id).execute()
                else:
                    l_res = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
                    new_id = (l_res.data[0]['EmployeeNumber'] + 1) if l_res.data else 1
                    final_db["EmployeeNumber"] = new_id
                    supabase.table("empleados").insert(final_db).execute()

                st.session_state.edit_id = None
                st.session_state.show_add = False
                st.rerun()

if __name__ == "__main__":
    render_employee_management_page()











