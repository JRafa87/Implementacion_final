import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. MAPEOS Y TRADUCCIONES (IDÉNTICO A TU BASE DE DATOS)
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
    "educationfield": "EducationField", "environmentsatisfaction": "EnvironmentSatisfaction",
    "gender": "Gender", "jobinvolvement": "JobInvolvement", "joblevel": "JobLevel",
    "jobrole": "JobRole", "jobsatisfaction": "JobSatisfaction", "maritalstatus": "MaritalStatus",
    "monthlyincome": "MonthlyIncome", "numcompaniesworked": "NumCompaniesWorked", "overtime": "OverTime",
    "performancerating": "PerformanceRating", "relationshipsatisfaction": "RelationshipSatisfaction",
    "totalworkingyears": "TotalWorkingYears", "trainingtimeslastyear": "TrainingTimesLastyear",
    "yearsatcompany": "YearsAtCompany", "yearsincurrentrole": "YearsInCurrentRole",
    "yearssincelastpromotion": "YearsSinceLastPromotion", "yearswithcurrmanager": "YearsWithCurrManager",
    "tipocontrato": "Tipocontrato", "numerotardanzas": "NumeroTardanzas", "numerofaltas": "NumeroFaltas",
    "fechaingreso": "FechaIngreso"
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
    st.title("👥 Gestión de Personal")

    if "edit_id" not in st.session_state: st.session_state.edit_id = None
    if "show_add" not in st.session_state: st.session_state.show_add = False

    # --- TABLA SUPERIOR (TRADUCIDA) ---
    raw_data = fetch_employees()
    if raw_data:
        df = pd.DataFrame(raw_data)
        df['department'] = df['department'].replace(MAPEO_DEPTOS)
        df['jobrole'] = df['jobrole'].replace(MAPEO_ROLES)
        
        st.subheader("Listado General de Personal")
        st.dataframe(df.rename(columns={
            "employeenumber": "ID", "age": "Edad", "department": "Depto", "jobrole": "Puesto", 
            "monthlyincome": "Sueldo"
        })[['ID', 'Edad', 'Depto', 'Puesto', 'Sueldo']], use_container_width=True, hide_index=True)

    st.divider()

    # --- BUSCADOR ÚNICO (Escribir número o seleccionar) ---
    st.subheader("🔍 Localizar Colaborador")
    lista_ids = [str(e['employeenumber']) for e in raw_data] if raw_data else []
    
    # Usamos selectbox con búsqueda: permite escribir el número para filtrar
    id_input = st.selectbox("Escriba el número de ID o seleccione de la lista:", 
                            options=[None] + lista_ids,
                            help="Puede escribir el número directamente para buscar.")

    c_b1, c_b2, c_b3 = st.columns(3)
    with c_b1:
        if st.button("✏️ Editar Registro", use_container_width=True) and id_input:
            st.session_state.edit_id = int(id_input)
            st.session_state.show_add = False
            st.rerun()
    with c_b2:
        if st.button("🗑️ Eliminar Registro", use_container_width=True) and id_input:
            supabase.table("empleados").delete().eq("EmployeeNumber", int(id_input)).execute()
            st.rerun()
    with c_b3:
        if st.button("➕ Nuevo Empleado", use_container_width=True):
            st.session_state.show_add = True
            st.session_state.edit_id = None
            st.rerun()

    # --- FORMULARIO COMPLETO ---
    if st.session_state.show_add or st.session_state.edit_id:
        st.divider()
        es_edit = st.session_state.edit_id is not None
        p = {}
        if es_edit:
            res_ind = supabase.table("empleados").select("*").eq("EmployeeNumber", st.session_state.edit_id).execute()
            p = {k.lower(): v for k, v in res_ind.data[0].items()} if res_ind.data else {}

        st.subheader("📋 Formulario Completo de Datos")
        
        with st.form("form_final"):
            # FILA 1: BÁSICOS
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                age = st.number_input("Edad", 0, 100, int(p.get('age', 25)), disabled=es_edit)
                gender = st.selectbox("Género", list(TRADUCCIONES_FIJAS["gender"].values()))
            with c2:
                income = st.number_input("Sueldo", 0, 50000, int(p.get('monthlyincome', 3000)))
                marital = st.selectbox("Estado Civil", list(TRADUCCIONES_FIJAS["maritalstatus"].values()))
            with c3:
                dept = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()))
                role = st.selectbox("Puesto", list(MAPEO_ROLES.values()))
            with c4:
                contract = st.selectbox("Tipo Contrato", ["Fijo", "Temporal", "Servicios"])
                f_ing = st.date_input("Fecha Ingreso", date.today())

            # FILA 2: SATISFACCIÓN Y NIVELES
            st.write("**Métricas de Satisfacción y Nivel**")
            c5, c6, c7, c8 = st.columns(4)
            with c5:
                env_sat = st.slider("Satis. Entorno", 1, 4, int(p.get('environmentsatisfaction', 3)))
                job_sat = st.slider("Satis. Trabajo", 1, 4, int(p.get('jobsatisfaction', 3)))
            with c6:
                job_inv = st.slider("Involucramiento", 1, 4, int(p.get('jobinvolvement', 3)))
                rel_sat = st.slider("Satis. Relaciones", 1, 4, int(p.get('relationshipsatisfaction', 3)))
            with c7:
                perf = st.slider("Desempeño", 1, 4, int(p.get('performancerating', 3)))
                job_lvl = st.slider("Nivel Puesto", 1, 5, int(p.get('joblevel', 1)))
            with c8:
                overtime = st.radio("Horas Extra", list(TRADUCCIONES_FIJAS["overtime"].values()), horizontal=True)
                travel = st.selectbox("Viajes", list(TRADUCCIONES_FIJAS["businesstravel"].values()))

            # FILA 3: EDUCACIÓN Y TRAYECTORIA
            st.write("**Educación y Trayectoria**")
            c9, c10, c11, c12 = st.columns(4)
            with c9:
                ed_field = st.selectbox("Campo Estudio", list(MAPEO_EDUCACION.values()))
                ed_lvl = st.number_input("Nivel Educ.", 1, 5, int(p.get('education', 3)))
            with c10:
                dist = st.number_input("Distancia Km", 0, 100, int(p.get('distancefromhome', 5)))
                num_comp = st.number_input("Empresas Prev.", 0, 20, int(p.get('numcompaniesworked', 1)))
            with c11:
                y_total = st.number_input("Años Exp. Total", 0, 50, int(p.get('totalworkingyears', 5)))
                y_comp = st.number_input("Años Empresa", 0, 50, int(p.get('yearsatcompany', 0)))
            with c12:
                tardanzas = st.number_input("Tardanzas", 0, 100, int(p.get('numerotardanzas', 0)))
                faltas = st.number_input("Faltas", 0, 100, int(p.get('numerofaltas', 0)))

            # CAMPOS ADICIONALES (Ocultos pero necesarios para la lógica)
            training = int(p.get('trainingtimeslastyear', 2))
            y_role = int(p.get('yearsincurrentrole', 0))
            y_promo = int(p.get('yearssincelastpromotion', 0))
            y_mgr = int(p.get('yearswithcurrmanager', 0))

            # --- RESTRICCIÓN DE EDAD (IGUAL O MAYOR A 18) ---
            bloqueado = age < 18
            if bloqueado:
                st.error("🚫 RESTRICCIÓN: No se permiten menores de 18 años.")

            b_save, b_cancel = st.columns(2)
            with b_save:
                # El botón se inhabilita físicamente si la edad es menor a 18
                submit = st.form_submit_button("💾 GUARDAR CAMBIOS", disabled=bloqueado)
            with b_cancel:
                if st.form_submit_button("❌ CANCELAR"):
                    st.session_state.edit_id = None
                    st.session_state.show_add = False
                    st.rerun()

            if submit and not bloqueado:
                def to_eng(d, v): return [k for k, val in d.items() if val == v][0]
                payload = {
                    "age": age, "monthlyincome": income, "distancefromhome": dist, "education": ed_lvl,
                    "environmentsatisfaction": env_sat, "jobinvolvement": job_inv, "joblevel": job_lvl,
                    "jobsatisfaction": job_sat, "numcompaniesworked": num_comp, "performancerating": perf,
                    "relationshipsatisfaction": rel_sat, "totalworkingyears": y_total, "trainingtimeslastyear": training,
                    "yearsatcompany": y_comp, "yearsincurrentrole": y_role, "yearssincelastpromotion": y_promo,
                    "yearswithcurrmanager": y_mgr, "numerotardanzas": tardanzas, "numerofaltas": faltas,
                    "fechaingreso": f_ing.isoformat(), "tipocontrato": contract,
                    "department": to_eng(MAPEO_DEPTOS, dept), "jobrole": to_eng(MAPEO_ROLES, role),
                    "educationfield": to_eng(MAPEO_EDUCACION, ed_field), "gender": to_eng(TRADUCCIONES_FIJAS["gender"], gender),
                    "maritalstatus": to_eng(TRADUCCIONES_FIJAS["maritalstatus"], marital), "overtime": to_eng(TRADUCCIONES_FIJAS["overtime"], overtime),
                    "businesstravel": to_eng(TRADUCCIONES_FIJAS["businesstravel"], travel)
                }
                db_ready = {COLUMN_MAPPING[k]: v for k, v in payload.items() if k in COLUMN_MAPPING}
                
                if es_edit:
                    supabase.table("empleados").update(db_ready).eq("EmployeeNumber", st.session_state.edit_id).execute()
                else:
                    l_res = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
                    db_ready["EmployeeNumber"] = (l_res.data[0]['EmployeeNumber'] + 1) if l_res.data else 1
                    supabase.table("empleados").insert(db_ready).execute()
                
                st.session_state.edit_id = None
                st.session_state.show_add = False
                st.rerun()

if __name__ == "__main__":
    render_employee_management_page()











