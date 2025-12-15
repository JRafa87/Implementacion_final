import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client, Client
from datetime import datetime

# =================================================================
# 1. CONFIGURACIÓN Y CONEXIÓN A SUPABASE (Usando st.secrets)
# =================================================================

@st.cache_resource
def get_supabase() -> Client:
    """Inicializa y cachea el cliente de Supabase."""
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("ERROR: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml. La autenticación fallará.")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

@st.cache_data(ttl=600)  # Almacenar en caché los datos por 10 minutos
def get_survey_data():
    """
    Consulta los datos de la tabla 'encuestas' usando el cliente de Supabase.
    """
    try:
        # Consulta: Traer todas las columnas de la tabla 'encuestas'
        # Usamos .select('*') y ordenamos por EmployeeNumber y Fecha
        response = supabase.table('encuestas').select('*').order('EmployeeNumber').order('Fecha').execute()
        
        data = response.data
        if not data:
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        
        # Asegurar el tipo de dato correcto para la fecha
        df['Fecha'] = pd.to_datetime(df['Fecha'])
        
        return df

    except Exception as e:
        st.error(f"❌ Error al consultar Supabase (Tabla 'encuestas'): {e}")
        return pd.DataFrame()


# =================================================================
# 2. FUNCIONES DE ANÁLISIS Y VISUALIZACIÓN
# =================================================================

def get_risk_analysis(employee_data: pd.DataFrame):
    """Calcula las alertas de riesgo para la última encuesta de un empleado."""
    if employee_data.empty:
        return {"riesgo": "N/A", "color": "blue", "señales": []}

    latest = employee_data.iloc[-1]
    signals = []

    # Reglas de Alertas (Usamos las escalas 1-4 o 1-5 que definiste)
    if latest['IntencionPermanencia'] <= 2:
        signals.append("Riesgo de Salida (IP <= 2)")
    if latest['ConfianzaEmpresa'] <= 2:
        signals.append("Desconfianza (CE <= 2)")
    if latest['CargaLaboralPercibida'] >= 4:
        signals.append("Agotamiento (CLP >= 4, Max 5)")
    if latest['SatisfaccionSalarial'] <= 1:
        signals.append("Problema Salarial (SS <= 1, Max 5)")

    # Nivel de Riesgo
    num_signals = len(signals)
    if num_signals >= 2:
        return {"riesgo": "CRÍTICO", "color": "#dc3545", "señales": signals} # Rojo
    elif num_signals == 1:
        return {"riesgo": "ADVERTENCIA", "color": "#ffc107", "señales": signals} # Amarillo
    else:
        return {"riesgo": "BAJO", "color": "#28a745", "señales": signals} # Verde

def create_radar_chart(latest_data: pd.Series):
    """Crea un gráfico de radar (Perfil de Satisfacción)"""
    categories = ['Ambiente', 'Involucramiento', 'Satisfacción Laboral', 
                  'Relación', 'Balance Vida/Trabajo', 'Confianza']
    values = [
        latest_data['EnvironmentSatisfaction'], latest_data['JobInvolvement'],
        latest_data['JobSatisfaction'], latest_data['RelationshipSatisfaction'],
        latest_data['WorkLifeBalance'], latest_data['ConfianzaEmpresa']
    ]
    
    fig = go.Figure(data=[
        go.Scatterpolar(r=values, theta=categories, fill='toself', mode='lines+markers',
                        line_color='darkblue', opacity=0.8)
    ])

    fig.update_layout(
        # La mayoría de las métricas están en escala 1-4, la Satisfacción Salarial y Carga Laboral están en 1-5,
        # Usaremos 1-5 en el rango máximo del radar para incluir a todas las variables
        polar=dict(radialaxis=dict(visible=True, range=[1, 5])), 
        showlegend=False,
        margin=dict(l=30, r=30, t=30, b=30),
        height=400,
        title_text="Perfil de Satisfacción Actual"
    )
    return fig

# =================================================================
# 3. MÓDULO PRINCIPAL DE STREAMLIT
# =================================================================

