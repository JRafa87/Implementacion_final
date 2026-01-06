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

@st.cache_data(ttl=120)
def fetch_employees_fast():
    res = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
    return [{k.lower(): v for k, v in r.items()} for r in res.data]

@st.cache_data(ttl=600)
def get_tipos_contrato():
    try:
        res = supabase.table("consolidado").select("Tipocontrato").execute()
        if res.data:
            return sorted(list(set([r['Tipocontrato'] for r in res.data if r['Tipocontrato']])))
    except:
        pass
    return ["Tiempo Completo", "Indefinido", "Temporal"]

def get_next_employee_number():
    """Obtiene el último ID y suma 1"""
    try:
        res = supabase.table("empleados").select("EmployeeNumber").order("EmployeeNumber", desc=True).limit(1).execute()
        if res.data:
            return int(res.data[0]['EmployeeNumber']) + 1
        return 1
    except:
        return 1

def to_eng(mapeo, valor_esp):
    return [k for k, v in mapeo.items() if v == valor_esp][0]

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

    # --- TABLA DE LISTADO ---
    if raw_data:
        df_view = pd.DataFrame(raw_data)
        st.subheader("Listado General")
        cols_viz = {"employeenumber": "ID", "age": "Edad", "department": "Depto", "jobrole": "Puesto", "monthlyincome": "Sueldo", "tipocontrato": "Contrato"}
        df_view['department'] = df_view['department'].replace(MAPEO_DEPTOS)
        df_view['jobrole'] = df_view['jobrole'].replace(MAPEO_ROLES)
        st.dataframe(df_view.rename(columns=cols_viz)[cols_viz.values()], use_container_width=True, hide_index=True)

    st.divider()

    # --- BUSCADOR ---
    st.subheader("🔍 Localizar Colaborador")
    lista_ids = [str(e['employeenumber']) for e in raw_data]
    id_sel = st.selectbox("Escriba o seleccione ID:", [None] + lista_ids, disabled=proceso_activo)
    
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
        if st.button("➕ Nuevo Registro", use_container_width=True, disabled=proceso_activo):
            st.session_state.show_add = True
            st.rerun()

    # --- FORMULARIO INTEGRAL ---
    if proceso_activo:
        st.divider()
        es_edit = st.session_state.edit_id is not None
        p = next((e for e in raw_data if e['employeenumber'] == st.session_state.edit_id), {}) if es_edit else {}

        # Definir ID automático o existente
        current_id = st.session_state.edit_id if es_edit else get_next_employee_number()

        st.subheader("📋 Formulario de Datos" + (" (Edición: Actualización)" if es_edit else " (Nuevo Ingreso)"))
        
        # Fila de control superior
        c_top0, c_top1, c_top2 = st.columns([1, 1, 2])
        with c_top0:
            st.text_input("ID Empleado", value=str(current_id), disabled=True)
        with c_top1:
            age = st.number_input("Edad", 0, 100, int(p.get('age', 25)), disabled=es_edit)
            permitir = age >= 18
            if not permitir: st.error("🚫 Edad mínima permitida: 18 años.")
        with c_top2:
            val_gen_db = p.get('gender', "Male")
            val_gen_esp = MAPEO_GENERO.get(val_gen_db, "Masculino")
            gender = st.selectbox("Género", list(MAPEO_GENERO.values()), 
                                 index=list(MAPEO_GENERO.values()).index(val_gen_esp), 
                                 disabled=es_edit)

        with st.form("main_employee_form"):
            st.write("### 💼 Información Laboral")
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                income = st.number_input("Sueldo Mensual", 0, 100000, int(p.get('monthlyincome', 2000)))
                def_con = p.get('tipocontrato', tipos_contrato[0])
                contract = st.selectbox("Tipo de Contrato", tipos_contrato, index=tipos_contrato.index(def_con) if def_con in tipos_contrato else 0)
            with f2:
                d_val = MAPEO_DEPTOS.get(p.get('department'), "Ventas")
                dept = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()), index=list(MAPEO_DEPTOS.values()).index(d_val))
                r_val = MAPEO_ROLES.get(p.get('jobrole'), "Ejecutivo de Ventas")
                role = st.selectbox("Puesto", list(MAPEO_ROLES.values()), index=list(MAPEO_ROLES.values()).index(r_val))
            with f3:
                v_val = MAPEO_VIAJES.get(p.get('businesstravel'), "Sin Viajes")
                travel = st.selectbox("Viajes de Negocios", list(MAPEO_VIAJES.values()), index=list(MAPEO_VIAJES.values()).index(v_val))
                job_lvl = st.number_input("Nivel Puesto (1-5)", 1, 5, int(p.get('joblevel', 1)))
            with f4:
                overtime = st.selectbox("Horas Extra", ["No", "Yes"], index=0 if p.get('overtime')=="No" else 1)
                stock = st.number_input("Nivel de Acciones", 0, 3, int(p.get('stockoptionlevel', 0)))

            st.write("### 🎓 Educación y Perfil")
            e1, e2, e3, e4 = st.columns(4)
            with e1:
                ed_f_val = MAPEO_EDUCACION.get(p.get('educationfield'), "Otros")
                ed_field = st.selectbox("Campo de Estudio", list(MAPEO_EDUCACION.values()), index=list(MAPEO_EDUCACION.values()).index(ed_f_val), disabled=es_edit)
            with e2:
                ed_lvl = st.number_input("Nivel Educación", 1, 5, int(p.get('education', 3)), disabled=es_edit)
            with e3:
                civ_val = MAPEO_ESTADO_CIVIL.get(p.get('maritalstatus'), "Soltero/a")
                civil = st.selectbox("Estado Civil", list(MAPEO_ESTADO_CIVIL.values()), index=list(MAPEO_ESTADO_CIVIL.values()).index(civ_val))
            with e4:
                dist = st.number_input("Distancia Casa (km)", 0, 200, int(p.get('distancefromhome', 5)))

            st.write("### 📈 Trayectoria y Asistencia")
            t1, t2, t3, t4 = st.columns(4)
            with t1:
                y_tot = st.number_input("Años Exp Total", 0, 50, int(p.get('totalworkingyears', 1)))
                y_com = st.number_input("Años en Empresa", 0, 50, int(p.get('yearsatcompany', 1)))
            with t2:
                y_rol = st.number_input("Años Cargo Actual", 0, 50, int(p.get('yearsincurrentrole', 1)))
                y_prm = st.number_input("Años Últ. Ascenso", 0, 50, int(p.get('yearssincelastpromotion', 0)))
            with t3:
                y_mgr = st.number_input("Años con Jefe Actual", 0, 50, int(p.get('yearswithcurrmanager', 1)))
                train = st.number_input("Capacitaciones (Año ant.)", 0, 20, int(p.get('trainingtimeslastyear', 0)))
            with t4:
                n_com = st.number_input("Empresas Previas", 0, 15, int(p.get('numcompaniesworked', 0)))
                perf = st.slider("Rating Desempeño", 1, 4, int(p.get('performancerating', 3)))

            st.write("### 📅 Fechas y Otros")
            d1, d2, d3 = st.columns(3)
            with d1:
                tardanzas = st.number_input("N° Tardanzas", 0, 1000, int(p.get('numerotardanzas', 0)))
                faltas = st.number_input("N° Faltas", 0, 1000, int(p.get('numerofaltas', 0)))
            with d2:
                f_ing = st.date_input("Fecha Ingreso", date.fromisoformat(p['fechaingreso']) if p.get('fechaingreso') else date.today())
            with d3:
                f_sal_str = p.get('fechasalida')
                f_sal = st.date_input("Fecha Salida (Opcional)", date.fromisoformat(f_sal_str) if f_sal_str else None)

            submitted = st.form_submit_button("💾 GUARDAR CAMBIOS", disabled=not permitir)
            
            if submitted:
                payload = {
                    "EmployeeNumber": current_id,
                    "Age": age, "Gender": to_eng(MAPEO_GENERO, gender),
                    "MonthlyIncome": income, "Department": to_eng(MAPEO_DEPTOS, dept),
                    "JobRole": to_eng(MAPEO_ROLES, role), "BusinessTravel": to_eng(MAPEO_VIAJES, travel),
                    "EducationField": to_eng(MAPEO_EDUCACION, ed_field), "Education": ed_lvl,
                    "MaritalStatus": to_eng(MAPEO_ESTADO_CIVIL, civil), "DistanceFromHome": dist,
                    "JobLevel": job_lvl, "OverTime": overtime, "TotalWorkingYears": y_tot,
                    "YearsAtCompany": y_com, "YearsInCurrentRole": y_rol, "YearsSinceLastPromotion": y_prm,
                    "YearsWithCurrManager": y_mgr, "TrainingTimesLastYear": train, "NumCompaniesWorked": n_com,
                    "PerformanceRating": perf, "NumeroTardanzas": tardanzas, "NumeroFaltas": faltas,
                    "Tipocontrato": contract, "StockOptionLevel": stock,
                    "FechaIngreso": f_ing.isoformat() if f_ing else None,
                    "FechaSalida": f_sal.isoformat() if f_sal else None
                }
                
                if es_edit:
                    supabase.table("empleados").update(payload).eq("EmployeeNumber", current_id).execute()
                else:
                    supabase.table("empleados").insert(payload).execute()
                
                st.session_state.edit_id = None
                st.session_state.show_add = False
                st.cache_data.clear()
                st.success(f"¡Base de Datos Actualizada! (ID: {current_id})")
                st.rerun()

        if st.button("❌ Cancelar Operación"):
            st.session_state.edit_id = None
            st.session_state.show_add = False
            st.rerun()

if __name__ == "__main__":
    render_employee_management_page()











