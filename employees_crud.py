import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date

# =================================================================
# 1. CONFIGURACIÓN Y MAPEOS (MANTENIENDO ESPAÑOL)
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

@st.cache_data(ttl=60)
def fetch_employees_fast():
    """Trae los datos manteniendo los nombres de columna originales de la DB"""
    res = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
    return res.data

@st.cache_data(ttl=600)
def get_tipos_contrato():
    try:
        res = supabase.table("empleados").select("Tipocontrato").execute()
        if res.data:
            # Filtrar valores nulos y duplicados
            tipos = sorted(list(set([r['Tipocontrato'] for r in res.data if r.get('Tipocontrato')])))
            return tipos if tipos else ["Indefinido", "Temporal"]
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

    # Inicialización de estados
    if "edit_id" not in st.session_state: st.session_state.edit_id = None
    if "show_add" not in st.session_state: st.session_state.show_add = False

    proceso_activo = st.session_state.edit_id is not None or st.session_state.show_add
    raw_data = fetch_employees_fast()
    tipos_contrato = get_tipos_contrato()

    # --- TABLA DE LISTADO (SOLO ACTIVOS) ---
    if raw_data:
        # Filtramos para mostrar solo activos en la tabla de vista previa rápida
        activos_df = [e for e in raw_data if not e.get('FechaSalida')]
        df_view = pd.DataFrame(activos_df)
        
        st.subheader(f"Listado de Colaboradores Activos ({len(activos_df)})")
        
        # Mapeo de columnas para la vista en español
        cols_viz = {
            "EmployeeNumber": "ID", 
            "Age": "Edad", 
            "Department": "Depto", 
            "JobRole": "Puesto", 
            "MonthlyIncome": "Sueldo", 
            "Tipocontrato": "Contrato"
        }
        
        # Aplicar traducciones para la tabla
        df_view['Department'] = df_view['Department'].replace(MAPEO_DEPTOS)
        df_view['JobRole'] = df_view['JobRole'].replace(MAPEO_ROLES)
        
        # Seleccionar y renombrar solo las columnas deseadas
        st.dataframe(
            df_view.rename(columns=cols_viz)[list(cols_viz.values())], 
            use_container_width=True, 
            hide_index=True
        )

    st.divider()

    # --- BUSCADOR INTEGRAL (ACTIVOS Y NO ACTIVOS) ---
    st.subheader("🔍 Localizar Colaborador")
    st.info("Busca por ID para editar o dar de baja a cualquier trabajador del sistema.")
    
    # Aquí cargamos TODOS los IDs para que el administrador pueda encontrar incluso a los que se fueron
    lista_ids = [str(e['EmployeeNumber']) for e in raw_data]
    id_sel = st.selectbox("Escriba o seleccione ID del empleado:", [None] + lista_ids, disabled=proceso_activo)
    
    c_b1, c_b2, c_b3 = st.columns(3)
    with c_b1:
        if st.button("✏️ Editar Datos", use_container_width=True, disabled=proceso_activo or not id_sel):
            st.session_state.edit_id = int(id_sel)
            st.rerun()
    with c_b2:
        if st.button("🗑️ Eliminar Registro", use_container_width=True, disabled=proceso_activo or not id_sel):
            # Esta acción borra de la tabla empleados (y por trigger del consolidado)
            supabase.table("empleados").delete().eq("EmployeeNumber", int(id_sel)).execute()
            st.cache_data.clear()
            st.success(f"ID {id_sel} eliminado correctamente.")
            st.rerun()
    with c_b3:
        if st.button("➕ Registrar Nuevo", use_container_width=True, disabled=proceso_activo, type="primary"):
            st.session_state.show_add = True
            st.rerun()

    # --- FORMULARIO DE EDICIÓN / ALTA ---
    if proceso_activo:
        st.divider()
        es_edit = st.session_state.edit_id is not None
        # Buscar el registro usando el nombre exacto de la columna de la DB
        p = next((e for e in raw_data if e['EmployeeNumber'] == st.session_state.edit_id), {}) if es_edit else {}

        current_id = st.session_state.edit_id if es_edit else get_next_employee_number()

        st.subheader("📋 Datos del Colaborador" + (f" (Editando ID: {current_id})" if es_edit else " (Nuevo Registro)"))
        
        # Fila superior de información básica
        c_top1, c_top2, c_top3 = st.columns(3)
        with c_top1:
            st.text_input("ID del Sistema", value=str(current_id), disabled=True)
        with c_top2:
            age = st.number_input("Edad Actual", 18, 100, int(p.get('Age', 25)))
        with c_top3:
            gen_db = p.get('Gender', "Male")
            gen_esp = MAPEO_GENERO.get(gen_db, "Masculino")
            gender = st.selectbox("Género", list(MAPEO_GENERO.values()), 
                                 index=list(MAPEO_GENERO.values()).index(gen_esp))

        with st.form("form_gestion_personal"):
            st.markdown("#### 💼 Situación Laboral")
            f1, f2, f3 = st.columns(3)
            with f1:
                income = st.number_input("Sueldo Mensual ($)", 0, 50000, int(p.get('MonthlyIncome', 1500)))
                dept_esp = MAPEO_DEPTOS.get(p.get('Department'), "Ventas")
                dept = st.selectbox("Departamento", list(MAPEO_DEPTOS.values()), index=list(MAPEO_DEPTOS.values()).index(dept_esp))
            with f2:
                role_esp = MAPEO_ROLES.get(p.get('JobRole'), "Ejecutivo de Ventas")
                role = st.selectbox("Puesto / Cargo", list(MAPEO_ROLES.values()), index=list(MAPEO_ROLES.values()).index(role_esp))
                def_con = p.get('Tipocontrato', "Indefinido")
                contract = st.selectbox("Tipo de Contrato", tipos_contrato, index=tipos_contrato.index(def_con) if def_con in tipos_contrato else 0)
            with f3:
                travel_esp = MAPEO_VIAJES.get(p.get('BusinessTravel'), "Sin Viajes")
                travel = st.selectbox("Frecuencia de Viajes", list(MAPEO_VIAJES.values()), index=list(MAPEO_VIAJES.values()).index(travel_esp))
                overtime = st.selectbox("Aplica Horas Extra", ["No", "Yes"], index=0 if p.get('OverTime')=="No" else 1)

            st.markdown("#### 📈 Historial y Asistencia")
            h1, h2, h3 = st.columns(3)
            with h1:
                y_com = st.number_input("Años en esta Empresa", 0, 50, int(p.get('YearsAtCompany', 0)))
                tardanzas = st.number_input("Total de Tardanzas", 0, 500, int(p.get('NumeroTardanzas', 0)))
            with h2:
                perf = st.slider("Calificación Desempeño (1-4)", 1, 4, int(p.get('PerformanceRating', 3)))
                faltas = st.number_input("Total de Faltas", 0, 100, int(p.get('NumeroFaltas', 0)))
            with h3:
                f_ing_val = p.get('FechaIngreso')
                f_ing = st.date_input("Fecha de Ingreso", date.fromisoformat(f_ing_val) if f_ing_val else date.today())
                f_sal_val = p.get('FechaSalida')
                # Usamos una casilla para habilitar la fecha de salida y no tener problemas de formato
                dar_de_baja = st.checkbox("Registrar Fecha de Salida (Cese)", value=True if f_sal_val else False)
                f_sal = st.date_input("Fecha de Salida", date.fromisoformat(f_sal_val) if f_sal_val else date.today(), disabled=not dar_de_baja)

            st.divider()
            
            # Recolección de campos adicionales ocultos para no saturar la vista pero mantener el Consolidado
            # (Aquí podrías agregar los demás campos siguiendo el mismo patrón si los necesitas editar)

            c_save, c_cancel = st.columns(2)
            with c_save:
                if st.form_submit_button("💾 Guardar Cambios en Sistema", use_container_width=True, type="primary"):
                    payload = {
                        "EmployeeNumber": current_id,
                        "Age": age, 
                        "Gender": to_eng(MAPEO_GENERO, gender),
                        "MonthlyIncome": income, 
                        "Department": to_eng(MAPEO_DEPTOS, dept),
                        "JobRole": to_eng(MAPEO_ROLES, role), 
                        "BusinessTravel": to_eng(MAPEO_VIAJES, travel),
                        "OverTime": overtime,
                        "Tipocontrato": contract,
                        "PerformanceRating": perf,
                        "NumeroTardanzas": tardanzas,
                        "NumeroFaltas": faltas,
                        "YearsAtCompany": y_com,
                        "FechaIngreso": f_ing.isoformat(),
                        "FechaSalida": f_sal.isoformat() if dar_de_baja else None
                    }
                    
                    if es_edit:
                        supabase.table("empleados").update(payload).eq("EmployeeNumber", current_id).execute()
                    else:
                        supabase.table("empleados").insert(payload).execute()
                    
                    st.session_state.edit_id = None
                    st.session_state.show_add = False
                    st.cache_data.clear()
                    st.rerun()
            
            with c_cancel:
                if st.form_submit_button("🚫 Cancelar", use_container_width=True):
                    st.session_state.edit_id = None
                    st.session_state.show_add = False
                    st.rerun()

if __name__ == "__main__":
    render_employee_management_page()











