import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS (INGLÉS ORIGINAL <-> ESPAÑOL)
# =================================================================

# Listas exactas solicitadas para traducción y envío
MAPEO_DEPTOS = {
    "Sales": "Ventas", 
    "Research & Development": "I+D / Desarrollo", 
    "Human Resources": "Recursos Humanos"
}

MAPEO_EDUCACION = {
    "Life Sciences": "Ciencias de la Vida", 
    "Other": "Otros", 
    "Medical": "Médico", 
    "Marketing": "Marketing", 
    "Technical Degree": "Grado Técnico", 
    "Human Resources": "Recursos Humanos"
}

MAPEO_ROLES = {
    "Sales Executive": "Ejecutivo de Ventas",
    "Research Scientist": "Científico de Investigación",
    "Laboratory Technician": "Técnico de Laboratorio",
    "Manufacturing Director": "Director de Manufactura",
    "Healthcare Representative": "Representante de Salud",
    "Manager": "Gerente",
    "Sales Representative": "Representante de Ventas",
    "Research Director": "Director de Investigación",
    "Human Resources": "Recursos Humanos"
}

TRADUCCIONES_FIJAS = {
    "businesstravel": {"Non-Travel": "No viaja", "Travel_Rarely": "Viaja raramente", "Travel_Frequently": "Viaja frecuentemente"},
    "gender": {"Male": "Masculino", "Female": "Femenino"},
    "maritalstatus": {"Single": "Soltero/a", "Married": "Casado/a", "Divorced": "Divorciado/a"},
    "overtime": {"Yes": "Sí", "No": "No"}
}

# Mapeo de variables a columnas de PostgreSQL (PascalCase)
COLUMN_MAPPING = {
    "employeenumber": "EmployeeNumber", "age": "Age", "businesstravel": "BusinessTravel",
    "department": "Department", "distancefromhome": "DistanceFromHome", "education": "Education",
    "educationfield": "EducationField", "gender": "Gender", "joblevel": "JobLevel",
    "jobrole": "JobRole", "maritalstatus": "MaritalStatus", "monthlyincome": "MonthlyIncome", 
    "numcompaniesworked": "NumCompaniesWorked", "overtime": "OverTime", "performancerating": "PerformanceRating",
    "totalworkingyears": "TotalWorkingYears", "trainingtimeslastyear": "TrainingTimesLastyear",
    "yearsatcompany": "YearsAtCompany", "yearsincurrentrole": "YearsInCurrentRole",
    "yearssincelastpromotion": "YearsSinceLastPromotion", "yearswithcurrmanager": "YearsWithCurrManager",
    "tipocontrato": "Tipocontrato", "numerotardanzas": "NumeroTardanzas", "numerofaltas": "NumeroFaltas",
    "fechaingreso": "FechaIngreso", "fechasalida": "FechaSalida",
}

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key)

supabase = get_supabase()

# -----------------------------------
# 2. FUNCIONES CRUD
# -----------------------------------

def get_next_id():
    resp = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
    return (resp.data[0]['EmployeeNumber'] + 1) if resp.data else 1

def fetch_employees():
    try:
        response = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
        return [{k.lower(): v for k, v in record.items()} for record in response.data]
    except: return []

# -----------------------------------
# 3. PÁGINA PRINCIPAL
# -----------------------------------

