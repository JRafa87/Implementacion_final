import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS (ESPAÑOL MANTENIDO)
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

@st.cache_data(ttl=5)
def fetch_employees_fast():
    """Trae todos los registros. El límite de 5000 asegura ver IDs altos como 2069."""
    res = supabase.table("empleados").select("*").order("EmployeeNumber").limit(5000).execute()
    return res.data

@st.cache_data(ttl=600)
def get_tipos_contrato():
    try:
        res = supabase.table("empleados").select("Tipocontrato").execute()
        if res.data:
            return sorted(list(set([r['Tipocontrato'] for r in res.data if r.get('Tipocontrato')])))
    except:
        pass
    return ["Tiempo Completo", "Indefinido", "Temporal"]

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
    tipos_contrato = get_tipos_contrato()

    # --- TABLA DE LISTADO (SOLO ACTIVOS) ---
    if raw_data:
        activos_df = [e for e in raw_data if not e.get('FechaSalida')]
        if activos_df:
            df_view = pd.DataFrame(activos_df)
            st.subheader("Colaboradores Activos")
            cols_viz = {"EmployeeNumber": "ID", "Age": "Edad", "Department": "Depto", "JobRole": "Puesto", "MonthlyIncome": "Sueldo", "Tipocontrato": "Contrato"}
            df_view['Department'] = df_view['Department'].replace(MAPEO_DEPTOS)
            df_view['JobRole'] = df_view['JobRole'].replace(MAPEO_ROLES)
            st.dataframe(df_view.rename(columns=cols_viz)[list(cols_viz.values())], use_container_width=True, hide_index=True)

    st.divider()

    # --- BUSCADOR (ORDENADO PARA VER ÚLTIMOS IDS PRIMERO) ---
    st.subheader("🔍 Localizar Colaborador")
    lista_ids = sorted([str(e['EmployeeNumber']) for e in raw_data], key=int, reverse=True)
    id_sel = st.selectbox("Seleccione ID (Los nuevos aparecen primero):", [None] + lista_ids, disabled=proceso_activo)
    
    c_b1, c_b2, c_b3 = st.columns(3)
    with c_b1:
        if st.button("✏️ Editar Datos", use_container_width=True, disabled=proceso_activo or not id_sel):
            st.session_state.edit_id = int(id_sel)
            st.rerun()
    with c_b2:
        if st.button("🗑️ Eliminar Registro", use_container_width=True, disabled=proceso_activo or not id_sel):
            supabase.table("empleados").delete().eq("EmployeeNumber", int(id_sel)).execute()
            st.cache_data.clear()
            st.rerun()
    with c_b3:
        if st.button("➕ Nuevo Registro", use_container_width=True, disabled=proceso_activo, type="primary"):
            st.session_state.show_add = True
            st.rerun()

    # --- FORMULARIO INTEGRAL RESTAURADO ---
    if proceso_activo:
        st.divider()
        es_edit = st.session_state.edit_id is not None
        # Búsqueda numérica exacta
        p = next((e for e in raw_data if int(e['EmployeeNumber']) == st.session_state.edit_id), {}) if es_edit else {}
        current_id = st.session_state.edit_id if es_edit else get_next_employee_number()

        st.subheader(f"📋 Ficha de Datos: ID {current_id}")
        
        # Fila de control superior (Edad y Género tienen restricciones de edición)
        c_top1, c_top2 = st.columns(2)
        with c_top1:
            age = st.number_input("Edad", 18, 100, int(p.get('Age', 25)), disabled=es_edit)
        with c_top2:
            gen_esp = MAPEO_GENERO.get(p.get('Gender'), "Masculino")
            gender = st.selectbox("Género", list(MAPEO_GENERO.values()), index=list(MAPEO_GENERO.values()).index(gen_esp), disabled=es_edit)

        with st.form("full_employee_form"):
            st.write("### 💼 Información Laboral")
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                income = st.number_input("Sueldo Mensual", 0, 100000, int(p.get('MonthlyIncome', 2000)))
                contract = st.selectbox("Contrato", tipos_contrato, index=tipos_contrato.index(p['Tipocontrato']) if p.get('Tipocontrato') in tipos_contrato else 0)
            with f2:
                dept = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()), index=list(MAPEO_DEPTOS.values()).index(MAPEO_DEPTOS.get(p.get('Department'), "Ventas")))
                role = st.selectbox("Puesto", list(MAPEO_ROLES.values()), index=list(MAPEO_ROLES.values()).index(MAPEO_ROLES.get(p.get('JobRole'), "Ejecutivo de Ventas")))
            with f3:
                travel = st.selectbox("Viajes", list(MAPEO_VIAJES.values()), index=list(MAPEO_VIAJES.values()).index(MAPEO_VIAJES.get(p.get('BusinessTravel'), "Sin Viajes")))
                job_lvl = st.number_input("Nivel Puesto (1-5)", 1, 5, int(p.get('JobLevel', 1)))
            with f4:
                overtime = st.selectbox("Horas Extra", ["No", "Yes"], index=0 if p.get('OverTime')=="No" else 1)
                stock = st.number_input("Nivel Acciones", 0, 3, int(p.get('StockOptionLevel', 0)))

            st.write("### 🎓 Educación y Perfil")
            e1, e2, e3, e4 = st.columns(4)
            with e1:
                ed_field = st.selectbox("Campo Estudio", list(MAPEO_EDUCACION.values()), index=list(MAPEO_EDUCACION.values()).index(MAPEO_EDUCACION.get(p.get('EducationField'), "Otros")), disabled=es_edit)
            with e2:
                ed_lvl = st.number_input("Nivel Educación", 1, 5, int(p.get('Education', 3)), disabled=es_edit)
            with e3:
                civil = st.selectbox("Estado Civil", list(MAPEO_ESTADO_CIVIL.values()), index=list(MAPEO_ESTADO_CIVIL.values()).index(MAPEO_ESTADO_CIVIL.get(p.get('MaritalStatus'), "Soltero/a")))
            with e4:
                dist = st.number_input("Distancia Casa (km)", 0, 200, int(p.get('DistanceFromHome', 5)))

            st.write("### 📈 Trayectoria y Asistencia")
            t1, t2, t3, t4 = st.columns(4)
            with t1:
                y_tot = st.number_input("Años Exp Total", 0, 50, int(p.get('TotalWorkingYears', 1)))
                y_com = st.number_input("Años en Empresa", 0, 50, int(p.get('YearsAtCompany', 1)))
            with t2:
                y_rol = st.number_input("Años Cargo Actual", 0, 50, int(p.get('YearsInCurrentRole', 1)))
                y_prm = st.number_input("Años Últ. Ascenso", 0, 50, int(p.get('YearsSinceLastPromotion', 0)))
            with t3:
                y_mgr = st.number_input("Años con Jefe", 0, 50, int(p.get('YearsWithCurrManager', 1)))
                train = st.number_input("Capacitaciones", 0, 20, int(p.get('TrainingTimesLastYear', 0)))
            with t4:
                n_com = st.number_input("Empresas Previas", 0, 15, int(p.get('NumCompaniesWorked', 0)))
                perf = st.slider("Rating Desempeño", 1, 4, int(p.get('PerformanceRating', 3)))

            st.write("### 📅 Fechas y Asistencia")
            d1, d2, d3 = st.columns(3)
            with d1:
                tardanzas = st.number_input("N° Tardanzas", 0, 1000, int(p.get('NumeroTardanzas', 0)))
                faltas = st.number_input("N° Faltas", 0, 1000, int(p.get('NumeroFaltas', 0)))
            with d2:
                f_ing = st.date_input("Fecha Ingreso", date.fromisoformat(p['FechaIngreso']) if p.get('FechaIngreso') else date.today())
            with d3:
                f_sal_val = p.get('FechaSalida')
                dar_baja = st.checkbox("Registrar Fecha Salida", value=True if f_sal_val else False)
                f_sal = st.date_input("Fecha Salida", date.fromisoformat(f_sal_val) if f_sal_val else date.today(), disabled=not dar_baja)

            if st.form_submit_button("💾 GUARDAR CAMBIOS", use_container_width=True, type="primary"):
                payload = {
                    "EmployeeNumber": current_id, "Age": age, "Gender": to_eng(MAPEO_GENERO, gender),
                    "MonthlyIncome": income, "Department": to_eng(MAPEO_DEPTOS, dept), "JobRole": to_eng(MAPEO_ROLES, role),
                    "BusinessTravel": to_eng(MAPEO_VIAJES, travel), "EducationField": to_eng(MAPEO_EDUCACION, ed_field),
                    "Education": ed_lvl, "MaritalStatus": to_eng(MAPEO_ESTADO_CIVIL, civil), "DistanceFromHome": dist,
                    "JobLevel": job_lvl, "OverTime": overtime, "TotalWorkingYears": y_tot, "YearsAtCompany": y_com,
                    "YearsInCurrentRole": y_rol, "YearsSinceLastPromotion": y_prm, "YearsWithCurrManager": y_mgr,
                    "TrainingTimesLastYear": train, "NumCompaniesWorked": n_com, "PerformanceRating": perf,
                    "NumeroTardanzas": tardanzas, "NumeroFaltas": faltas, "Tipocontrato": contract, "StockOptionLevel": stock,
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










