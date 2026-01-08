import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS
# =================================================================

MAPEO_DEPTOS = {"Sales": "Ventas", "Research & Development": "Investigación y Desarrollo", "Human Resources": "Recursos Humanos"}
MAPEO_EDUCACION = {"Life Sciences": "Ciencias de la Vida", "Other": "Otros", "Medical": "Médico", "Marketing": "Marketing", "Technical Degree": "Grado Técnico", "Human Resources": "Recursos Humanos"}
MAPEO_ROLES = {
    "Sales Executive": "Ejecutivo de Ventas", "Research Scientist": "Científico de Investigación",
    "Laboratory Technician": "Técnico de Laboratorio", "Manufacturing Director": "Director de Manufactura",
    "Healthcare Representative": "Representante de Salud", "Manager": "Gerente",
    "Sales Representative": "Representante de Ventas", "Research Director": "Director de Investigación",
    "Human Resources": "Recursos Humanos"
}
MAPEO_VIAJES = {"Non-Travel": "Sin Viajes", "Travel_Rarely": "Viaja Poco", "Travel_Frequently": "Viaja Frecuentemente"}
MAPEO_ESTADO_CIVIL = {"Single": "Soltero/a", "Married": "Casado/a", "Divorced": "Divorciado/a"}
MAPEO_GENERO = {"Male": "Masculino", "Female": "Femenino"}

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key)

supabase = get_supabase()

@st.cache_data(ttl=2)
def fetch_employees_fast():
    """
    CORRECCIÓN CRÍTICA: Se usa .range() para saltar el límite por defecto de Supabase
    y asegurar que IDs altos como el 2069 sean consultados.
    """
    res = supabase.table("empleados").select("*").range(0, 4000).order("EmployeeNumber").execute()
    return res.data

def get_next_employee_number():
    try:
        res = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
        if res.data:
            return int(res.data[0]['EmployeeNumber']) + 1
        return 1
    except:
        return 1

def to_eng(mapeo, valor_esp):
    try:
        return [k for k, v in mapeo.items() if v == valor_esp][0]
    except:
        return valor_esp

# =================================================================
# 2. INTERFAZ DE USUARIO
# =================================================================

