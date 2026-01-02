import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
import warnings

warnings.filterwarnings("ignore")

# ==============================================================================
# 0. MAPEOS DE TRADUCCIÓN (Para la Interfaz)
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
        # Traemos las columnas con sus nombres originales de la base de datos
        columns = ["EmployeeNumber", "Department", "JobRole", "PerformanceRating", 
                   "YearsAtCompany", "YearsSinceLastPromotion", "NumeroFaltas", "JobInvolvement"]
        
        response = supabase.table("consolidado").select(", ".join(columns)).execute()
        
        # Procesamos los datos manteniendo nombres internos consistentes
        data = []
        for r in response.data:
            data.append({
                "id": r.get("EmployeeNumber"),
                "depto_orig": r.get("Department"), # Guardamos el original para lógica
                "puesto_orig": r.get("JobRole"),   # Guardamos el original para lógica
                "performancerating": r.get("PerformanceRating"),
                "yearsatcompany": r.get("YearsAtCompany"),
                "yearssincelastpromotion": r.get("YearsSinceLastPromotion"),
                "numerofaltas": r.get("NumeroFaltas"),
                "jobinvolvement": r.get("JobInvolvement")
            })
        return data
    except Exception as e:
        st.error(f"Error: {e}")
        return []

@st.cache_data(ttl=300)
def get_prepared_data():
    data = fetch_employees_data()
    if not data: return pd.DataFrame()
    df = pd.DataFrame(data)
    
    # Creamos las versiones traducidas como nuevas columnas para mostrar
    df['Departamento'] = df['depto_orig'].map(TRAD_DEPTO).fillna(df['depto_orig'])
    df['Puesto'] = df['puesto_orig'].map(TRAD_PUESTO).fillna(df['puesto_orig'])
    
    # Limpieza numérica
    for col in ['yearssincelastpromotion', 'performancerating', 'numerofaltas', 'jobinvolvement']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    return df

# ==============================================================================
# 2. LÓGICA DE RIESGO
# ==============================================================================

def get_risk_summary(df):
    # Clasificamos usando el nombre traducido 'Departamento' para que el resumen ya salga en español
    def classify(years):
        if years >= 3: return 'Crítico'
        if years >= 2: return 'Moderado'
        return 'Bajo'
    
    df['Riesgo'] = df['yearssincelastpromotion'].apply(classify)
    
    summary = df.groupby('Departamento').agg(
        Critico=('Riesgo', lambda x: (x == 'Crítico').sum()),
        Moderado=('Riesgo', lambda x: (x == 'Moderado').sum()),
        Total=('id', 'count'),
        Promedio=('yearssincelastpromotion', 'mean')
    ).reset_index()
    
    summary['Riesgo %'] = (summary['Critico'] + summary['Moderado']) / summary['Total'] * 100
    return summary

# ==============================================================================
# 3. INTERFAZ (Donde impacta la traducción)
# ==============================================================================

def render_recognition_page():
    st.title("⭐ Reconocimiento y Desarrollo")
    
    df = get_prepared_data()
    if df.empty:
        st.error("No se detectaron datos.")
        return

    summary = get_risk_summary(df)

    # 1. Alertas Superiores
    total_criticos = summary['Critico'].sum()
    if total_criticos > 0:
        st.error(f"🛑 Se han detectado **{total_criticos} colaboradores** en estado crítico (más de 3 años sin ascenso).")

    # 2. Tabla Resumen (Traducción aplicada en las columnas)
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

    # 3. Filtro y Tabla de Empleados
    st.divider()
    st.subheader("🔍 Detalle de Candidatos")
    
    # El selector ahora usa los nombres ya traducidos
    lista_deptos = sorted(df['Departamento'].unique())
    dept_sel = st.selectbox("Filtrar por Departamento:", ["--- Mostrar Todos ---"] + lista_deptos)

    df_view = df.copy()
    if dept_sel != "--- Mostrar Todos ---":
        df_view = df_view[df_view['Departamento'] == dept_sel]

    # Mostramos la tabla final con nombres de columnas amigables
    st.data_editor(
        df_view[['id', 'Puesto', 'Departamento', 'performancerating', 'jobinvolvement', 'yearssincelastpromotion']],
        column_config={
            "id": "ID",
            "Puesto": "Cargo",
            "Departamento": "Área",
            "performancerating": "Desempeño",
            "jobinvolvement": "Compromiso",
            "yearssincelastpromotion": st.column_config.NumberColumn("⚠️ Años S/Prom.", format="%.1f")
        },
        disabled=True,
        hide_index=True,
        use_container_width=True
    )

if __name__ == '__main__':
    st.set_page_config(page_title="Reconocimiento", layout="wide")
    render_recognition_page()