import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
import warnings

warnings.filterwarnings("ignore")

# ==============================================================================
# 0. MAPEOS DE TRADUCCIÓN EXACTOS
# ==============================================================================

TRAD_DEPTO = {
    "Human Resources": "Recursos Humanos",
    "Research & Development": "Investigación y Desarrollo",
    "Sales": "Ventas"
}

TRAD_PUESTO = {
    "Sales Executive": "Ejecutivo de Ventas",
    "Sales Representative": "Representante de Ventas",
    "Research Scientist": "Científico de Investigación",
    "Laboratory Technician": "Técnico de Laboratorio",
    "Manufacturing Director": "Director de Manufactura",
    "Healthcare Representative": "Representante de Salud",
    "Research Director": "Director de Investigación",
    "Manager": "Gerente",
    "Human Resources": "Recursos Humanos"
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
                   "YearsSinceLastPromotion", "JobInvolvement", "NumeroFaltas"]
        response = supabase.table("consolidado").select(", ".join(columns)).execute()
        return response.data
    except Exception as e:
        st.error(f"Error en base de datos: {e}")
        return []

@st.cache_data(ttl=300)
def get_prepared_data():
    raw_data = fetch_employees_data()
    if not raw_data: return pd.DataFrame()
    df = pd.DataFrame(raw_data)
    df['Departamento_Vista'] = df['Department'].map(TRAD_DEPTO).fillna(df['Department'])
    df['Cargo_Vista'] = df['JobRole'].map(TRAD_PUESTO).fillna(df['JobRole'])
    for col in ['YearsSinceLastPromotion', 'PerformanceRating', 'JobInvolvement', 'NumeroFaltas']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

# ==============================================================================
# 2. INTERFAZ
# ==============================================================================

def render_recognition_page():
    st.title("⭐ Reconocimiento y Desarrollo")
    
    df = get_prepared_data()
    if df.empty:
        st.warning("No hay datos disponibles.")
        return

    # --- LÓGICA DE RIESGO PARA RESUMEN ---
    def classify_risk(y):
        if y >= 3: return 'Crítico'
        if y >= 2: return 'Moderado'
        return 'Bajo'
    
    df['Nivel_Riesgo'] = df['YearsSinceLastPromotion'].apply(classify_risk)
    
    # Agrupación para la tabla de resumen inicial
    summary = df.groupby('Departamento_Vista').agg(
        Critico=('Nivel_Riesgo', lambda x: (x == 'Crítico').sum()),
        Moderado=('Nivel_Riesgo', lambda x: (x == 'Moderado').sum()),
        Total=('EmployeeNumber', 'count'),
        Promedio=('YearsSinceLastPromotion', 'mean')
    ).reset_index()

    # Cálculo del porcentaje de riesgo (Críticos + Moderados sobre el total)
    summary['Riesgo %'] = ((summary['Critico'] + summary['Moderado']) / summary['Total']) * 100

    # --- TABLA INICIAL (RESTAURADA) ---
    st.subheader("Análisis de Estancamiento por Área")
    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Departamento_Vista": "Área / Departamento",
            "Critico": "Riesgo Crítico",
            "Moderado": "Riesgo Moderado",
            "Total": "N° Colaboradores",
            "Promedio": st.column_config.NumberColumn("Años Promedio", format="%.1f"),
            "Riesgo %": st.column_config.ProgressColumn(
                "Nivel de Riesgo (%)", 
                min_value=0, 
                max_value=100, 
                format="%.0f%%"
            )
        }
    )

    st.divider()

    # --- AUDITORÍA DETALLADA ---
    st.subheader("🔍 Auditoría de Colaboradores")
    lista_deptos = sorted(df['Departamento_Vista'].unique())
    dept_sel = st.selectbox("Seleccione un Departamento para auditar:", ["--- Seleccione ---"] + lista_deptos)

    if dept_sel != "--- Seleccione ---":
        df_filtrado = df[df['Departamento_Vista'] == dept_sel].copy()

        # Preparamos las tablas finales traduciendo etiquetas
        df_display = df_filtrado[['EmployeeNumber', 'Cargo_Vista', 'PerformanceRating', 'JobInvolvement', 'YearsSinceLastPromotion', 'NumeroFaltas']].copy()
        df_display.columns = ['ID', 'Cargo', 'Desempeño', 'Compromiso', 'Años sin Promoción', 'Faltas']

        tab1, tab2 = st.tabs(["🔴 Riesgo de Estancamiento", "✨ Alto Potencial para Promover"])

        with tab1:
            df_riesgo = df_display[df_display['Años sin Promoción'] >= 2.0].sort_values('Años sin Promoción', ascending=False)
            if not df_riesgo.empty:
                st.warning(f"Hay {len(df_riesgo)} colaboradores con 2+ años en el mismo cargo.")
                st.dataframe(df_riesgo, use_container_width=True, hide_index=True)
            else:
                st.success("No se detecta riesgo de estancamiento en esta área.")

        with tab2:
            df_potencial = df_display[
                (df_display['Desempeño'] >= 3) & 
                (df_display['Compromiso'] >= 3) & 
                (df_display['Años sin Promoción'] >= 1.0)
            ].sort_values(['Desempeño', 'Años sin Promoción'], ascending=False)
            
            if not df_potencial.empty:
                st.info(f"Se identificaron {len(df_potencial)} candidatos para planes de carrera.")
                st.dataframe(df_potencial, use_container_width=True, hide_index=True)
            else:
                st.write("No hay candidatos con alto potencial detectados hoy.")

if __name__ == '__main__':
    st.set_page_config(page_title="Reconocimiento", layout="wide")
    render_recognition_page()