import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. MAPEOS Y TRADUCCIONES
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

    # --- TABLA SUPERIOR (CORREGIDO I+D / DESARROLLO) ---
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

    # --- BUSCADOR ÚNICO (Escribir o Seleccionar) ---
    st.subheader("🔍 Localizar Colaborador")
    lista_ids = [str(e['employeenumber']) for e in raw_data] if raw_data else []
    
    id_input = st.selectbox("Busque por número de ID o seleccione de la lista:", 
                            options=[None] + lista_ids)

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
        if st.button("➕ Nuevo Registro", use_container_width=True):
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
        
        # FILA 1: DATOS CLAVE (Fuera del form para que la edad bloquee dinámicamente)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            age = st.number_input("Edad (Mínimo 18)", 0, 100, int(p.get('age', 25)), key="age_input")
        with c2:
            income = st.number_input("Sueldo", 0, 50000, int(p.get('monthlyincome', 3000)))
        with c3:
            dept = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()))
        with c4:
            role = st.selectbox("Puesto", list(MAPEO_ROLES.values()))

        # RESTRICCIÓN DE EDAD
        if age < 18:
            st.error("🚫 RESTRICCIÓN: El empleado debe ser mayor o igual a 18 años. El formulario está bloqueado.")
        else:
            with st.form("form_registro_completo"):
                # FILA 2: SATISFACCIÓN
                st.write("**Satisfacción y Entorno**")
                s1, s2, s3, s4 = st.columns(4)
                with s1: env_sat = st.slider("Satis. Entorno", 1, 4, int(p.get('environmentsatisfaction', 3)))
                with s2: job_sat = st.slider("Satis. Trabajo", 1, 4, int(p.get('jobsatisfaction', 3)))
                with s3: job_inv = st.slider("Involucramiento", 1, 4, int(p.get('jobinvolvement', 3)))
                with s4: rel_sat = st.slider("Satis. Relaciones", 1, 4, int(p.get('relationshipsatisfaction', 3)))

                # FILA 3: EDUCACIÓN Y TRAYECTORIA
                st.write("**Educación y Trayectoria**")
                t1, t2, t3, t4 = st.columns(4)
                with t1:
                    ed_field = st.selectbox("Campo Estudio", list(MAPEO_EDUCACION.values()))
                    ed_lvl = st.number_input("Nivel Educ.", 1, 5, int(p.get('education', 3)))
                with t2:
                    dist = st.number_input("Distancia Km", 0, 100, int(p.get('distancefromhome', 5)))
                    num_comp = st.number_input("Empresas Prev.", 0, 20, int(p.get('numcompaniesworked', 1)))
                with t3:
                    y_total = st.number_input("Años Exp. Total", 0, 50, int(p.get('totalworkingyears', 5)))
                    y_comp = st.number_input("Años Empresa", 0, 50, int(p.get('yearsatcompany', 0)))
                with t4:
                    tardanzas = st.number_input("Tardanzas", 0, 100, int(p.get('numerotardanzas', 0)))
                    faltas = st.number_input("Faltas", 0, 100, int(p.get('numerofaltas', 0)))

                f_ing = st.date_input("Fecha Ingreso", date.today())
                
                # BOTONES DE ENVÍO
                submit = st.form_submit_button("💾 GUARDAR TODO")
                
                if submit:
                    # Lógica de guardado (Insert/Update)
                    def to_eng(d, v): return [k for k, val in d.items() if val == v][0]
                    payload = {
                        "Age": age, "MonthlyIncome": income, "Department": to_eng(MAPEO_DEPTOS, dept),
                        "JobRole": to_eng(MAPEO_ROLES, role), "EnvironmentSatisfaction": env_sat,
                        "JobSatisfaction": job_sat, "JobInvolvement": job_inv, "RelationshipSatisfaction": rel_sat,
                        "EducationField": to_eng(MAPEO_EDUCACION, ed_field), "Education": ed_lvl,
                        "DistanceFromHome": dist, "NumCompaniesWorked": num_comp, "TotalWorkingYears": y_total,
                        "YearsAtCompany": y_comp, "NumeroTardanzas": tardanzas, "NumeroFaltas": faltas,
                        "FechaIngreso": f_ing.isoformat()
                    }
                    
                    if es_edit:
                        supabase.table("empleados").update(payload).eq("EmployeeNumber", st.session_state.edit_id).execute()
                    else:
                        l_res = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
                        payload["EmployeeNumber"] = (l_res.data[0]['EmployeeNumber'] + 1) if l_res.data else 1
                        supabase.table("empleados").insert(payload).execute()
                    
                    st.success("¡Datos guardados!")
                    st.session_state.edit_id = None
                    st.session_state.show_add = False
                    st.rerun()

        if st.button("❌ Cancelar"):
            st.session_state.edit_id = None
            st.session_state.show_add = False
            st.rerun()

if __name__ == "__main__":
    render_employee_management_page()











