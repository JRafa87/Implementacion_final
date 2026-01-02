import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. DICCIONARIOS DE TRADUCCIÓN Y MAPEO
# =================================================================

MAPEO_DEPTOS = {
    "Sales": "Ventas", 
    "Research & Development": "I+D / Desarrollo", 
    "Human Resources": "Recursos Humanos"
}

TRADUCCIONES_TABLA = {
    "businesstravel": {"Non-Travel": "No viaja", "Travel_Rarely": "Viaja raramente", "Travel_Frequently": "Viaja frecuentemente"},
    "gender": {"Male": "Masculino", "Female": "Femenino"},
    "maritalstatus": {"Single": "Soltero/a", "Married": "Casado/a", "Divorced": "Divorciado/a"},
    "educationfield": {"Life Sciences": "Ciencias de la Vida", "Other": "Otros", "Medical": "Médico", "Marketing": "Marketing", "Technical Degree": "Grado Técnico", "Human Resources": "Recursos Humanos"}
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

    # --- TABLA TRADUCIDA VISUALMENTE ---
    raw_data = fetch_employees()
    if raw_data:
        df = pd.DataFrame(raw_data)
        # Traducción forzada de cada celda para la vista
        df['department'] = df['department'].replace(MAPEO_DEPTOS)
        for col, mapa in TRADUCCIONES_TABLA.items():
            if col in df.columns:
                df[col] = df[col].replace(mapa)
        
        st.subheader("Listado General de Personal")
        # Mostrar todas las columnas con nombres en español
        st.dataframe(df.rename(columns={
            "employeenumber": "ID", "age": "Edad", "department": "Depto", "jobrole": "Puesto", 
            "monthlyincome": "Sueldo", "businesstravel": "Viajes", "educationfield": "Educación"
        }), use_container_width=True, hide_index=True)

    st.divider()

    # --- BUSCADOR ÚNICO (CAJA DE SELECCIÓN Y BÚSQUEDA) ---
    st.subheader("🔍 Localizar y Gestionar")
    lista_ids = [e['employeenumber'] for e in raw_data] if raw_data else []
    
    # Una sola caja para buscar (escribiendo) o seleccionar
    id_seleccionado = st.selectbox("Escriba el ID o selecciónelo de la lista:", [None] + lista_ids)

    col_acc1, col_acc2, col_acc3 = st.columns(3)
    with col_acc1:
        if st.button("✏️ Editar Registro", use_container_width=True) and id_seleccionado:
            st.session_state.edit_id = id_seleccionado
            st.session_state.show_add = False
            st.rerun()
    with col_acc2:
        if st.button("🗑️ Eliminar Registro", use_container_width=True) and id_seleccionado:
            supabase.table("empleados").delete().eq("EmployeeNumber", id_seleccionado).execute()
            st.rerun()
    with col_acc3:
        if st.button("➕ Nuevo Empleado", use_container_width=True):
            st.session_state.show_add = True
            st.session_state.edit_id = None
            st.rerun()

    # --- FORMULARIO INTEGRAL CON RESTRICCIÓN ---
    if st.session_state.show_add or st.session_state.edit_id:
        st.divider()
        es_edit = st.session_state.edit_id is not None
        p = {}
        if es_edit:
            res_ind = supabase.table("empleados").select("*").eq("EmployeeNumber", st.session_state.edit_id).execute()
            p = {k.lower(): v for k, v in res_ind.data[0].items()} if res_ind.data else {}

        st.subheader("📝 Formulario Detallado")
        
        # El formulario NO tiene botón de submit automático para controlar la edad
        with st.container():
            # FILA 1
            c1, c2, c3 = st.columns(3)
            with c1:
                # RESTRICCIÓN DE EDAD: El campo informa, la lógica bloquea
                age = st.number_input("Edad (Mínimo 18 años)", 0, 100, int(p.get('age', 25)))
                dept = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()), 
                                   index=list(MAPEO_DEPTOS.values()).index(MAPEO_DEPTOS.get(p.get('department'), "Ventas")) if p.get('department') else 0)
            with c2:
                gender = st.selectbox("Género", ["Masculino", "Femenino"], 
                                     index=0 if p.get('gender') == "Male" else 1)
                income = st.number_input("Sueldo Mensual", 0, 50000, int(p.get('monthlyincome', 3000)))
            with c3:
                marital = st.selectbox("Estado Civil", ["Soltero/a", "Casado/a", "Divorciado/a"])
                travel = st.selectbox("Viajes", ["No viaja", "Viaja raramente", "Viaja frecuentemente"])

            # FILA 2: TODOS LOS CAMPOS DE SATISFACCIÓN Y MÉTRICAS
            st.write("**Métricas y Satisfacción**")
            c4, c5, c6 = st.columns(3)
            with c4:
                env_sat = st.slider("Satisfacción Entorno", 1, 4, int(p.get('environmentsatisfaction', 3)))
                job_sat = st.slider("Satisfacción Trabajo", 1, 4, int(p.get('jobsatisfaction', 3)))
            with c5:
                job_inv = st.slider("Involucramiento", 1, 4, int(p.get('jobinvolvement', 3)))
                perf = st.slider("Desempeño", 1, 4, int(p.get('performancerating', 3)))
            with c6:
                job_lvl = st.number_input("Nivel Puesto", 1, 5, int(p.get('joblevel', 1)))
                dist = st.number_input("Distancia Km", 0, 100, int(p.get('distancefromhome', 5)))

            # VALIDACIÓN DE EDAD PARA MOSTRAR BOTÓN
            if age < 18:
                st.error("🚫 BLOQUEADO: No se permiten registros de menores de 18 años.")
                # No se muestra el botón de guardar
            else:
                st.info("✅ Edad válida para registro.")
                if st.button("💾 GUARDAR CAMBIOS"):
                    # Lógica de guardado...
                    def rev(dic, val): return [k for k, v in dic.items() if v == val][0]
                    payload = {
                        "age": age, "monthlyincome": income, "department": rev(MAPEO_DEPTOS, dept),
                        "gender": "Male" if gender == "Masculino" else "Female",
                        "environmentsatisfaction": env_sat, "jobsatisfaction": job_sat,
                        "jobinvolvement": job_inv, "performancerating": perf, "joblevel": job_lvl,
                        "distancefromhome": dist, "businesstravel": "Travel_Rarely" # Ejemplo simplificado
                    }
                    db_ready = {COLUMN_MAPPING[k]: v for k, v in payload.items() if k in COLUMN_MAPPING}
                    
                    if es_edit:
                        supabase.table("empleados").update(db_ready).eq("EmployeeNumber", st.session_state.edit_id).execute()
                    else:
                        l_id = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
                        db_ready["EmployeeNumber"] = (l_id.data[0]['EmployeeNumber'] + 1) if l_id.data else 1
                        supabase.table("empleados").insert(db_ready).execute()
                    
                    st.success("¡Operación exitosa!")
                    st.session_state.edit_id = None
                    st.session_state.show_add = False
                    st.rerun()

        if st.button("❌ Cancelar"):
            st.session_state.edit_id = None
            st.session_state.show_add = False
            st.rerun()

if __name__ == "__main__":
    render_employee_management_page()











