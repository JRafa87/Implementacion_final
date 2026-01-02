import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional, Dict
import warnings

warnings.filterwarnings("ignore")

# ==============================================================================
# 0. DICCIONARIOS DE TRADUCCIÓN (Basados en tu tabla consolidado)
# ==============================================================================

TRAD_DEPTO = {
    "HR": "Recursos Humanos",
    "RESEARCH_AND_DEVELOPMENT": "I+D",
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
# 1. CONFIGURACIÓN Y CONEXIÓN
# ==============================================================================

@st.cache_resource
def get_supabase() -> Optional[Client]:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("Faltan credenciales de Supabase.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

# ==============================================================================
# 2. FUNCIONES DE DATOS
# ==============================================================================

def fetch_employees_data():
    if supabase is None: return [] 
    try:
        # Ahora incluimos JobInvolvement ya que existe en tu tabla
        columns_to_fetch = [
            "EmployeeNumber", "Department", "JobRole", "PerformanceRating", 
            "YearsAtCompany", "YearsSinceLastPromotion", "NumeroFaltas", "JobInvolvement"
        ]
        cols_select = ", ".join(columns_to_fetch)
        response = supabase.table("consolidado").select(cols_select).execute()
        
        # Mapeo y Traducción inmediata
        data = []
        for r in response.data:
            dept_orig = r.get("Department", "")
            puesto_orig = r.get("JobRole", "")
            
            data.append({
                "id": r.get("EmployeeNumber"),
                "depto": TRAD_DEPTO.get(dept_orig, dept_orig), # Traduce o deja original
                "puesto": TRAD_PUESTO.get(puesto_orig, puesto_orig),
                "performancerating": r.get("PerformanceRating"),
                "yearsatcompany": r.get("YearsAtCompany"),
                "yearssincelastpromotion": r.get("YearsSinceLastPromotion"),
                "numerofaltas": r.get("NumeroFaltas"),
                "jobinvolvement": r.get("JobInvolvement") # Ahora viene de la DB
            })
        return data
    except Exception as e:
        st.error(f"Error al obtener datos: {e}")
        return []

@st.cache_data(ttl=300)
def get_employees_data_for_recognition():
    df_data = fetch_employees_data() 
    if not df_data: return pd.DataFrame()
    df = pd.DataFrame(df_data)
    
    # Limpieza de tipos
    numeric_cols = ['yearssincelastpromotion', 'performancerating', 'numerofaltas', 'jobinvolvement', 'yearsatcompany']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    return df

# ==============================================================================
# 3. LÓGICA DE CLASIFICACIÓN
# ==============================================================================

def get_risk_by_promotion(df):
    def classify_risk(years):
        if years >= 3.0: return 'Critico'
        elif years >= 2.0: return 'Moderado'
        else: return 'Bajo'

    df['NivelRiesgo'] = df['yearssincelastpromotion'].apply(classify_risk)
    
    risk_summary = df.groupby('depto').agg(
        Critico=('NivelRiesgo', lambda x: (x == 'Critico').sum()),
        Moderado=('NivelRiesgo', lambda x: (x == 'Moderado').sum()),
        Bajo=('NivelRiesgo', lambda x: (x == 'Bajo').sum()),
        TotalEmpleados=('id', 'count'),
        PromedioAñosSPromocion=('yearssincelastpromotion', 'mean')
    ).reset_index()
    
    risk_summary['RiesgoTotal'] = risk_summary['Critico'] + risk_summary['Moderado']
    risk_summary['PorcentajeRiesgo'] = (risk_summary['RiesgoTotal'] / risk_summary['TotalEmpleados'] * 100).round(1)
    
    return risk_summary.sort_values(by='RiesgoTotal', ascending=False)

def display_employee_table(data):
    """Tabla en español con Compromiso real."""
    display_cols = [
        'id', 'puesto', 'performancerating', 'yearsatcompany',
        'yearssincelastpromotion', 'jobinvolvement', 'numerofaltas'
    ]
    
    st.data_editor(
        data[display_cols],
        column_config={
            "id": "ID Empleado",
            "puesto": "Cargo / Puesto",
            "performancerating": "Desempeño",
            "yearsatcompany": st.column_config.NumberColumn("Años Empresa", format="%.1f"),
            "yearssincelastpromotion": st.column_config.NumberColumn("⚠️ Años S/Promoción", format="%.1f"),
            "jobinvolvement": "Nivel Compromiso",
            "numerofaltas": "N° Faltas",
        },
        disabled=display_cols, 
        hide_index=True,
        use_container_width=True
    )

# ==============================================================================
# 4. UI - RECONOCIMIENTO
# ==============================================================================

def render_recognition_page(): 
    st.title("⭐ Reconocimiento y Desarrollo")
    
    df = get_employees_data_for_recognition()
    if df.empty:
        st.warning("No hay datos disponibles para mostrar.")
        return

    risk_df = get_risk_by_promotion(df.copy()) 

    st.markdown("Identificación de áreas con alto riesgo de estancamiento para acción proactiva.")
    
    # --- 1. Alertas ---
    st.header("1. 🚨 Zonas de Intervención")
    criticas = risk_df[risk_df['Critico'] > 0]
    moderadas = risk_df[(risk_df['Moderado'] > 0) & (risk_df['Critico'] == 0)]
    
    if not criticas.empty:
        st.error(f"🛑 **RIESGO CRÍTICO:** {criticas['Critico'].sum()} empleados llevan **más de 3 años** sin promoción.")
    if not moderadas.empty:
        st.warning(f"⚠️ **RIESGO MODERADO:** {moderadas['Moderado'].sum()} empleados llevan **2 a 3 años** sin promoción.")
    
    st.divider()

    # --- 2. Tabla de Áreas ---
    st.header("2. 📊 Desglose por Departamento")
    st.dataframe(
        risk_df.drop(columns=['RiesgoTotal']),
        use_container_width=True,
        hide_index=True,
        column_config={
            "depto": "Departamento",
            "Critico": "Críticos (>3A)",
            "Moderado": "Moderados (2-3A)",
            "Bajo": "En Meta (<2A)",
            "PromedioAñosSPromocion": st.column_config.NumberColumn("Promedio Años", format="%.1f años"),
            "PorcentajeRiesgo": st.column_config.ProgressColumn("Riesgo Total (%)", format="%f%%", min_value=0, max_value=100)
        }
    )
    
    st.divider()

    # --- 3. Auditoría por Depto ---
    st.header("3. 🔍 Auditoría de Colaboradores")
    
    dept_to_view = st.selectbox(
        "Seleccione el Departamento para auditar:", 
        options=["--- Seleccionar ---"] + sorted(df['depto'].unique().tolist()),
    )

    if dept_to_view != "--- Seleccionar ---":
        df_filtrado = df[df['depto'] == dept_to_view].copy()
        t1, t2 = st.tabs(["🔴 Estancamiento", "✨ Alto Potencial"])

        with t1:
            candidatos_riesgo = df_filtrado[df_filtrado['yearssincelastpromotion'] >= 2.0]
            if not candidatos_riesgo.empty:
                st.info(f"Colaboradores con 2 o más años sin ascensos en {dept_to_view}:")
                display_employee_table(candidatos_riesgo)
            else:
                st.success("No hay casos críticos en esta área.")

        with t2:
            # Candidatos con buen desempeño y tiempo prudente
            candidatos_potenciales = df_filtrado[
                (df_filtrado['yearssincelastpromotion'] >= 1.0) & 
                (df_filtrado['performancerating'] >= 3)
            ]
            if not candidatos_potenciales.empty:
                st.success(f"Candidatos para programa de reconocimiento en {dept_to_view}:")
                display_employee_table(candidatos_potenciales)
            else:
                st.info("No se identificaron candidatos con el perfil de alto potencial hoy.")