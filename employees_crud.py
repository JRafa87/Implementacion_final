import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS (Español <-> Inglés)
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
    # Mantenemos nombres de variables originales internamente (minúsculas para facilitar manejo en DF)
    return [{k.lower(): v for k, v in r.items()} for r in res.data]

def to_eng(mapeo, valor_esp):
    """Retorna la llave en inglés dado el valor en español."""
    return [k for k, v in mapeo.items() if v == valor_esp][0]

# =================================================================
# 2. INTERFAZ DE USUARIO
# =================================================================

def render_employee_management_page():
    st.title("👥 Gestión de Personal")

    if "edit_id" not in st.session_state: st.session_state.edit_id = None
    if "show_add" not in st.session_state: st.session_state.show_add = False

    proceso_activo = st.session_state.edit_id is not None or st.session_state.show_add

    # --- TABLA DE LISTADO ---
    raw_data = fetch_employees()
    df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()
    
    if not df.empty:
        st.subheader("Listado General de Personal")
        # Traducción para visualización en tabla
        df_display = df.copy()
        df_display['department'] = df_display['department'].replace(MAPEO_DEPTOS)
        df_display['jobrole'] = df_display['jobrole'].replace(MAPEO_ROLES)
        df_display['educationfield'] = df_display['educationfield'].replace(MAPEO_EDUCACION)
        
        cols_table = {
            "employeenumber": "ID", "age": "Edad", "department": "Depto", 
            "jobrole": "Puesto", "monthlyincome": "Sueldo", "educationfield": "Educación"
        }
        st.dataframe(df_display.rename(columns=cols_table)[cols_table.values()], use_container_width=True, hide_index=True)

    st.divider()

    # --- BUSCADOR HÍBRIDO ---
    st.subheader("🔍 Localizar Colaborador")
    lista_ids = [str(e['employeenumber']) for e in raw_data] if raw_data else []
    id_seleccionado = st.selectbox("Busque o escriba el ID del empleado:", options=[None] + lista_ids, disabled=proceso_activo)
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

    # --- FORMULARIO INTEGRAL (TODOS LOS CAMPOS) ---
    if proceso_activo:
        st.divider()
        es_edit = st.session_state.edit_id is not None
        p = next((e for e in raw_data if e['employeenumber'] == st.session_state.edit_id), {}) if es_edit else {}

        st.subheader("📋 Formulario de Datos" + (" (Edición)" if es_edit else " (Nuevo)"))
        
        # Edad con restricción y visualización gris en edición
        age = st.number_input("Edad (Mínimo 18)", 0, 100, int(p.get('age', 25)), disabled=es_edit)
        
        if age < 18:
            st.error("🚫 La edad debe ser mayor o igual a 18 para habilitar el guardado.")
            valid_age = False
        else:
            valid_age = True

        with st.form("full_employee_form"):
            # SECCIÓN 1: DATOS LABORALES BÁSICOS
            st.write("### 💼 Información Laboral")
            col1, col2, col3 = st.columns(3)
            with col1:
                income = st.number_input("Sueldo Mensual", 0, 100000, int(p.get('monthlyincome', 3000)))
                dist = st.number_input("Distancia Casa (km)", 0, 200, int(p.get('distancefromhome', 5)))
            with col2:
                curr_dept = MAPEO_DEPTOS.get(p.get('department'), list(MAPEO_DEPTOS.values())[0])
                dept = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()), index=list(MAPEO_DEPTOS.values()).index(curr_dept))
                curr_role = MAPEO_ROLES.get(p.get('jobrole'), list(MAPEO_ROLES.values())[0])
                role = st.selectbox("Puesto", list(MAPEO_ROLES.values()), index=list(MAPEO_ROLES.values()).index(curr_role))
            with col3:
                f_ing_val = p.get('fechaingreso')
                f_ing = st.date_input("Fecha de Ingreso", date.fromisoformat(f_ing_val) if f_ing_val else date.today())
                overtime = st.checkbox("Trabaja Horas Extra", value=(p.get('overtime') == 'Yes'))

            # SECCIÓN 2: EDUCACIÓN Y SATISFACCIÓN
            st.write("### 🎓 Educación y Satisfacción")
            col4, col5, col6 = st.columns(3)
            with col4:
                curr_edu = MAPEO_EDUCACION.get(p.get('educationfield'), list(MAPEO_EDUCACION.values())[0])
                ed_field = st.selectbox("Campo de Estudio", list(MAPEO_EDUCACION.values()), index=list(MAPEO_EDUCACION.values()).index(curr_edu))
                ed_lvl = st.slider("Nivel de Educación", 1, 5, int(p.get('education', 3)))
            with col5:
                env_sat = st.slider("Satis. Entorno", 1, 4, int(p.get('environmentsatisfaction', 3)))
                job_sat = st.slider("Satis. Trabajo", 1, 4, int(p.get('jobsatisfaction', 3)))
            with col6:
                rel_sat = st.slider("Satis. Relaciones", 1, 4, int(p.get('relationshipsatisfaction', 3)))
                job_inv = st.slider("Involucramiento", 1, 4, int(p.get('jobinvolvement', 3)))

            # SECCIÓN 3: HISTORIAL Y ASISTENCIA
            st.write("### 📈 Historial y Asistencia")
            col7, col8, col9 = st.columns(3)
            with col7:
                y_total = st.number_input("Años Exp. Total", 0, 50, int(p.get('totalworkingyears', 5)))
                y_comp = st.number_input("Años en Empresa", 0, 50, int(p.get('yearsatcompany', 1)))
            with col8:
                num_comp = st.number_input("Empresas Previas", 0, 15, int(p.get('numcompaniesworked', 1)))
                stock = st.number_input("Nivel de Acciones", 0, 3, int(p.get('stockoptionlevel', 0)))
            with col9:
                tardanzas = st.number_input("Tardanzas", 0, 100, int(p.get('numerotardanzas', 0)))
                faltas = st.number_input("Faltas", 0, 100, int(p.get('numerofaltas', 0)))

            # BOTÓN DE ACCIÓN
            btn_save = st.form_submit_button("💾 GUARDAR REGISTRO", disabled=not valid_age)
            
            if btn_save:
                # REVERSIÓN A IDIOMA ORIGINAL PARA SUPABASE
                payload = {
                    "Age": age,
                    "MonthlyIncome": income,
                    "Department": to_eng(MAPEO_DEPTOS, dept),
                    "JobRole": to_eng(MAPEO_ROLES, role),
                    "EducationField": to_eng(MAPEO_EDUCACION, ed_field),
                    "Education": ed_lvl,
                    "EnvironmentSatisfaction": env_sat,
                    "JobSatisfaction": job_sat,
                    "RelationshipSatisfaction": rel_sat,
                    "JobInvolvement": job_inv,
                    "DistanceFromHome": dist,
                    "TotalWorkingYears": y_total,
                    "YearsAtCompany": y_comp,
                    "NumCompaniesWorked": num_comp,
                    "StockOptionLevel": stock,
                    "NumeroTardanzas": tardanzas,
                    "NumeroFaltas": faltas,
                    "OverTime": "Yes" if overtime else "No",
                    "FechaIngreso": f_ing.isoformat()
                }
                
                if es_edit:
                    supabase.table("empleados").update(payload).eq("EmployeeNumber", st.session_state.edit_id).execute()
                else:
                    # Auto-incremento manual del ID
                    l_res = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
                    payload["EmployeeNumber"] = (l_res.data[0]['EmployeeNumber'] + 1) if l_res.data else 1
                    supabase.table("empleados").insert(payload).execute()
                
                st.session_state.edit_id = None
                st.session_state.show_add = False
                st.success("Operación exitosa.")
                st.rerun()

        if st.button("❌ Cancelar"):
            st.session_state.edit_id = None
            st.session_state.show_add = False
            st.rerun()

if __name__ == "__main__":
    render_employee_management_page()











