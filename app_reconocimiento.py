import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
import warnings

warnings.filterwarnings("ignore")

# ==============================================================================
# 0. MAPEOS DE TRADUCCIÓN EXACTOS (Basados en tu lista)
# ==============================================================================

TRAD_DEPTO = {
    "Human Resources": "Recursos Humanos",
    "Research & Development": "Investigación y Desarrollo",
    "Sales": "Ventas"
}

TRAD_PUESTO = {
    # Ventas
    "Sales Executive": "Ejecutivo de Ventas",
    "Sales Representative": "Representante de Ventas",
    # I+D
    "Research Scientist": "Científico de Investigación",
    "Laboratory Technician": "Técnico de Laboratorio",
    "Manufacturing Director": "Director de Manufactura",
    "Healthcare Representative": "Representante de Salud",
    "Research Director": "Director de Investigación",
    # Comunes / HR
    "Manager": "Gerente",
    "Human Resources": "Recursos Humanos"
}

# ==============================================================================
# 1. CONEXIÓN Y OBTENCIÓN DE DATOS
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
        # Extraemos las columnas clave de la tabla consolidado
        columns = ["EmployeeNumber", "Department", "JobRole", "PerformanceRating", 
                   "YearsSinceLastPromotion", "JobInvolvement", "NumeroFaltas"]
        response = supabase.table("consolidado").select(", ".join(columns)).execute()
        return response.data
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return []

@st.cache_data(ttl=300)
def get_prepared_data():
    raw_data = fetch_employees_data()
    if not raw_data: return pd.DataFrame()
    df = pd.DataFrame(raw_data)
    
    # Aplicamos la traducción interna
    df['Departamento_Vista'] = df['Department'].map(TRAD_DEPTO).fillna(df['Department'])
    df['Cargo_Vista'] = df['JobRole'].map(TRAD_PUESTO).fillna(df['JobRole'])
    
    # Limpieza de datos numéricos
    cols_num = ['YearsSinceLastPromotion', 'PerformanceRating', 'JobInvolvement', 'NumeroFaltas']
    for col in cols_num:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    return df

# ==============================================================================
# 2. RENDERIZADO DE LA PÁGINA
# ==============================================================================

def render_recognition_page():
    st.title("⭐ Reconocimiento y Desarrollo")
    
    df = get_prepared_data()
    if df.empty:
        st.warning("No se encontraron datos para procesar.")
        return

    # --- Resumen Ejecutivo por Departamento ---
    def classify_risk(y):
        if y >= 3: return 'Crítico'
        if y >= 2: return 'Moderado'
        return 'Bajo'
    
    df['Nivel_Riesgo'] = df['YearsSinceLastPromotion'].apply(classify_risk)
    
    summary = df.groupby('Departamento_Vista').agg(
        Critico=('Nivel_Riesgo', lambda x: (x == 'Crítico').sum()),
        Moderado=('Nivel_Riesgo', lambda x: (x == 'Moderado').sum()),
        Total=('EmployeeNumber', 'count'),
        Promedio_Anos=('YearsSinceLastPromotion', 'mean')
    ).reset_index()

    st.subheader("Estado de Estancamiento por Departamento")
    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Departamento_Vista": "Departamento",
            "Critico": "Riesgo Crítico (>3 años)",
            "Moderado": "Riesgo Moderado (2-3 años)",
            "Total": "Colaboradores Totales",
            "Promedio_Anos": st.column_config.NumberColumn("Promedio de Años", format="%.1f")
        }
    )

    st.divider()

    # --- Buscador y Filtro ---
    st.subheader("🔍 Auditoría de Colaboradores")
    lista_deptos = sorted(df['Departamento_Vista'].unique())
    dept_sel = st.selectbox("Seleccione un Departamento para analizar:", ["--- Seleccione ---"] + lista_deptos)

    if dept_sel != "--- Seleccione ---":
        # Filtrar datos por departamento seleccionado
        df_filtrado = df[df['Departamento_Vista'] == dept_sel].copy()

        # Seleccionamos y renombramos columnas para que la interfaz sea 100% en español
        # No incluimos el departamento porque ya está en el filtro superior
        df_display = df_filtrado[['EmployeeNumber', 'Cargo_Vista', 'PerformanceRating', 'JobInvolvement', 'YearsSinceLastPromotion', 'NumeroFaltas']].copy()
        df_display.columns = ['ID', 'Cargo', 'Desempeño', 'Compromiso', 'Años sin Promoción', 'Faltas']

        tab1, tab2 = st.tabs(["🔴 Riesgo de Estancamiento", "✨ Candidatos a Promoción"])

        with tab1:
            # Riesgo: 2 años o más sin ser promovidos
            df_riesgo = df_display[df_display['Años sin Promoción'] >= 2.0].sort_values('Años sin Promoción', ascending=False)
            if not df_riesgo.empty:
                st.error(f"Se han identificado {len(df_riesgo)} colaboradores con riesgo de desmotivación por estancamiento.")
                st.dataframe(df_riesgo, use_container_width=True, hide_index=True)
            else:
                st.success("¡Excelente! No hay colaboradores con estancamiento crítico en este departamento.")

        with tab2:
            # Potencial: Desempeño Alto (>=3), Compromiso Alto (>=3) y al menos 1 año en el puesto
            df_potencial = df_display[
                (df_display['Desempeño'] >= 3) & 
                (df_display['Compromiso'] >= 3) & 
                (df_display['Años sin Promoción'] >= 1.0)
            ].sort_values(['Desempeño', 'Años sin Promoción'], ascending=False)
            
            if not df_potencial.empty:
                st.info(f"Se han identificado {len(df_potencial)} colaboradores con alto potencial para ser promovidos o reconocidos.")
                st.dataframe(df_potencial, use_container_width=True, hide_index=True)
            else:
                st.write("No se encontraron colaboradores que cumplan simultáneamente con alto desempeño y compromiso en este periodo.")

if __name__ == '__main__':
    st.set_page_config(page_title="Gestión de Talento", layout="wide")
    render_recognition_page()