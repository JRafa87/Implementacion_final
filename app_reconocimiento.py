import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
from datetime import datetime, timedelta

# ==============================================================================
# 0. CONFIGURACIÓN Y CONEXIÓN A SUPABASE
# ==============================================================================

# Conexión a Supabase (usando la función especificada)
@st.cache_resource
def get_supabase() -> Optional[Client]:
    """Inicializa y cachea el cliente de Supabase. Requiere secrets.toml."""
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    
    if not url or not key:
        st.error("ERROR: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml. La aplicación no puede ejecutarse.")
        # Usamos st.stop() para detener la ejecución si no hay credenciales.
        st.stop() 
    
    try:
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}. Revise la URL y la clave.")
        st.stop() 

supabase = get_supabase()

# ==============================================================================
# 1. FUNCIONES DE DATOS (Solo fetch real)
# ==============================================================================

def fetch_employees_data():
    """Obtiene datos de empleados reales de la tabla 'empleados' de Supabase."""
    
    # Si la conexión falló antes (aunque st.stop() debería haberlo evitado), salimos.
    if supabase is None:
        return [] 
        
    try:
        # Columnas necesarias para el análisis de reconocimiento
        columns_to_fetch = [
            "EmployeeNumber", "Department", "JobRole", "PerformanceRating", 
            "YearsAtCompany", "YearsSinceLastPromotion", "JobInvolvement", 
            "RelationshipSatisfaction", "NumeroFaltas"
        ]
        
        cols_select = ", ".join(columns_to_fetch)
        
        response = supabase.table("empleados").select(cols_select).execute()
        
        # Mapea claves de Supabase (PascalCase) a claves de Python (minúsculas y acortadas)
        data = [{k.lower().replace("employeenumber", "id").replace("department", "depto").replace("jobrole", "puesto"): v for k, v in record.items()} for record in response.data]
        return data
    
    except Exception as e:
        st.error(f"Error crítico al ejecutar la consulta SQL: {e}. La tabla 'empleados' podría no existir o la estructura ser incorrecta.")
        st.stop()
        return []

@st.cache_data(ttl=300)
def get_employees_data_for_recognition():
    """Carga los datos de empleados, los limpia y los prepara para el display."""
    df_data = fetch_employees_data() 
    
    if not df_data:
        return pd.DataFrame()
        
    df = pd.DataFrame(df_data)
    
    # CRÍTICO: Limpieza de tipos y NaNs para la lógica de riesgo
    df['yearssincelastpromotion'] = pd.to_numeric(df['yearssincelastpromotion'], errors='coerce').fillna(0.0)
    df['performancerating'] = pd.to_numeric(df['performancerating'], errors='coerce').fillna(0)
    df['jobinvolvement'] = pd.to_numeric(df['jobinvolvement'], errors='coerce').fillna(0)
    df['relationshipsatisfaction'] = pd.to_numeric(df['relationshipsatisfaction'], errors='coerce').fillna(0)
    df['numerofaltas'] = pd.to_numeric(df['numerofaltas'], errors='coerce').fillna(0)
    
    return df

# ==============================================================================
# 2. LÓGICA DE CLASIFICACIÓN Y RIESGO
# ==============================================================================

def get_risk_by_promotion(df):
    """
    Calcula el número de empleados en riesgo (Crítico, Moderado, Bajo) por departamento,
    basado en YearsSinceLastPromotion.
    """
    def classify_risk(years):
        if years >= 3.0:
            return 'Critico'
        elif years >= 2.0:
            return 'Moderado'
        else:
            return 'Bajo'

    df['NivelRiesgo'] = df['yearssincelastpromotion'].apply(classify_risk)
    
    # Agrupar por departamento y contar las clasificaciones
    risk_summary = df.groupby('depto').agg(
        Critico=('NivelRiesgo', lambda x: (x == 'Critico').sum()),
        Moderado=('NivelRiesgo', lambda x: (x == 'Moderado').sum()),
        Bajo=('NivelRiesgo', lambda x: (x == 'Bajo').sum()),
        TotalEmpleados=('id', 'count'),
        PromedioAñosSPromocion=('yearssincelastpromotion', 'mean')
    ).reset_index()
    
    # Calcular el porcentaje de riesgo total (Crítico + Moderado)
    risk_summary['RiesgoTotal'] = risk_summary['Critico'] + risk_summary['Moderado']
    risk_summary['PorcentajeRiesgo'] = (risk_summary['RiesgoTotal'] / risk_summary['TotalEmpleados'] * 100).round(1)
    
    return risk_summary.sort_values(by='RiesgoTotal', ascending=False)

def display_employee_table(data):
    """Renderiza la tabla de empleados con variables clave y columna de acción."""
    
    display_cols = [
        'id', 'puesto', 'performancerating', 'yearsatcompany',
        'yearssincelastpromotion', 'jobinvolvement', 'numerofaltas'
    ]
    
    st.data_editor(
        data[display_cols],
        column_config={
            "id": "ID",
            "puesto": "Puesto",
            "performancerating": "Perf. Rating",
            "yearsatcompany": st.column_config.NumberColumn("Años Empresa", format="%.1f"),
            "yearssincelastpromotion": st.column_config.NumberColumn("⚠️ Años S/Prom.", format="%.1f"),
            "jobinvolvement": "Compromiso",
            "numerofaltas": "N° Faltas",
            "Acción": st.column_config.ButtonColumn("Acción Rápida", help="Registrar Reconocimiento", on_click=None, default='Reconocimiento')
        },
        disabled=display_cols, 
        hide_index=True,
        use_container_width=True
    )
    st.markdown("") 

