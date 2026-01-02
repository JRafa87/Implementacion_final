import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS (Interfaz Español <-> DB Inglés)
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
MAPEO_VIAJES = {"Non-Travel": "Sin Viajes", "Travel_Rarely": "Viaja Poco", "Travel_Frequently": "Viaja Frecuentemente"}
MAPEO_ESTADO_CIVIL = {"Single": "Soltero/a", "Married": "Casado/a", "Divorced": "Divorciado/a"}
MAPEO_GENERO = {"Male": "Masculino", "Female": "Femenino"}

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key)

supabase = get_supabase()

def fetch_employees():
    res = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
    return [{k.lower(): v for k, v in r.items()} for r in res.data]

def to_eng(mapeo, valor_esp):
    return [k for k, v in mapeo.items() if v == valor_esp][0]

# =================================================================
# 2. INTERFAZ DE USUARIO
# =================================================================

def render_employee_management_page():
    st.title("👥 Gestión de Personal (Sistema Integral)")

    if "edit_id" not in st.session_state: st.session_state.edit_id = None
    if "show_add" not in st.session_state: st.session_state.show_add = False

    proceso_activo = st.session_state.edit_id is not None or st.session_state.show_add
    raw_data = fetch_employees()

    # --- TABLA DE LISTADO ---
    if raw_data:
        df_view = pd.DataFrame(raw_data)
        st.subheader("Listado General")
        cols_viz = {"employeenumber": "ID", "age": "Edad", "department": "Depto", "jobrole": "Puesto", "monthlyincome": "Sueldo", "tipocontrato": "Contrato"}
        # Traducimos solo para la vista
        df_view['department'] = df_view['department'].replace(MAPEO_DEPTOS)
        df_view['jobrole'] = df_view['jobrole'].replace(MAPEO_ROLES)
        st.dataframe(df_view.rename(columns=cols_viz)[cols_viz.values()], use_container_width=True, hide_index=True)

    st.divider()

    # --- BUSCADOR HÍBRIDO ---
    st.subheader("🔍 Localizar Colaborador")
    lista_ids = [str(e['employeenumber']) for e in raw_data]
    id_sel = st.selectbox("Escriba o seleccione ID:", [None] + lista_ids, disabled=proceso_activo)
    
    c_b1, c_b2, c_b3 = st.columns(3)
    with c_b1:
        if st.button("✏️ Editar", use_container_width=True, disabled=proceso_activo or not id_sel):
            st.session_state.edit_id = int(id_sel); st.rerun()
    with c_b2:
        if st.button("🗑️ Eliminar", use_container_width=True, disabled=proceso_activo or not id_sel):
            supabase.table("empleados").delete().eq("EmployeeNumber", int(id_sel)).execute()
            st.rerun()
    with c_b3:
        if st.button("➕ Nuevo Registro", use_container_width=True, disabled=proceso_activo):
            st.session_state.show_add = True; st.rerun()

    # --- FORMULARIO INTEGRAL ---
    if proceso_activo:
        st.divider()
        es_edit = st.session_state.edit_id is not None
        p = next((e for e in raw_data if e['employeenumber'] == st.session_state.edit_id), {}) if es_edit else {}

        st.subheader("📋 Datos del Colaborador" + (" (Edición - Campos Protegidos)" if es_edit else " (Nuevo Ingreso)"))
        
        # --- RESTRICCIONES DE EDICIÓN ---
        c_top1, c_top2 = st.columns(2)
        with c_top1:
            age = st.number_input("Edad", 0, 100, int(p.get('age', 25)), disabled=es_edit)
            if age < 18: st.error("🚫 Edad mínima permitida: 18 años."); permitir = False
            else: permitir = True
        with c_top2:
            val_gen = MAPEO_GENERO.get(p.get('gender'), "Masculino")
            gender = st.selectbox("Género", list(MAPEO_GENERO.values()), index=list(MAPEO_GENERO.values()).index(val_gen), disabled=es_edit)

        with st.form("form_final"):
            # FILA 1: LABORAL PRINCIPAL
            st.write("### 💼 Contrato y Puesto")
            f1_1, f1_2, f1_3, f1_4 = st.columns(4)
            with f1_1:
                income = st.number_input("Sueldo Mensual", 0, 100000, int(p.get('monthlyincome', 2000)))
                contract = st.selectbox("Tipo Contrato", ["Tiempo Completo", "Part-Time", "Freelance"], index=0)
            with f1_2:
                curr_dep = MAPEO_DEPTOS.get(p.get('department'), "Ventas")
                dept = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()), index=list(MAPEO_DEPTOS.values()).index(curr_dep))
                curr_role = MAPEO_ROLES.get(p.get('jobrole'), "Ejecutivo de Ventas")
                role = st.selectbox("Puesto", list(MAPEO_ROLES.values()), index=list(MAPEO_ROLES.values()).index(curr_role))
            with f1_3:
                curr_trav = MAPEO_VIAJES.get(p.get('businesstravel'), "Sin Viajes")
                travel = st.selectbox("Viajes de Negocios", list(MAPEO_VIAJES.values()), index=list(MAPEO_VIAJES.values()).index(curr_trav))
                job_lvl = st.number_input("Nivel Puesto (1-5)", 1, 5, int(p.get('joblevel', 1)))
            with f1_4:
                overtime = st.selectbox("Horas Extra", ["No", "Yes"], index=0 if p.get('overtime')=="No" else 1)
                stock = st.number_input("Stock Options", 0, 3, int(p.get('stockoptionlevel', 0)))

            # FILA 2: EDUCACIÓN (BLOQUEADA EN EDICIÓN)
            st.write("### 🎓 Educación y Perfil")
            f2_1, f2_2, f2_3, f2_4 = st.columns(4)
            with f2_1:
                curr_ed_f = MAPEO_EDUCACION.get(p.get('educationfield'), "Otros")
                ed_field = st.selectbox("Campo Estudio", list(MAPEO_EDUCACION.values()), index=list(MAPEO_EDUCACION.values()).index(curr_ed_f), disabled=es_edit)
            with f2_2:
                ed_lvl = st.number_input("Nivel Educación", 1, 5, int(p.get('education', 3)), disabled=es_edit)
            with f2_3:
                curr_civ = MAPEO_ESTADO_CIVIL.get(p.get('maritalstatus'), "Soltero/a")
                civil = st.selectbox("Estado Civil", list(MAPEO_ESTADO_CIVIL.values()), index=list(MAPEO_ESTADO_CIVIL.values()).index(curr_civ))
            with f2_4:
                dist = st.number_input("Distancia (km)", 0, 200, int(p.get('distancefromhome', 5)))

            # FILA 3: TRAYECTORIA Y TIEMPOS
            st.write("### ⏳ Trayectoria en la Empresa")
            f3_1, f3_2, f3_3, f3_4 = st.columns(4)
            with f3_1:
                y_total = st.number_input("Años Exp Total", 0, 50, int(p.get('totalworkingyears', 1)))
                y_comp = st.number_input("Años en Empresa", 0, 50, int(p.get('yearsatcompany', 1)))
            with f3_2:
                y_role = st.number_input("Años Cargo Actual", 0, 50, int(p.get('yearsincurrentrole', 1)))
                y_prom = st.number_input("Años Últ. Ascenso", 0, 50, int(p.get('yearssincelastpromotion', 0)))
            with f3_3:
                y_mgr = st.number_input("Años con Jefe Actual", 0, 50, int(p.get('yearswithcurrmanager', 1)))
                train = st.number_input("Capacitaciones (Año ant.)", 0, 20, int(p.get('trainingtimeslastyear', 0)))
            with f3_4:
                num_comp = st.number_input("Empresas Previas", 0, 15, int(p.get('numcompaniesworked', 0)))
                perf = st.slider("Rating Desempeño", 1, 4, int(p.get('performancerating', 3)))

            # FILA 4: ASISTENCIA Y FECHAS
            st.write("### 📅 Asistencia y Fechas")
            f4_1, f4_2, f4_3 = st.columns(3)
            with f4_1:
                tardanzas = st.number_input("N° Tardanzas", 0, 1000, int(p.get('numerotardanzas', 0)))
                faltas = st.number_input("N° Faltas", 0, 1000, int(p.get('numerofaltas', 0)))
            with f4_2:
                f_ing = st.date_input("Fecha Ingreso", date.fromisoformat(p['fechaingreso']) if p.get('fechaingreso') else date.today())
            with f4_3:
                f_salida = st.date_input("Fecha Salida (Opcional)", date.fromisoformat(p['fechasalida']) if p.get('fechasalida') else None)

            # --- GUARDADO ---
            if st.form_submit_button("💾 GUARDAR TODO", disabled=not permitir):
                payload = {
                    "Age": age, "Gender": to_eng(MAPEO_GENERO, gender),
                    "MonthlyIncome": income, "Department": to_eng(MAPEO_DEPTOS, dept),
                    "JobRole": to_eng(MAPEO_ROLES, role), "BusinessTravel": to_eng(MAPEO_VIAJES, travel),
                    "EducationField": to_eng(MAPEO_EDUCACION, ed_field), "Education": ed_lvl,
                    "MaritalStatus": to_eng(MAPEO_ESTADO_CIVIL, civil), "DistanceFromHome": dist,
                    "JobLevel": job_lvl, "OverTime": overtime, "TotalWorkingYears": y_total,
                    "YearsAtCompany": y_comp, "YearsInCurrentRole": y_role, "YearsSinceLastPromotion": y_prom,
                    "YearsWithCurrManager": y_mgr, "TrainingTimesLastYear": train, "NumCompaniesWorked": num_comp,
                    "PerformanceRating": perf, "NumeroTardanzas": tardanzas, "NumeroFaltas": faltas,
                    "Tipocontrato": contract, "FechaIngreso": f_ing.isoformat(),
                    "FechaSalida": f_salida.isoformat() if f_salida else None
                }
                
                if es_edit:
                    supabase.table("empleados").update(payload).eq("EmployeeNumber", st.session_state.edit_id).execute()
                else:
                    l_res = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
                    payload["EmployeeNumber"] = (l_res.data[0]['EmployeeNumber'] + 1) if l_res.data else 1
                    supabase.table("empleados").insert(payload).execute()
                
                st.session_state.edit_id = None; st.session_state.show_add = False
                st.success("¡Base de datos actualizada!"); st.rerun()

        if st.button("❌ Cancelar"):
            st.session_state.edit_id = None; st.session_state.show_add = False; st.rerun()

if __name__ == "__main__":
    render_employee_management_page()