def historial_encuestas_module(df_maestro):
    """Renderiza el módulo 'Historial de Encuestas'."""
    st.title("👤 Módulo: Historial de Encuestas por Empleado")
    
    # --- 3.1 Filtro de Empleado ---
    unique_employees = sorted(df_maestro['EmployeeNumber'].unique())
    selected_employee = st.selectbox(
        "🔍 Selecciona el Número de Empleado:",
        options=unique_employees,
    )

    employee_data = df_maestro[df_maestro['EmployeeNumber'] == selected_employee].copy()
    
    latest_survey = employee_data.iloc[-1]
    risk_data = get_risk_analysis(employee_data)
    
    # --- 3.2 Tarjeta de Alerta (Diagnóstico Rápido) ---
    st.markdown("---")
    col_risk, col_signals = st.columns([1, 3])
    
    with col_risk:
        # Tarjeta de Riesgo (HTML para el color de fondo)
        st.markdown(f"""
            <div style="background-color:{risk_data['color']}; color:white; padding: 15px; border-radius: 10px; text-align: center;">
                <h4>RIESGO: {risk_data['riesgo']}</h4>
            </div>
        """, unsafe_allow_html=True)
        st.info(f"Última Encuesta: **{latest_survey['Fecha'].strftime('%d/%m/%Y')}**")
        
    with col_signals:
        st.subheader("🛑 Señales de Alerta Activas")
        if risk_data['señales']:
            for signal in risk_data['señales']:
                st.error(f"**{signal}**")
        else:
            st.success("🎉 No se detectaron señales de riesgo crítico.")
            
    st.markdown("---")

    # --- 3.3 Gráficos (Radar y Trayectoria) ---
    col_radar, col_line = st.columns(2)
    
    with col_radar:
        st.subheader("Perfil de Satisfacción Actual")
        st.plotly_chart(create_radar_chart(latest_survey), use_container_width=True)
        # 

    with col_line:
        st.subheader("Trayectoria de Intención de Permanencia")
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=employee_data['Fecha'], y=employee_data['IntencionPermanencia'], 
            mode='lines+markers', name='Intención de Permanencia'
        ))
        
        # Línea de Umbral de Riesgo (Intención <= 2)
        fig_line.add_shape(type="line", x0=employee_data['Fecha'].min(), y0=2, 
                           x1=employee_data['Fecha'].max(), y1=2,
                           line=dict(color="Red", width=2, dash="dash"))
                           
        fig_line.update_layout(
            yaxis=dict(range=[0.5, 4.5], tickmode='linear', dtick=1), # IP es escala 1-4
            title='Evolución de Intención de Permanencia (1=Bajo, 4=Alto)',
            margin=dict(l=30, r=30, t=30, b=30),
            height=400
        )
        st.plotly_chart(fig_line, use_container_width=True)
        # 
        
    st.markdown("---")

    # --- 3.4 Tabla de Datos Crudos con Formato Condicional ---
    st.header("📜 Datos Históricos (Crudos)")
    
    def highlight_risk(s):
        """Resalta en rojo los valores críticos."""
        # Rojo para satisfacción <= 2 y Carga Laboral >= 4
        is_low_sat = (s <= 2) & s.index.isin(['IntencionPermanencia', 'JobSatisfaction', 'SatisfaccionSalarial', 'ConfianzaEmpresa'])
        is_high_carga = (s >= 4) & (s.index == 'CargaLaboralPercibida')
        
        return ['background-color: #f8d7da' if v else '' for v in (is_low_sat | is_high_carga)]

    display_cols = ['Fecha', 'IntencionPermanencia', 'ConfianzaEmpresa', 'CargaLaboralPercibida', 'SatisfaccionSalarial', 'JobSatisfaction', 'WorkLifeBalance', 'JobInvolvement', 'EnvironmentSatisfaction']
    table_data = employee_data[display_cols]
    
    st.dataframe(
        table_data.style.apply(highlight_risk, axis=1), 
        use_container_width=True,
        hide_index=True,
        column_order=display_cols
    )

# =================================================================
# 4. EJECUCIÓN DEL SCRIPT
# =================================================================

if __name__ == '__main__':
    st.set_page_config(layout="wide", page_title="Historial de Encuestas")
    
    # 1. Cargar datos
    df_maestro = get_survey_data()
    
    if not df_maestro.empty:
        # 2. Renderizar el módulo
        historial_encuestas_module(df_maestro)
    else:
        # El mensaje de error ya se muestra en get_survey_data
        st.warning("Verifica la configuración de Streamlit secrets y la conexión a Supabase.")