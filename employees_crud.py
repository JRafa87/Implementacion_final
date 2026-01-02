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

    # --- TABLA SUPERIOR COMPLETA ---
    raw_data = fetch_employees()
    df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()
    
    if not df.empty:
        df['department_esp'] = df['department'].replace(MAPEO_DEPTOS)
        df['jobrole_esp'] = df['jobrole'].replace(MAPEO_ROLES)
        
        st.subheader("Listado General de Personal")
        cols_mostrar = {
            "employeenumber": "ID", 
            "age": "Edad", 
            "department_esp": "Departamento", 
            "jobrole_esp": "Cargo", 
            "monthlyincome": "Sueldo",
            "totalworkingyears": "Años Exp.",
            "yearsatcompany": "Años Empresa",
            "educationfield": "Educación"
        }
        st.dataframe(df.rename(columns=cols_mostrar)[cols_mostrar.values()], use_container_width=True, hide_index=True)

    st.divider()

    # --- BUSCADOR HÍBRIDO (SELECTBOX + ESCRITURA) ---
    st.subheader("🔍 Localizar Colaborador")
    
    # Lista de IDs disponibles para el buscador
    lista_ids = [str(e['employeenumber']) for e in raw_data] if raw_data else []
    
    # El selectbox de Streamlit permite escribir para buscar por defecto
    id_seleccionado = st.selectbox(
        "Busque o escriba el ID del empleado:",
        options=[None] + lista_ids,
        index=0,
        disabled=proceso_activo,
        help="Puede escribir el número directamente para filtrar."
    )

    # Validamos si se ha seleccionado un ID válido
    id_existe = id_seleccionado is not None and id_seleccionado != ""

    # Mensaje informativo si no hay selección y no hay proceso activo
    if not id_existe and not proceso_activo:
        st.info("💡 Seleccione un ID de la lista o escríbalo para habilitar Edición o Eliminación.")

    # --- BOTONES DE ACCIÓN ---
    c_b1, c_b2, c_b3 = st.columns(3)
    
    with c_b1:
        if st.button("✏️ Editar Registro", use_container_width=True, disabled=proceso_activo or not id_existe):
            st.session_state.edit_id = int(id_seleccionado)
            st.rerun()
            
    with c_b2:
        if st.button("🗑️ Eliminar Registro", use_container_width=True, disabled=proceso_activo or not id_existe):
            supabase.table("empleados").delete().eq("EmployeeNumber", int(id_seleccionado)).execute()
            st.success(f"Empleado {id_seleccionado} eliminado correctamente.")
            st.rerun()
            
    with c_b3:
        if st.button("➕ Nuevo Registro", use_container_width=True, disabled=proceso_activo):
            st.session_state.show_add = True
            st.rerun()

    # --- FORMULARIO DINÁMICO ---
    if proceso_activo:
        st.divider()
        es_edit = st.session_state.edit_id is not None
        p = {}
        if es_edit:
            p = next((e for e in raw_data if e['employeenumber'] == st.session_state.edit_id), {})

        st.subheader("📋 Formulario: " + ("Modificar Colaborador" if es_edit else "Nuevo Registro"))
        
        with st.form("main_form"):
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                age = st.number_input("Edad", 18, 100, int(p.get('age', 25)), disabled=es_edit)
            with f2:
                income = st.number_input("Sueldo Mensual", 0, 50000, int(p.get('monthlyincome', 3000)))
            with f3:
                # Lógica para pre-seleccionar el departamento actual en edición
                val_depto = MAPEO_DEPTOS.get(p.get('department'), list(MAPEO_DEPTOS.values())[0])
                dept = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()), index=list(MAPEO_DEPTOS.values()).index(val_depto))
            with f4:
                val_role = MAPEO_ROLES.get(p.get('jobrole'), list(MAPEO_ROLES.values())[0])
                role = st.selectbox("Puesto", list(MAPEO_ROLES.values()), index=list(MAPEO_ROLES.values()).index(val_role))

            st.markdown("---")
            # Agregamos algunos campos extra en el form para aprovechar el espacio
            s1, s2, s3, s4 = st.columns(4)
            with s1: env_sat = st.slider("Satisfacción Entorno", 1, 4, int(p.get('environmentsatisfaction', 3)))
            with s2: job_sat = st.slider("Satisfacción Trabajo", 1, 4, int(p.get('jobsatisfaction', 3)))
            with s3: y_total = st.number_input("Años Exp. Total", 0, 50, int(p.get('totalworkingyears', 5)))
            with s4: y_comp = st.number_input("Años en Empresa", 0, 50, int(p.get('yearsatcompany', 0)))

            save_btn = st.form_submit_button("💾 FINALIZAR Y GUARDAR")
            
            if save_btn:
                def to_eng(d, v): return [k for k, val in d.items() if val == v][0]
                payload = {
                    "Age": age, "MonthlyIncome": income, 
                    "Department": to_eng(MAPEO_DEPTOS, dept),
                    "JobRole": to_eng(MAPEO_ROLES, role), 
                    "EnvironmentSatisfaction": env_sat,
                    "JobSatisfaction": job_sat,
                    "TotalWorkingYears": y_total,
                    "YearsAtCompany": y_comp
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

        if st.button("❌ Cancelar"):
            st.session_state.edit_id = None
            st.session_state.show_add = False
            st.rerun()

if __name__ == "__main__":
    render_employee_management_page()











