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
    SOLUCIÓN AL LÍMITE DE 1000:
    Usamos .range(0, 4999) para pedir explícitamente los primeros 5000 registros.
    Esto rompe el bloqueo de los 1000 registros por defecto de la API.
    """
    res = supabase.table("empleados").select("*").range(0, 4999).order("EmployeeNumber", desc=True).execute()
    return res.data

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
    
    # Obtenemos los datos con el rango ampliado (hasta 5000)
    raw_data = fetch_employees_fast()

    # --- TABLA DE ACTIVOS ---
    if raw_data:
        activos_df = [e for e in raw_data if not e.get('FechaSalida')]
        if activos_df:
            df_view = pd.DataFrame(activos_df)
            st.subheader("Listado de Personal")
            cols_viz = {"EmployeeNumber": "ID", "Age": "Edad", "Department": "Depto", "JobRole": "Puesto", "MonthlyIncome": "Sueldo"}
            
            # Formateo para visualización
            df_view['Department'] = df_view['Department'].replace(MAPEO_DEPTOS)
            df_view['JobRole'] = df_view['JobRole'].replace(MAPEO_ROLES)
            
            st.dataframe(df_view.rename(columns=cols_viz)[list(cols_viz.values())], use_container_width=True, hide_index=True)

    st.divider()

    # --- BUSCADOR CORREGIDO (MUESTRA 2069, 2070, ETC.) ---
    st.subheader("🔍 Localizar Colaborador")
    # Al estar ordenados por desc=True, el 2070 aparecerá de los primeros
    lista_ids = [str(e['EmployeeNumber']) for e in raw_data]
    id_sel = st.selectbox("Buscar por ID de Empleado:", [None] + lista_ids, disabled=proceso_activo)
    
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

    # --- FORMULARIO CON TODAS LAS RESTRICCIONES ---
    if proceso_activo:
        st.divider()
        es_edit = st.session_state.edit_id is not None
        
        # Búsqueda exacta del registro seleccionado
        p = next((e for e in raw_data if int(e['EmployeeNumber']) == st.session_state.edit_id), {}) if es_edit else {}
        
        # Generar ID siguiente si es nuevo
        if not es_edit:
            try:
                current_id = int(lista_ids[0]) + 1 if lista_ids else 1
            except:
                current_id = 1
        else:
            current_id = st.session_state.edit_id

        st.subheader(f"📋 Ficha: ID {current_id}")
        
        # --- RESTRICCIÓN DE EDAD (MÍNIMO 18) ---
        age = st.number_input("Edad", 0, 100, int(p.get('Age', 25)), disabled=es_edit)
        permitir_registro = age >= 18
        
        if not permitir_registro:
            st.error("🚫 Validación: El trabajador debe ser mayor de 18 años.")

        with st.form("form_integral"):
            st.write("### 💼 Información del Cargo")
            c1, c2, c3 = st.columns(3)
            with c1:
                income = st.number_input("Sueldo Mensual", 0, 100000, int(p.get('MonthlyIncome', 1500)))
                dept = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()), index=list(MAPEO_DEPTOS.values()).index(MAPEO_DEPTOS.get(p.get('Department'), "Ventas")))
            with c2:
                role = st.selectbox("Puesto", list(MAPEO_ROLES.values()), index=list(MAPEO_ROLES.values()).index(MAPEO_ROLES.get(p.get('JobRole'), "Ejecutivo de Ventas")))
                contract = st.selectbox("Contrato", ["Indefinido", "Tiempo Completo", "Temporal"], index=0)
            with c3:
                travel = st.selectbox("Viajes", list(MAPEO_VIAJES.values()), index=list(MAPEO_VIAJES.values()).index(MAPEO_VIAJES.get(p.get('BusinessTravel'), "Sin Viajes")))
                overtime = st.selectbox("Horas Extra", ["No", "Yes"], index=0 if p.get('OverTime')=="No" else 1)

            st.write("### 🎓 Educación y Personal")
            e1, e2, e3 = st.columns(3)
            with e1:
                gen_esp = MAPEO_GENERO.get(p.get('Gender'), "Masculino")
                gender = st.selectbox("Género", list(MAPEO_GENERO.values()), index=list(MAPEO_GENERO.values()).index(gen_esp), disabled=es_edit)
            with e2:
                civil = st.selectbox("Estado Civil", list(MAPEO_ESTADO_CIVIL.values()), index=list(MAPEO_ESTADO_CIVIL.values()).index(MAPEO_ESTADO_CIVIL.get(p.get('MaritalStatus'), "Soltero/a")))
            with e3:
                dist = st.number_input("Distancia Casa (km)", 0, 200, int(p.get('DistanceFromHome', 5)))

            st.write("### 📈 Trayectoria y Asistencia")
            t1, t2, t3 = st.columns(3)
            with t1:
                y_com = st.number_input("Años en Empresa", 0, 50, int(p.get('YearsAtCompany', 0)))
                tardanzas = st.number_input("N° Tardanzas", 0, 1000, int(p.get('NumeroTardanzas', 0)))
            with t2:
                y_tot = st.number_input("Años Exp. Total", 0, 50, int(p.get('TotalWorkingYears', 0)))
                faltas = st.number_input("N° Faltas", 0, 1000, int(p.get('NumeroFaltas', 0)))
            with t3:
                perf = st.slider("Rating Desempeño", 1, 4, int(p.get('PerformanceRating', 3)))

            st.write("### 📅 Fechas")
            d1, d2 = st.columns(2)
            with d1:
                f_ing = st.date_input("Fecha Ingreso", date.fromisoformat(p['FechaIngreso']) if p.get('FechaIngreso') else date.today())
            with d2:
                f_sal_val = p.get('FechaSalida')
                dar_baja = st.checkbox("Registrar Salida", value=True if f_sal_val else False)
                f_sal = st.date_input("Fecha Salida", date.fromisoformat(f_sal_val) if f_sal_val else date.today(), disabled=not dar_baja)

            # Botón de Guardado
            if st.form_submit_button("💾 GUARDAR", use_container_width=True, type="primary", disabled=not permitir_registro):
                payload = {
                    "EmployeeNumber": current_id, "Age": age, "Gender": to_eng(MAPEO_GENERO, gender),
                    "MonthlyIncome": income, "Department": to_eng(MAPEO_DEPTOS, dept), "JobRole": to_eng(MAPEO_ROLES, role),
                    "BusinessTravel": to_eng(MAPEO_VIAJES, travel), "MaritalStatus": to_eng(MAPEO_ESTADO_CIVIL, civil),
                    "DistanceFromHome": dist, "OverTime": overtime, "YearsAtCompany": y_com, "TotalWorkingYears": y_tot,
                    "NumeroTardanzas": tardanzas, "NumeroFaltas": faltas, "PerformanceRating": perf,
                    "Tipocontrato": contract, "FechaIngreso": f_ing.isoformat(), 
                    "FechaSalida": f_sal.isoformat() if dar_baja else None
                }
                
                if es_edit:
                    supabase.table("empleados").update(payload).eq("EmployeeNumber", current_id).execute()
                else:
                    supabase.table("empleados").insert(payload).execute()
                
                st.cache_data.clear()
                st.session_state.edit_id = None
                st.session_state.show_add = False
                st.success(f"ID {current_id} sincronizado.")
                st.rerun()

        if st.button("❌ Cancelar"):
            st.session_state.edit_id = None
            st.session_state.show_add = False
            st.rerun()

if __name__ == "__main__":
    render_employee_management_page()










