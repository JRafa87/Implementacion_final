import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS
# =================================================================

MAPEO_DEPTOS = {"Sales": "Ventas", "Research & Development": "I+D", "Human Resources": "Recursos Humanos"}
MAPEO_EDUCACION = {"Life Sciences": "Ciencias de la Vida", "Other": "Otros", "Medical": "Médico", "Marketing": "Marketing", "Technical Degree": "Grado Técnico", "Human Resources": "Recursos Humanos"}
MAPEO_ROLES = {
    "Sales Executive": "Ejecutivo de Ventas", "Research Scientist": "Científico de Investigación",
    "Laboratory Technician": "Técnico de Laboratorio", "Manufacturing Director": "Director de Manufactura",
    "Healthcare Representative": "Representante de Salud", "Manager": "Gerente",
    "Sales Representative": "Representante de Ventas", "Research Director": "Director de Investigación",
    "Human Resources": "Recursos Humanos"
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

    proceso_activo = st.session_state.edit_id is not None or st.session_state.show_add

    # --- TABLA SUPERIOR ---
    raw_data = fetch_employees()
    df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()
    
    if not df.empty:
        df['department_esp'] = df['department'].replace(MAPEO_DEPTOS)
        df['jobrole_esp'] = df['jobrole'].replace(MAPEO_ROLES)
        df['educationfield_esp'] = df['educationfield'].replace(MAPEO_EDUCACION)
        
        st.subheader("Listado General de Personal")
        cols_mostrar = {
            "employeenumber": "ID", "age": "Edad", "department_esp": "Depto", 
            "jobrole_esp": "Puesto", "monthlyincome": "Sueldo",
            "educationfield_esp": "Educación", "totalworkingyears": "Exp. Total"
        }
        st.dataframe(df.rename(columns=cols_mostrar)[cols_mostrar.values()], use_container_width=True, hide_index=True)

    st.divider()

    # --- BUSCADOR HÍBRIDO ---
    st.subheader("🔍 Localizar Colaborador")
    lista_ids = [str(e['employeenumber']) for e in raw_data] if raw_data else []
    
    id_seleccionado = st.selectbox(
        "Busque o escriba el ID del empleado:",
        options=[None] + lista_ids,
        disabled=proceso_activo
    )
    id_existe = id_seleccionado is not None

    c_b1, c_b2, c_b3 = st.columns(3)
    with c_b1:
        if st.button("✏️ Editar Registro", use_container_width=True, disabled=proceso_activo or not id_existe):
            st.session_state.edit_id = int(id_seleccionado)
            st.rerun()
    with c_b2:
        if st.button("🗑️ Eliminar Registro", use_container_width=True, disabled=proceso_activo or not id_existe):
            supabase.table("empleados").delete().eq("EmployeeNumber", int(id_seleccionado)).execute()
            st.rerun()
    with c_b3:
        if st.button("➕ Nuevo Registro", use_container_width=True, disabled=proceso_activo):
            st.session_state.show_add = True
            st.rerun()

    # --- FORMULARIO INTEGRAL ---
    if proceso_activo:
        st.divider()
        es_edit = st.session_state.edit_id is not None
        p = next((e for e in raw_data if e['employeenumber'] == st.session_state.edit_id), {}) if es_edit else {}

        st.subheader("📋 Formulario de Datos" + (" (Modo Edición)" if es_edit else " (Nuevo Registro)"))
        
        # Validación de edad inmediata
        age = st.number_input("Edad (Mínimo 18 años)", 0, 100, int(p.get('age', 25)), disabled=es_edit)
        
        if age < 18:
            st.error("🚫 Bloqueo: La edad debe ser mayor o igual a 18 para registrar.")
            permitir_guardado = False
        else:
            permitir_guardado = True

        with st.form("full_form"):
            # FILA 1: LABORAL
            st.write("**Información Laboral**")
            c1, c2, c3 = st.columns(3)
            with c1:
                income = st.number_input("Sueldo Mensual", 0, 100000, int(p.get('monthlyincome', 3000)))
            with c2:
                val_depto = MAPEO_DEPTOS.get(p.get('department'), list(MAPEO_DEPTOS.values())[0])
                dept = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()), index=list(MAPEO_DEPTOS.values()).index(val_depto))
            with c3:
                val_role = MAPEO_ROLES.get(p.get('jobrole'), list(MAPEO_ROLES.values())[0])
                role = st.selectbox("Puesto", list(MAPEO_ROLES.values()), index=list(MAPEO_ROLES.values()).index(val_role))

            # FILA 2: EDUCACIÓN Y MÉTRICAS
            st.write("**Educación y Satisfacción**")
            e1, e2, e3, e4 = st.columns(4)
            with e1:
                val_edu = MAPEO_EDUCACION.get(p.get('educationfield'), list(MAPEO_EDUCACION.values())[0])
                ed_field = st.selectbox("Campo de Estudio", list(MAPEO_EDUCACION.values()), index=list(MAPEO_EDUCACION.values()).index(val_edu))
            with e2:
                ed_lvl = st.number_input("Nivel Educación (1-5)", 1, 5, int(p.get('education', 3)))
            with e3:
                env_sat = st.slider("Satis. Entorno", 1, 4, int(p.get('environmentsatisfaction', 3)))
            with e4:
                job_sat = st.slider("Satis. Trabajo", 1, 4, int(p.get('jobsatisfaction', 3)))

            # FILA 3: TRAYECTORIA Y ASISTENCIA
            st.write("**Trayectoria y Asistencia**")
            t1, t2, t3, t4 = st.columns(4)
            with t1:
                y_total = st.number_input("Años Exp. Total", 0, 50, int(p.get('totalworkingyears', 5)))
            with t2:
                y_comp = st.number_input("Años en Empresa", 0, 50, int(p.get('yearsatcompany', 1)))
            with t3:
                tardanzas = st.number_input("N° Tardanzas", 0, 500, int(p.get('numerotardanzas', 0)))
            with t4:
                faltas = st.number_input("N° Faltas", 0, 500, int(p.get('numerofaltas', 0)))

            f_ing = st.date_input("Fecha de Ingreso", date.today() if not p.get('fechaingreso') else date.fromisoformat(p.get('fechaingreso')))

            # BOTÓN DE GUARDADO
            btn_save = st.form_submit_button("💾 GUARDAR CAMBIOS", disabled=not permitir_guardado)
            
            if btn_save:
                def to_eng(d, v): return [k for k, val in d.items() if val == v][0]
                payload = {
                    "Age": age, "MonthlyIncome": income, "Department": to_eng(MAPEO_DEPTOS, dept),
                    "JobRole": to_eng(MAPEO_ROLES, role), "EducationField": to_eng(MAPEO_EDUCACION, ed_field),
                    "Education": ed_lvl, "EnvironmentSatisfaction": env_sat, "JobSatisfaction": job_sat,
                    "TotalWorkingYears": y_total, "YearsAtCompany": y_comp, "NumeroTardanzas": tardanzas,
                    "NumeroFaltas": faltas, "FechaIngreso": f_ing.isoformat()
                }
                
                if es_edit:
                    supabase.table("empleados").update(payload).eq("EmployeeNumber", st.session_state.edit_id).execute()
                else:
                    l_res = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
                    payload["EmployeeNumber"] = (l_res.data[0]['EmployeeNumber'] + 1) if l_res.data else 1
                    supabase.table("empleados").insert(payload).execute()
                
                st.session_state.edit_id = None
                st.session_state.show_add = False
                st.rerun()

        if st.button("❌ Cancelar Operación"):
            st.session_state.edit_id = None
            st.session_state.show_add = False
            st.rerun()

if __name__ == "__main__":
    render_employee_management_page()











