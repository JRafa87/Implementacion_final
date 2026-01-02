import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS (INGLÉS ORIGINAL <-> ESPAÑOL)
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
TRADUCCIONES_FIJAS = {
    "businesstravel": {"Non-Travel": "No viaja", "Travel_Rarely": "Viaja raramente", "Travel_Frequently": "Viaja frecuentemente"},
    "gender": {"Male": "Masculino", "Female": "Femenino"},
    "maritalstatus": {"Single": "Soltero/a", "Married": "Casado/a", "Divorced": "Divorciado/a"},
    "overtime": {"Yes": "Sí", "No": "No"}
}

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
# 3. INTERFAZ
# -----------------------------------

def render_employee_management_page():
    st.title("👥 Gestión de Empleados")

    if "edit_id" not in st.session_state: st.session_state.edit_id = None
    if "show_add" not in st.session_state: st.session_state.show_add = False

    # Botones superiores
    c_nav1, c_nav2 = st.columns(2)
    with c_nav1:
        if st.button("➕ Nuevo Empleado"):
            st.session_state.show_add = True
            st.session_state.edit_id = None
            st.rerun()
    with c_nav2:
        if st.button("🔄 Recargar"): st.rerun()

    # FORMULARIO (NUEVO O EDICIÓN)
    if st.session_state.show_add or st.session_state.edit_id:
        es_edit = st.session_state.edit_id is not None
        prev = {}
        if es_edit:
            res = supabase.table("empleados").select("*").eq("EmployeeNumber", st.session_state.edit_id).single().execute()
            prev = {k.lower(): v for k, v in res.data.items()}

        with st.form("form_emp"):
            st.header("✏️ Datos del Empleado")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                # RESTRICCIÓN: Edad desde 18 para evitar errores de entrada, pero validamos igual
                age = st.number_input("Edad", 0, 100, int(prev.get('age', 25)))
                gender_s = st.selectbox("Género", list(TRADUCCIONES_FIJAS["gender"].values()))
                marital_s = st.selectbox("Estado Civil", list(TRADUCCIONES_FIJAS["maritalstatus"].values()))
            with c2:
                income = st.number_input("Salario Mensual", 0, 50000, int(prev.get('monthlyincome', 3000)))
                overtime_s = st.radio("Horas Extra", list(TRADUCCIONES_FIJAS["overtime"].values()), horizontal=True)
                contract = st.selectbox("Contrato", ["Fijo", "Temporal", "Servicios"])
            with c3:
                dept_s = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()))
                role_s = st.selectbox("Puesto", list(MAPEO_ROLES.values()))
                ed_s = st.selectbox("Educación", list(MAPEO_EDUCACION.values()))

            st.subheader("Métricas de Desempeño")
            c4, c5, c6 = st.columns(3)
            with c4:
                y_comp = st.number_input("Años Empresa", 0, 50, int(prev.get('yearsatcompany', 0)))
                dist = st.number_input("Distancia Km", 0, 100, int(prev.get('distancefromhome', 5)))
            with c5:
                perf = st.number_input("Calificación (1-4)", 1, 4, int(prev.get('performancerating', 3)))
                tardanzas = st.number_input("Tardanzas", 0, 100, int(prev.get('numerotardanzas', 0)))
            with c6:
                faltas = st.number_input("Faltas", 0, 100, int(prev.get('numerofaltas', 0)))
                f_ingreso = st.date_input("Fecha Ingreso", date.today())

            # VALIDACIÓN CRÍTICA
            bloqueado = age < 18
            if bloqueado:
                st.error("⚠️ PROHIBIDO: Edad menor a 18 años. El botón de guardado no funcionará.")

            b_save, b_cancel = st.columns(2)
            with b_save:
                # Bloqueo real del botón
                btn_txt = "ACTUALIZAR" if es_edit else "GUARDAR"
                submit = st.form_submit_button(btn_txt, disabled=bloqueado)
            with b_cancel:
                if st.form_submit_button("CANCELAR"):
                    st.session_state.show_add = False
                    st.session_state.edit_id = None
                    st.rerun()

            if submit and not bloqueado:
                def rev(d, v): return [k for k, val in d.items() if val == v][0]
                
                payload = {
                    "age": age, "monthlyincome": income, "tipocontrato": contract,
                    "distancefromhome": dist, "yearsatcompany": y_comp, "performancerating": perf,
                    "numerotardanzas": tardanzas, "numerofaltas": faltas, "fechaingreso": f_ingreso.isoformat(),
                    "gender": rev(TRADUCCIONES_FIJAS["gender"], gender_s),
                    "maritalstatus": rev(TRADUCCIONES_FIJAS["maritalstatus"], marital_s),
                    "overtime": rev(TRADUCCIONES_FIJAS["overtime"], overtime_s),
                    "department": rev(MAPEO_DEPTOS, dept_s),
                    "jobrole": rev(MAPEO_ROLES, role_s),
                    "educationfield": rev(MAPEO_EDUCACION, ed_s),
                    "businesstravel": "Travel_Rarely" # Valor por defecto funcional
                }

                if es_edit:
                    pg_data = {COLUMN_MAPPING[k]: v for k, v in payload.items() if k in COLUMN_MAPPING}
                    supabase.table("empleados").update(pg_data).eq("EmployeeNumber", st.session_state.edit_id).execute()
                    st.success("Empleado actualizado")
                else:
                    payload["employeenumber"] = get_next_id()
                    pg_data = {COLUMN_MAPPING[k]: v for k, v in payload.items() if k in COLUMN_MAPPING}
                    supabase.table("empleados").insert(pg_data).execute()
                    st.success("Empleado creado")
                
                st.session_state.show_add = False
                st.session_state.edit_id = None
                st.rerun()

    # TABLA EN ESPAÑOL
    raw = fetch_employees()
    if raw:
        df = pd.DataFrame(raw)
        
        # TRADUCCIÓN DE DATOS PARA LA TABLA
        df['department'] = df['department'].map(MAPEO_DEPTOS).fillna(df['department'])
        df['jobrole'] = df['jobrole'].map(MAPEO_ROLES).fillna(df['jobrole'])
        
        # RENOMBRAR COLUMNAS PARA LA VISTA
        df_view = df[['employeenumber', 'age', 'department', 'jobrole', 'monthlyincome']].rename(columns={
            'employeenumber': 'ID', 'age': 'Edad', 'department': 'Departamento', 
            'jobrole': 'Puesto', 'monthlyincome': 'Sueldo'
        })
        
        st.subheader("Listado de Colaboradores")
        st.dataframe(df_view, use_container_width=True, hide_index=True)

        # GESTIÓN DE FILAS
        sel_id = st.selectbox("Seleccione ID para Editar o Eliminar", [None] + [e['employeenumber'] for e in raw])
        if sel_id:
            ced, cdel = st.columns(2)
            with ced:
                if st.button("✏️ Editar"):
                    st.session_state.edit_id = sel_id
                    st.session_state.show_add = False
                    st.rerun()
            with cdel:
                if st.button("🗑️ Eliminar"):
                    supabase.table("empleados").delete().eq("EmployeeNumber", sel_id).execute()
                    st.rerun()

if __name__ == "__main__":
    render_employee_management_page()