def render_employee_management_page():
    st.title("👥 Gestión Integral de Empleados")

    if "edit_id" not in st.session_state: st.session_state.edit_id = None
    if "show_add" not in st.session_state: st.session_state.show_add = False

    col_nav1, col_nav2 = st.columns([1, 1])
    with col_nav1:
        if st.button("➕ Añadir Nuevo Empleado"):
            st.session_state.show_add = True
            st.session_state.edit_id = None
    with col_nav2:
        if st.button("🔄 Actualizar Tabla"): st.rerun()

    # FORMULARIO COMPLETO
    if st.session_state.show_add or st.session_state.edit_id:
        es_edicion = st.session_state.edit_id is not None
        datos_previos = {}
        if es_edicion:
            res = supabase.table("empleados").select("*").eq("EmployeeNumber", st.session_state.edit_id).single().execute()
            datos_previos = {k.lower(): v for k, v in res.data.items()}

        with st.form("formulario_completo"):
            st.header("Formulario de Datos")
            
            # SECCIÓN 1: DATOS CLAVE
            st.subheader("1. Información Personal")
            c1, c2, c3 = st.columns(3)
            with c1:
                age = st.number_input("Edad", 0, 100, int(datos_previos.get('age', 25)))
                gender_sp = st.selectbox("Género", list(TRADUCCIONES_FIJAS["gender"].values()))
                marital_sp = st.selectbox("Estado Civil", list(TRADUCCIONES_FIJAS["maritalstatus"].values()))
            with c2:
                income = st.number_input("Sueldo Mensual", 0, 50000, int(datos_previos.get('monthlyincome', 3500)))
                overtime_sp = st.radio("Horas Extra", list(TRADUCCIONES_FIJAS["overtime"].values()), horizontal=True)
                contract = st.selectbox("Contrato", ["Fijo", "Temporal", "Servicios"], 
                                      index=["Fijo", "Temporal", "Servicios"].index(datos_previos.get('tipocontrato', 'Fijo')))
            with c3:
                f_ingreso = st.date_input("Fecha Ingreso", date.today())
                dist = st.number_input("Distancia Km", 1, 100, int(datos_previos.get('distancefromhome', 5)))

            # SECCIÓN 2: PUESTO Y EDUCACIÓN (TRADUCCIÓN DINÁMICA)
            st.subheader("2. Perfil Profesional")
            c4, c5, c6 = st.columns(3)
            with c4:
                dept_sp = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()))
                role_sp = st.selectbox("Puesto", list(MAPEO_ROLES.values()))
            with c5:
                ed_sp = st.selectbox("Campo de Educación", list(MAPEO_EDUCACION.values()))
                ed_lvl = st.slider("Nivel Educación (1-5)", 1, 5, int(datos_previos.get('education', 3)))
            with c6:
                travel_sp = st.selectbox("Viajes", list(TRADUCCIONES_FIJAS["businesstravel"].values()))
                job_lvl = st.slider("Nivel Puesto (1-5)", 1, 5, int(datos_previos.get('joblevel', 1)))

            # SECCIÓN 3: MÉTRICAS Y DESEMPEÑO
            st.subheader("3. Historial y Métricas")
            c7, c8, c9 = st.columns(3)
            with c7:
                y_comp = st.number_input("Años en Empresa", 0, 50, int(datos_previos.get('yearsatcompany', 0)))
                y_role = st.number_input("Años en Puesto", 0, 50, int(datos_previos.get('yearsincurrentrole', 0)))
            with c8:
                perf = st.number_input("Desempeño (1-4)", 1, 4, int(datos_previos.get('performancerating', 3)))
                training = st.number_input("Capacitaciones", 0, 10, int(datos_previos.get('trainingtimeslastyear', 2)))
            with c9:
                tardanzas = st.number_input("Tardanzas", 0, 100, int(datos_previos.get('numerotardanzas', 0)))
                faltas = st.number_input("Faltas", 0, 100, int(datos_previos.get('numerofaltas', 0)))

            # RESTRICCIÓN DE EDAD: BLOQUEO FÍSICO
            edad_valida = age >= 18
            if not edad_valida:
                st.error("❌ LA EDAD DEBE SER MAYOR O IGUAL A 18. BOTÓN DE GUARDADO DESHABILITADO.")

            btn_save, btn_cancel = st.columns(2)
            with btn_save:
                # El botón se bloquea si la edad es menor a 18
                guardar = st.form_submit_button("💾 GUARDAR DATOS", disabled=not edad_valida)
            with btn_cancel:
                if st.form_submit_button("❌ CANCELAR"):
                    st.session_state.show_add = False
                    st.session_state.edit_id = None
                    st.rerun()

            if guardar:
                # RE-MAPEO A INGLÉS ANTES DE ENVIAR
                def reverse(d, val): return [k for k, v in d.items() if v == val][0]

                payload = {
                    "age": age,
                    "gender": reverse(TRADUCCIONES_FIJAS["gender"], gender_sp),
                    "maritalstatus": reverse(TRADUCCIONES_FIJAS["maritalstatus"], marital_sp),
                    "department": reverse(MAPEO_DEPTOS, dept_sp),
                    "jobrole": reverse(MAPEO_ROLES, role_sp),
                    "educationfield": reverse(MAPEO_EDUCACION, ed_sp),
                    "businesstravel": reverse(TRADUCCIONES_FIJAS["businesstravel"], travel_sp),
                    "overtime": reverse(TRADUCCIONES_FIJAS["overtime"], overtime_sp),
                    "monthlyincome": income, "tipocontrato": contract, "distancefromhome": dist,
                    "education": ed_lvl, "joblevel": job_lvl, "yearsatcompany": y_comp,
                    "yearsincurrentrole": y_role, "performancerating": perf,
                    "trainingtimeslastyear": training, "numerotardanzas": tardanzas,
                    "numerofaltas": faltas, "fechaingreso": f_ingreso.isoformat()
                }

                if es_edicion:
                    pg_data = {COLUMN_MAPPING[k]: v for k, v in payload.items() if k in COLUMN_MAPPING}
                    supabase.table("empleados").update(pg_data).eq("EmployeeNumber", st.session_state.edit_id).execute()
                    st.success("Empleado actualizado.")
                else:
                    payload["employeenumber"] = get_next_id()
                    pg_data = {COLUMN_MAPPING[k]: v for k, v in payload.items() if k in COLUMN_MAPPING}
                    supabase.table("empleados").insert(pg_data).execute()
                    st.success("Empleado registrado.")
                
                st.session_state.show_add = False
                st.session_state.edit_id = None
                st.rerun()

    # TABLA DE VISUALIZACIÓN
    datos_tabla = fetch_employees()
    if datos_tabla:
        df = pd.DataFrame(datos_tabla)
        st.subheader("Listado de Empleados")
        # Mostrar columnas principales para no saturar
        columnas_ver = ['employeenumber', 'age', 'department', 'jobrole', 'monthlyincome']
        st.dataframe(df[columnas_ver], use_container_width=True, hide_index=True)

        # SELECCIÓN PARA EDICIÓN O ELIMINACIÓN
        id_selección = st.selectbox("Seleccione ID de empleado para gestionar:", [None] + [e['employeenumber'] for e in datos_tabla])
        
        if id_selección:
            col_ed, col_del = st.columns(2)
            with col_ed:
                if st.button("✏️ Editar Registro"):
                    st.session_state.edit_id = id_selección
                    st.session_state.show_add = False
                    st.rerun()
            with col_del:
                if st.button("🗑️ Eliminar Registro"):
                    supabase.table("empleados").delete().eq("EmployeeNumber", id_selección).execute()
                    st.warning(f"Empleado {id_selección} eliminado.")
                    st.rerun()

if __name__ == "__main__":
    render_employee_management_page()