# ==============================================================================
# 3. PÁGINA DE RECONOCIMIENTO (MAIN RENDER)
# ==============================================================================

def render_recognition_page(df, risk_df):
    """Renderiza la interfaz de Reconocimiento."""
    st.title("⭐ Reconocimiento y Desarrollo")
    st.markdown("Identificación de áreas con alto riesgo de estancamiento (`YearsSinceLastPromotion`) para acción proactiva.")
    
    # --- 1. Alertas Agregadas por Nivel de Riesgo (Accionable Directo) ---
    st.header("1. 🚨 Zonas de Intervención (Clasificación por Estancamiento)")

    criticas = risk_df[risk_df['Critico'] > 0]
    moderadas = risk_df[(risk_df['Moderado'] > 0) & (risk_df['Critico'] == 0)]
    bajo_riesgo = risk_df[risk_df['RiesgoTotal'] == 0]

    if not criticas.empty:
        st.error(
            f"🛑 **RIESGO CRÍTICO:** {criticas['Critico'].sum()} empleados en total (en {len(criticas)} áreas) llevan **más de 3 años** sin promoción. **Revisión INMEDIATA.**"
        )
    if not moderadas.empty:
        st.warning(
            f"⚠️ **RIESGO MODERADO:** {moderadas['Moderado'].sum()} empleados en total (en {len(moderadas)} áreas) llevan **2 a 3 años** sin promoción. Iniciar seguimiento de desarrollo."
        )
    if not criticas.empty or not moderadas.empty:
        pass 
    else:
        st.success(
            f"✅ **ESTADO ÓPTIMO:** Todas las áreas están bajo el umbral de riesgo de estancamiento. Refuerzo positivo."
        )
    
    st.markdown("---")

    # --- 2. Cuadro de Mandos Detallado ---
    st.header("2. 📊 Desglose del Estancamiento por Área")

    st.dataframe(
        risk_df.drop(columns=['RiesgoTotal']),
        use_container_width=True,
        hide_index=True,
        column_config={
            "depto": "Departamento",
            "Critico": "Empleados Críticos (>3A)",
            "Moderado": "Empleados Moderados (2-3A)",
            "Bajo": "Empleados en Meta (<2A)",
            "PromedioAñosSPromocion": st.column_config.NumberColumn(
                "Promedio Años S/Promoción", format="%.1f años"
            ),
            "PorcentajeRiesgo": st.column_config.ProgressColumn(
                "Riesgo Total (%)", format="%f%%", min_value=0, max_value=100
            )
        }
    )
    
    st.markdown("---")

    # --- 3. Detalle de Candidatos y Potenciales (Pestañas) ---
    st.header("3. 🔍 Detalle de Candidatos a Reconocimiento")
    
    department_options = risk_df['depto'].unique().tolist()
    dept_to_view = st.selectbox(
        "Seleccione el Departamento para auditar:", 
        options=["Seleccione un departamento"] + department_options,
        key="select_dept_audit"
    )

    if dept_to_view != "Seleccione un departamento":
        
        df_filtrado = df[df['depto'] == dept_to_view].copy()
        
        tab1, tab2 = st.tabs(["🔴 Riesgo y Estancamiento (>= 2 Años)", "✨ Alto Potencial y Oportunidad"])

        with tab1:
            st.subheader("Candidatos de Alto Riesgo / Estancamiento")
            UMBRAL_RIESGO = 2.0
            
            candidatos_riesgo = df_filtrado[df_filtrado['yearssincelastpromotion'] >= UMBRAL_RIESGO]
            
            if not candidatos_riesgo.empty:
                st.warning(f"Se encontraron **{len(candidatos_riesgo)}** empleados en riesgo de estancamiento en {dept_to_view}.")
                display_employee_table(candidatos_riesgo)
            else:
                st.info("No hay empleados en riesgo de estancamiento en este departamento.")

        with tab2:
            st.subheader("Potenciales Candidatos a Reconocimiento (Oportunidad)")
            
            # Criterio: 1 a 2 años S/Promoción Y buen desempeño (>= 3)
            candidatos_potenciales = df_filtrado[
                (df_filtrado['yearssincelastpromotion'] >= 1.0) & 
                (df_filtrado['yearssincelastpromotion'] < 2.0) &
                (df_filtrado['performancerating'] >= 3)
            ]
            
            if not candidatos_potenciales.empty:
                st.success(f"Se encontraron **{len(candidatos_potenciales)}** candidatos de alto potencial listos para ser reconocidos en {dept_to_view}.")
                display_employee_table(candidatos_potenciales)
            else:
                st.info("No hay candidatos de alto potencial identificados en este rango de oportunidad.")

# ==============================================================================
# 4. FUNCIÓN PRINCIPAL
# ==============================================================================

def main():
    st.set_page_config(layout="wide", page_title="Gestión de Reconocimiento")
    
    df = get_employees_data_for_recognition()
    
    if df.empty:
        # Si fetch_employees_data() ya ha fallado, la ejecución se detiene antes.
        # Si llega aquí, significa que la BD no devolvió filas.
        st.error("No se encontraron datos en la tabla 'empleados'. Verifique que la tabla contenga registros.")
        return

    # Calculamos la tabla de riesgo una sola vez
    risk_df = get_risk_by_promotion(df)
    
    # Renderizamos la página
    render_recognition_page(df, risk_df)

if __name__ == "__main__":
    main()