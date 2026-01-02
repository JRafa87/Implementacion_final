import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
import warnings

warnings.filterwarnings("ignore")

# ==============================================================================
# 0. MAPEOS DE TRADUCCIÓN
# ==============================================================================

TRAD_DEPTO = {
    "HR": "Recursos Humanos",
    "RESEARCH_AND_DEVELOPMENT": "Investigación y Desarrollo",
    "SALES": "Ventas"
}

TRAD_PUESTO = {
    "HEALTHCARE_REPRESENTATIVE": "Representante de Salud",
    "HUMAN_RESOURCES": "Recursos Humanos",
    "LABORATORY_TECHNICIAN": "Técnico de Laboratorio",
    "MANAGER": "Gerente",
    "MANUFACTURING_DIRECTOR": "Director de Manufactura",
    "RESEARCH_DIRECTOR": "Director de Investigación",
    "RESEARCH_SCIENTIST": "Científico de Investigación",
    "SALES_EXECUTIVE": "Ejecutivo de Ventas",
    "SALES_REPRESENTATIVE": "Representante de Ventas"
}

# ==============================================================================
# 1. CONEXIÓN Y DATOS
# ==============================================================================

@st.cache_resource
def get_supabase() -> Optional[Client]:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key) if url and key else None

supabase = get_supabase()

def fetch_employees_data():
    if not supabase: return []
    try:
        columns = ["EmployeeNumber", "Department", "JobRole", "PerformanceRating", 
                   "YearsAtCompany", "YearsSinceLastPromotion", "NumeroFaltas", "JobInvolvement"]
        response = supabase.table("consolidado").select(", ".join(columns)).execute()
        return response.data
    except Exception as e:
        st.error(f"Error: {e}")
        return []

@st.cache_data(ttl=300)
def get_prepared_data():
    raw_data = fetch_employees_data()
    if not raw_data: return pd.DataFrame()
    df = pd.DataFrame(raw_data)
    
    # Renombrar y Traducir para la lógica y la interfaz
    df['Departamento'] = df['Department'].map(TRAD_DEPTO).fillna(df['Department'])
    df['Cargo'] = df['JobRole'].map(TRAD_PUESTO).fillna(df['JobRole'])
    
    # Limpieza numérica
    cols_num = ['YearsSinceLastPromotion', 'PerformanceRating', 'NumeroFaltas', 'JobInvolvement', 'YearsAtCompany']
    for col in cols_num:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    return df

# ==============================================================================
# 2. INTERFAZ
# ==============================================================================

def render_recognition_page():
    st.title("⭐ Reconocimiento y Desarrollo")
    
    df = get_prepared_data()
    if df.empty:
        st.error("No se detectaron datos.")
        return

    # --- Resumen de Riesgo ---
    def classify(y):
        if y >= 3: return 'Crítico'
        if y >= 2: return 'Moderado'
        return 'Bajo'
    
    df['Riesgo_Status'] = df['YearsSinceLastPromotion'].apply(classify)
    
    summary = df.groupby('Departamento').agg(
        Critico=('Riesgo_Status', lambda x: (x == 'Crítico').sum()),
        Moderado=('Riesgo_Status', lambda x: (x == 'Moderado').sum()),
        Total=('EmployeeNumber', 'count'),
        Promedio=('YearsSinceLastPromotion', 'mean')
    ).reset_index()
    summary['Riesgo %'] = (summary['Critico'] + summary['Moderado']) / summary['Total'] * 100

    st.subheader("Análisis de Estancamiento por Área")
    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Departamento": "Área / Departamento",
            "Critico": "Riesgo Crítico",
            "Moderado": "Riesgo Moderado",
            "Total": "N° Colaboradores",
            "Promedio": st.column_config.NumberColumn("Años Promedio", format="%.1f"),
            "Riesgo %": st.column_config.ProgressColumn("Nivel de Riesgo (%)", min_value=0, max_value=100, format="%.0f%%")
        }
    )

    st.divider()

    # --- Filtro de Departamento ---
    st.subheader("🔍 Auditoría de Colaboradores")
    lista_deptos = sorted(df['Departamento'].unique())
    dept_sel = st.selectbox("Seleccione el Departamento para auditar:", ["--- Seleccione un departamento ---"] + lista_deptos)

    if dept_sel != "--- Seleccione un departamento ---":
        df_filtrado = df[df['Departamento'] == dept_sel].copy()

        # Preparar DataFrame final con nombres de columnas ya traducidos para que Streamlit los tome
        # Eliminamos 'Departamento' porque ya está en el filtro
        df_final = df_filtrado[['EmployeeNumber', 'Cargo', 'PerformanceRating', 'JobInvolvement', 'YearsSinceLastPromotion', 'NumeroFaltas']].copy()
        df_final.columns = ['ID', 'Cargo', 'Desempeño', 'Compromiso', 'Años sin Promoción', 'Faltas']

        tab1, tab2 = st.tabs(["🔴 Riesgo de Estancamiento", "✨ Alto Potencial para Promover"])

        with tab1:
            # Riesgo: 2 o más años sin promoción
            candidatos_riesgo = df_final[df_final['Años sin Promoción'] >= 2.0]
            if not candidatos_riesgo.empty:
                st.warning(f"Se identificaron **{len(candidatos_riesgo)}** colaboradores con 2+ años sin ascenso.")
                st.dataframe(candidatos_riesgo, use_container_width=True, hide_index=True)
            else:
                st.success("No hay colaboradores en riesgo en esta área.")

        with tab2:
            # Potencial: Desempeño >= 3 y Compromiso >= 3
            candidatos_potencial = df_final[
                (df_final['Desempeño'] >= 3) & 
                (df_final['Compromiso'] >= 3) & 
                (df_final['Años sin Promoción'] >= 1.0)
            ]
            if not candidatos_potencial.empty:
                st.success(f"Se identificaron **{len(candidatos_potencial)}** candidatos con perfil para promoción.")
                st.dataframe(candidatos_potencial, use_container_width=True, hide_index=True)
            else:
                st.info("No hay candidatos que cumplan el perfil de alto potencial en este momento.")

if __name__ == '__main__':
    st.set_page_config(page_title="Reconocimiento", layout="wide")
    render_recognition_page()