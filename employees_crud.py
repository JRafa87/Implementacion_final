import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS (INTERFAZ EN ESPAÑOL)
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

@st.cache_data(ttl=10)
def fetch_employees_fast():
    """Trae todos los registros. Se usa limit(5000) para asegurar que IDs como 2069 aparezcan."""
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

    # Estados de sesión
    if "edit_id" not in st.session_state: st.session_state.edit_id = None
    if "show_add" not in st.session_state: st.session_state.show_add = False

    proceso_activo = st.session_state.edit_id is not None or st.session_state.show_add
    raw_data = fetch_employees_fast()
    tipos_contrato = get_tipos_contrato()

    # --- TABLA DE LISTADO (SOLO ACTIVOS) ---
    if raw_data:
        # Filtrar solo activos para la tabla principal
        activos_df = [e for e in raw_data if not e.get('FechaSalida')]
        if activos_df:
            df_view = pd.DataFrame(activos_df)
            st.subheader("Colaboradores Activos")
            
            cols_viz = {
                "EmployeeNumber": "ID", "Age": "Edad", "Department": "Depto", 
                "JobRole": "Puesto", "MonthlyIncome": "Sueldo", "Tipocontrato": "Contrato"
            }
            
            df_view['Department'] = df_view['Department'].replace(MAPEO_DEPTOS)
            df_view['JobRole'] = df_view['JobRole'].replace(MAPEO_ROLES)
            
            st.dataframe(
                df_view.rename(columns=cols_viz)[list(cols_viz.values())], 
                use_container_width=True, 
                hide_index=True
            )

    st.divider()

    # --- BUSCADOR (ENCUENTRA HASTA EL ÚLTIMO ID) ---
    st.subheader("🔍 Localizar Colaborador")
    
    # Generamos la lista de IDs de todos (activos e inactivos) para poder editar cualquiera
    lista_ids = sorted([str(e['EmployeeNumber']) for e in raw_data], key=int, reverse=True)
    
    id_sel = st.selectbox("Escriba o seleccione ID:", [None] + lista_ids, disabled=proceso_activo)
    
    c_b1, c_b2, c_b3 = st.columns(3)
    with c_b1:
        if st.button("✏️ Editar", use_container_width=True, disabled=proceso_activo or not id_sel):
            st.session_state.edit_id = int(id_sel)
            st.rerun()
    with c_b2:
        if st.button("🗑️ Eliminar", use_container_width=True, disabled=proceso_activo or not id_sel):
            # El trigger en DB se encargará de actualizar el consolidado automáticamente
            supabase.table("empleados").delete().eq("EmployeeNumber", int(id_sel)).execute()
            st.cache_data.clear()
            st.rerun()
    with c_b3:
        if st.button("➕ Nuevo Registro", use_container_width=True, disabled=proceso_activo, type="primary"):
            st.session_state.show_add = True
            st.rerun()

    # --- FORMULARIO DE DATOS ---
    if proceso_activo:
        st.divider()
        es_edit = st.session_state.edit_id is not None
        # Búsqueda del registro para editar (uso de int() para asegurar coincidencia)
        p = next((e for e in raw_data if int(e['EmployeeNumber']) == st.session_state.edit_id), {}) if es_edit else {}
        current_id = st.session_state.edit_id if es_edit else get_next_employee_number()

        st.subheader("📋 Formulario" + (f" (ID: {current_id})" if es_edit else " (Nuevo)"))
        
        with st.form("main_form"):
            # Fila 1: Datos Personales
            c1, c2, c3 = st.columns(3)
            with c1:
                age = st.number_input("Edad", 18, 100, int(p.get('Age', 25)))
                gen_esp = MAPEO_GENERO.get(p.get('Gender'), "Masculino")
                gender = st.selectbox("Género", list(MAPEO_GENERO.values()), index=list(MAPEO_GENERO.values()).index(gen_esp))
            with c2:
                civ_esp = MAPEO_ESTADO_CIVIL.get(p.get('MaritalStatus'), "Soltero/a")
                civil = st.selectbox("Estado Civil", list(MAPEO_ESTADO_CIVIL.values()), index=list(MAPEO_ESTADO_CIVIL.values()).index(civ_esp))
                dist = st.number_input("Distancia Casa (km)", 0, 200, int(p.get('DistanceFromHome', 5)))
            with c3:
                income = st.number_input("Sueldo Mensual", 0, 50000, int(p.get('MonthlyIncome', 1500)))
                overtime = st.selectbox("Horas Extra", ["No", "Yes"], index=0 if p.get('OverTime')=="No" else 1)

            st.markdown("---")
            # Fila 2: Datos Laborales
            f1, f2, f3 = st.columns(3)
            with f1:
                dept_esp = MAPEO_DEPTOS.get(p.get('Department'), "Ventas")
                dept = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()), index=list(MAPEO_DEPTOS.values()).index(dept_esp))
                role_esp = MAPEO_ROLES.get(p.get('JobRole'), "Ejecutivo de Ventas")
                role = st.selectbox("Puesto", list(MAPEO_ROLES.values()), index=list(MAPEO_ROLES.values()).index(role_esp))
            with f2:
                contract = st.selectbox("Contrato", tipos_contrato, index=tipos_contrato.index(p['Tipocontrato']) if p.get('Tipocontrato') in tipos_contrato else 0)
                perf = st.slider("Rating Desempeño", 1, 4, int(p.get('PerformanceRating', 3)))
            with f3:
                f_ing_val = p.get('FechaIngreso')
                f_ing = st.date_input("Fecha Ingreso", date.fromisoformat(f_ing_val) if f_ing_val else date.today())
                f_sal_val = p.get('FechaSalida')
                dar_baja = st.checkbox("Registrar Salida", value=True if f_sal_val else False)
                f_sal = st.date_input("Fecha Salida", date.fromisoformat(f_sal_val) if f_sal_val else date.today(), disabled=not dar_baja)

            # Botón Guardar
            if st.form_submit_button("💾 GUARDAR", use_container_width=True, type="primary"):
                payload = {
                    "EmployeeNumber": current_id,
                    "Age": age, "Gender": to_eng(MAPEO_GENERO, gender),
                    "MonthlyIncome": income, "Department": to_eng(MAPEO_DEPTOS, dept),
                    "JobRole": to_eng(MAPEO_ROLES, role), "OverTime": overtime,
                    "MaritalStatus": to_eng(MAPEO_ESTADO_CIVIL, civil),
                    "DistanceFromHome": dist, "Tipocontrato": contract,
                    "PerformanceRating": perf, "FechaIngreso": f_ing.isoformat(),
                    "FechaSalida": f_sal.isoformat() if dar_baja else None
                }
                
                if es_edit:
                    supabase.table("empleados").update(payload).eq("EmployeeNumber", current_id).execute()
                else:
                    # En insert, nos aseguramos de no duplicar si el trigger no ha limpiado
                    supabase.table("empleados").insert(payload).execute()
                
                st.session_state.edit_id = None
                st.session_state.show_add = False
                st.cache_data.clear()
                st.success("¡Datos sincronizados correctamente!")
                st.rerun()

        if st.button("❌ Cancelar"):
            st.session_state.edit_id = None
            st.session_state.show_add = False
            st.rerun()

if __name__ == "__main__":
    render_employee_management_page()