def render_employee_management_page():
    st.title("👥 Gestión de Personal")

    if "edit_id" not in st.session_state: st.session_state.edit_id = None
    if "show_add" not in st.session_state: st.session_state.show_add = False

    proceso_activo = st.session_state.edit_id is not None or st.session_state.show_add
    raw_data = fetch_employees_fast()

    # --- TABLA DE LISTADO ---
    if raw_data:
        activos_df = [e for e in raw_data if not e.get('FechaSalida')]
        if activos_df:
            df_view = pd.DataFrame(activos_df)
            st.subheader("Colaboradores Activos")
            cols_viz = {"EmployeeNumber": "ID", "Age": "Edad", "Department": "Depto", "JobRole": "Puesto", "MonthlyIncome": "Sueldo"}
            df_view['Department'] = df_view['Department'].replace(MAPEO_DEPTOS)
            df_view['JobRole'] = df_view['JobRole'].replace(MAPEO_ROLES)
            st.dataframe(df_view.rename(columns=cols_viz)[list(cols_viz.values())], use_container_width=True, hide_index=True)

    st.divider()

    # --- BUSCADOR CORREGIDO PARA 2069 ---
    st.subheader("🔍 Localizar Colaborador")
    # Forzamos que el ID sea el EmployeeNumber real
    lista_ids = sorted([str(e['EmployeeNumber']) for e in raw_data], key=int, reverse=True)
    id_sel = st.selectbox("Escriba el ID de Empleado (EmployeeNumber):", [None] + lista_ids, disabled=proceso_activo)
    
    c_b1, c_b2, c_b3 = st.columns(3)
    with c_b1:
        if st.button("✏️ Editar", use_container_width=True, disabled=proceso_activo or not id_sel):
            st.session_state.edit_id = int(id_sel)
            st.rerun()
    with c_b2:
        if st.button("🗑️ Eliminar", use_container_width=True, disabled=proceso_activo or not id_sel):
            supabase.table("empleados").delete().eq("EmployeeNumber", int(id_sel)).execute()
            st.cache_data.clear()
            st.rerun()
    with c_b3:
        if st.button("➕ Nuevo Registro", use_container_width=True, disabled=proceso_activo, type="primary"):
            st.session_state.show_add = True
            st.rerun()

    # --- FORMULARIO CON VALIDACIÓN DE EDAD ---
    if proceso_activo:
        st.divider()
        es_edit = st.session_state.edit_id is not None
        p = next((e for e in raw_data if int(e['EmployeeNumber']) == st.session_state.edit_id), {}) if es_edit else {}
        current_id = st.session_state.edit_id if es_edit else get_next_employee_number()

        st.subheader(f"📋 Ficha: ID {current_id}")
        
        # Validación de Edad (Restricción implementada)
        age = st.number_input("Edad", 0, 100, int(p.get('Age', 25)), disabled=es_edit)
        permitir_guardar = age >= 18
        if not permitir_guardar:
            st.error("🚫 La edad debe ser mayor o igual a 18 años para registrar un nuevo empleado.")

        with st.form("main_form_full"):
            st.write("### 💼 Información Laboral y Perfil")
            f1, f2, f3 = st.columns(3)
            with f1:
                income = st.number_input("Sueldo Mensual", 0, 100000, int(p.get('MonthlyIncome', 2000)))
                dept = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()), index=list(MAPEO_DEPTOS.values()).index(MAPEO_DEPTOS.get(p.get('Department'), "Ventas")))
                gen_esp = MAPEO_GENERO.get(p.get('Gender'), "Masculino")
                gender = st.selectbox("Género", list(MAPEO_GENERO.values()), index=list(MAPEO_GENERO.values()).index(gen_esp), disabled=es_edit)
            with f2:
                role = st.selectbox("Puesto", list(MAPEO_ROLES.values()), index=list(MAPEO_ROLES.values()).index(MAPEO_ROLES.get(p.get('JobRole'), "Ejecutivo de Ventas")))
                contract = st.selectbox("Contrato", ["Tiempo Completo", "Indefinido", "Temporal"], index=0)
                civil = st.selectbox("Estado Civil", list(MAPEO_ESTADO_CIVIL.values()), index=list(MAPEO_ESTADO_CIVIL.values()).index(MAPEO_ESTADO_CIVIL.get(p.get('MaritalStatus'), "Soltero/a")))
            with f3:
                overtime = st.selectbox("Horas Extra", ["No", "Yes"], index=0 if p.get('OverTime')=="No" else 1)
                dist = st.number_input("Distancia Casa (km)", 0, 200, int(p.get('DistanceFromHome', 5)))
                travel = st.selectbox("Viajes", list(MAPEO_VIAJES.values()), index=list(MAPEO_VIAJES.values()).index(MAPEO_VIAJES.get(p.get('BusinessTravel'), "Sin Viajes")))

            st.write("### 🎓 Educación y Trayectoria")
            e1, e2, e3 = st.columns(3)
            with e1:
                ed_field = st.selectbox("Campo Estudio", list(MAPEO_EDUCACION.values()), index=list(MAPEO_EDUCACION.values()).index(MAPEO_EDUCACION.get(p.get('EducationField'), "Otros")), disabled=es_edit)
                y_tot = st.number_input("Años Exp Total", 0, 50, int(p.get('TotalWorkingYears', 1)))
            with e2:
                ed_lvl = st.number_input("Nivel Educación", 1, 5, int(p.get('Education', 3)), disabled=es_edit)
                y_com = st.number_input("Años en Empresa", 0, 50, int(p.get('YearsAtCompany', 1)))
            with e3:
                job_lvl = st.number_input("Nivel Puesto", 1, 5, int(p.get('JobLevel', 1)))
                n_com = st.number_input("Empresas Previas", 0, 15, int(p.get('NumCompaniesWorked', 0)))

            st.write("### 📅 Fechas y Asistencia")
            d1, d2, d3 = st.columns(3)
            with d1:
                f_ing = st.date_input("Fecha Ingreso", date.fromisoformat(p['FechaIngreso']) if p.get('FechaIngreso') else date.today())
                tardanzas = st.number_input("N° Tardanzas", 0, 1000, int(p.get('NumeroTardanzas', 0)))
            with d2:
                f_sal_val = p.get('FechaSalida')
                dar_baja = st.checkbox("Registrar Salida", value=True if f_sal_val else False)
                f_sal = st.date_input("Fecha Salida", date.fromisoformat(f_sal_val) if f_sal_val else date.today(), disabled=not dar_baja)
                faltas = st.number_input("N° Faltas", 0, 1000, int(p.get('NumeroFaltas', 0)))
            with d3:
                perf = st.slider("Rating Desempeño", 1, 4, int(p.get('PerformanceRating', 3)))

            if st.form_submit_button("💾 GUARDAR", use_container_width=True, type="primary", disabled=not permitir_guardar):
                payload = {
                    "EmployeeNumber": current_id, "Age": age, "Gender": to_eng(MAPEO_GENERO, gender),
                    "MonthlyIncome": income, "Department": to_eng(MAPEO_DEPTOS, dept), "JobRole": to_eng(MAPEO_ROLES, role),
                    "BusinessTravel": to_eng(MAPEO_VIAJES, travel), "EducationField": to_eng(MAPEO_EDUCACION, ed_field),
                    "Education": ed_lvl, "MaritalStatus": to_eng(MAPEO_ESTADO_CIVIL, civil), "DistanceFromHome": dist,
                    "JobLevel": job_lvl, "OverTime": overtime, "TotalWorkingYears": y_tot, "YearsAtCompany": y_com,
                    "NumCompaniesWorked": n_com, "PerformanceRating": perf,
                    "NumeroTardanzas": tardanzas, "NumeroFaltas": faltas, "Tipocontrato": contract,
                    "FechaIngreso": f_ing.isoformat(), "FechaSalida": f_sal.isoformat() if dar_baja else None
                }
                
                if es_edit:
                    supabase.table("empleados").update(payload).eq("EmployeeNumber", current_id).execute()
                else:
                    supabase.table("empleados").insert(payload).execute()
                
                st.session_state.edit_id = None
                st.session_state.show_add = False
                st.cache_data.clear()
                st.rerun()

        if st.button("❌ Cancelar"):
            st.session_state.edit_id = None
            st.session_state.show_add = False
            st.rerun()

if __name__ == "__main__":
    render_employee_management_page()










