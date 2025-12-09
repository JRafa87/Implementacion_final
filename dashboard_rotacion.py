import streamlit as st
import pandas as pd
import plotly.express as px
from lifelines import KaplanMeierFitter
import matplotlib.pyplot as plt
import io
from supabase import create_client, Client
from typing import Optional
from datetime import date

# ==============================================================================
# 0. CONFIGURACIÓN, CONEXIÓN Y DATOS
# ==============================================================================

# Definición de fecha actual constante para consistencia en el cálculo de antigüedad
FECHA_ACTUAL = pd.to_datetime(date.today())

@st.cache_resource
def get_supabase() -> Optional[Client]:
    """Inicializa y cachea el cliente de Supabase."""
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    
    if not url or not key:
        st.error("ERROR: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml.")
        return None
    
    try:
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}.")
        return None

supabase = get_supabase()

@st.cache_data(ttl=3600)
def get_employees_data_for_dashboard():
    """Carga, limpia y prepara los datos desde la tabla 'consolidado'."""
    if supabase is None:
        return pd.DataFrame() 
        
    try:
        response = supabase.table("consolidado").select("*").execute()
        df = pd.DataFrame(response.data)
        
        # --- Limpieza y Conversión ---
        df['FechaIngreso'] = pd.to_datetime(df['FechaIngreso'], errors='coerce')
        df['FechaSalida'] = pd.to_datetime(df['FechaSalida'], errors='coerce')
        
        # 1. Definir la Fecha de Referencia para Empleados Activos (Censura a la Derecha)
        # Asumimos que si FechaSalida es NULL, Attrition es 'No'.
        if 'Attrition' not in df.columns:
            df['Attrition'] = df['FechaSalida'].apply(lambda x: 'No' if pd.isna(x) else 'Yes')

        df['FechaSalida'] = df.apply(
            lambda row: FECHA_ACTUAL if pd.isna(row['FechaSalida']) and row['Attrition'] == 'No' else row['FechaSalida'], 
            axis=1
        )

        # 2. Cálculo de Duración y Evento de Renuncia
        df['DuracionDias'] = (df['FechaSalida'] - df['FechaIngreso']).dt.days
        df['EventoRenuncia'] = df['Attrition'].apply(lambda x: 1 if x == 'Yes' else 0)
        df['AntigüedadAños'] = df['DuracionDias'] / 365
        
        # 3. Limpieza de columnas clave (Aseguramos que sean numéricas)
        cols_to_clean = ['YearsSinceLastPromotion', 'JobSatisfaction', 'Age', 'MonthlyIncome', 
                         'RelationshipSatisfaction', 'JobInvolvement', 'DistanceFromHome']
        for col in cols_to_clean:
            if col in df.columns:
                 df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                 
        # 4. Renombrar Columnas (para gráficos en español y uso interno)
        df = df.rename(columns={
            'Department': 'Departamento', 
            'JobRole': 'Puesto',
            'MaritalStatus': 'EstadoCivil',
            'MonthlyIncome': 'IngresoMensual'
        })
                 
        return df.dropna(subset=['FechaIngreso', 'FechaSalida']) 

    except Exception as e:
        st.error(f"Error al cargar datos del dashboard: {e}")
        return pd.DataFrame()

# ==============================================================================
# 1. FUNCIONES AUXILIARES DE DISEÑO
# ==============================================================================

MESES_ESPANOL = {1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun', 
                 7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'}

def filter_data(df, genero, departamento):
    """Aplica filtros de género y departamento a un DataFrame."""
    df_filtered = df.copy()
    if genero != 'All':
        df_filtered = df_filtered[df_filtered['Gender'] == genero]
    if departamento != 'All':
        df_filtered = df_filtered[df_filtered['Departamento'] == departamento]
    return df_filtered

def render_kpi_card(title, value, unit, color):
    """Renderiza una tarjeta de KPI con formato HTML."""
    st.markdown(f"""
    <div style='
        background-color: #ffffff; 
        padding: 15px; 
        border-radius: 10px; 
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        border-left: 5px solid {color};
        margin-bottom: 10px;
    '>
        <h5 style='color: #808080; text-align: left; margin: 0; font-size: 14px;'>{title}</h5>
        <p style='font-size: 28px; font-weight: bold; text-align: left; margin-top: 5px; color: #333;'>
            {round(value, 2)}{unit}
        </p>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. FUNCIÓN PRINCIPAL DEL DASHBOARD (MÓDULO)
# ==============================================================================

def render_rotacion_dashboard():
    # 🚨 CORRECCIÓN CRÍTICA: Se elimina st.set_page_config de aquí. 
    # Debe estar solo en el archivo principal (app.py)

    data = get_employees_data_for_dashboard()
    
    if data.empty:
        st.error("No se pudieron cargar datos. No se puede renderizar el dashboard.")
        return

    data_renuncias = data[data['Attrition'] == 'Yes'].copy()

    st.title("🔥 Dashboard de Rotación y Retención")
    st.markdown("---")

    # --- A. FILTROS GLOBALES (Usando st.sidebar para que sean parte de la barra principal) ---
    st.sidebar.header("🎯 Filtros de Segmentación")

    # Usamos keys para evitar conflictos de widgets entre páginas.
    genero = st.sidebar.selectbox("Filtro por Género", ['All'] + list(data['Gender'].unique()), key='db_genero')
    departamento = st.sidebar.selectbox("Filtro por Departamento", ['All'] + list(data['Departamento'].unique()), key='db_depto')

    data_filtered_general = filter_data(data, genero, departamento)
    data_filtered_renuncias = filter_data(data_renuncias, genero, departamento)

    # --- B. KPIs Y MÉTRICAS CLAVE ---
    st.header("1. Métricas Clave y Resumen")

    tasa_rotacion = (data_filtered_renuncias.shape[0] / data_filtered_general.shape[0]) * 100 if data_filtered_general.shape[0] > 0 else 0
    promedio_antiguedad = data_filtered_renuncias['AntigüedadAños'].mean() if not data_filtered_renuncias.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("Empleados Totales", data_filtered_general.shape[0], "", "#6495ED")
    with col2:
        render_kpi_card("Total Renuncias", data_filtered_renuncias.shape[0], " personas", "#FF5733")
    with col3:
        render_kpi_card("Tasa de Rotación", tasa_rotacion, "%", "#4CAF50")
    with col4:
        render_kpi_card("Antigüedad Prom. Rotación", promedio_antiguedad, " años", "#FFA07A")

    st.markdown("---")

    # ==============================================================================
    # 3. ANÁLISIS DE SUPERVIVENCIA
    # ==============================================================================

    st.header("2. 📈 Análisis de Retención (Kaplan-Meier)")
    st.markdown("Muestra la **probabilidad de permanencia** en el tiempo, segmentado por un factor de riesgo. ")

    col_km_plot, col_km_control = st.columns([2, 1])

    with col_km_control:
        st.subheader("Segmentación KM")
        survival_factor = st.selectbox(
            "Segmentar por:",
            options=['Departamento', 'Puesto', 'EstadoCivil', 'Gender', 'YearsSinceLastPromotion'],
            index=0,
            key='km_factor'
        )
        st.info(f"Compara el riesgo de rotación por **{survival_factor}**.")

    with col_km_plot:
        fig_seg, ax_seg = plt.subplots(figsize=(12, 6))
        kmf = KaplanMeierFitter()
        
        try:
            for name, grouped_df in data_filtered_general.groupby(survival_factor):
                if not grouped_df.empty:
                    # Usar DuracionDias y EventoRenuncia calculados
                    kmf.fit(grouped_df['DuracionDias'], event_observed=grouped_df['EventoRenuncia'], label=name)
                    kmf.plot(ax=ax_seg, ci_show=False)
                
            ax_seg.set_title(f'Curvas de Retención Segmentadas por {survival_factor}', fontsize=16)
            ax_seg.set_xlabel('Tiempo de Permanencia (días)', fontsize=12)
            ax_seg.set_ylabel('Probabilidad de Retención', fontsize=12)
            ax_seg.grid(True, linestyle='--', alpha=0.6)
            plt.legend(title=survival_factor, loc='upper right', fontsize=10)
            
            buf_seg = io.BytesIO()
            fig_seg.savefig(buf_seg, format='png', bbox_inches='tight')
            st.image(buf_seg.getvalue(), use_column_width=True)
            plt.close(fig_seg)
        except Exception as e:
            st.warning(f"No se pudo generar el gráfico de Supervivencia: {e}")

    st.markdown("---")

    # ==============================================================================
    # 4. ANÁLISIS DE FACTORES Y DEMOGRAFÍA
    # ==============================================================================

    st.header("3. 🎯 Análisis de Compensación y Factores de Riesgo")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Riesgo Salarial (Distribución)")
        
        # BOX PLOT de Ingreso Mensual (Análisis Comparativo)
        if 'IngresoMensual' in data_filtered_general.columns:
            fig_income_box = px.box(
                data_filtered_general, 
                x='Attrition', 
                y='IngresoMensual', 
                color='Attrition',
                title="Distribución de Ingresos Mensuales",
                labels={'Attrition': 'Estado', 'IngresoMensual': 'Ingreso Mensual'},
                color_discrete_map={'Yes': '#FF5733', 'No': '#4CAF50'}
            )
            fig_income_box.update_xaxes(title_text='Estado del Empleado')
            st.plotly_chart(fig_income_box, use_container_width=True)
        else:
            st.info("Faltan datos de Ingreso Mensual para el Box Plot.")
        
        # SCATTER PLOT de Ingreso Mensual vs. Edad (Análisis Contextual)
        if 'IngresoMensual' in data_filtered_general.columns and 'Age' in data_filtered_general.columns:
            fig_scatter = px.scatter(
                data_filtered_general, 
                x='Age', 
                y='IngresoMensual', 
                color='Attrition',
                title="Ingreso Mensual vs. Edad por Estado",
                labels={'Attrition': 'Estado', 'IngresoMensual': 'Ingreso Mensual', 'Age': 'Edad'},
                color_discrete_map={'Yes': '#FF5733', 'No': '#4CAF50'}, 
                opacity=0.6,
                hover_data=['Puesto', 'Departamento']
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("Faltan datos de Ingreso Mensual y/o Edad para el Scatter Plot.")


    with col_right:
        st.subheader("Factores Críticos y Tendencia")

        # Renuncias por Puesto de Trabajo
        renuncias_jobrole = data_filtered_renuncias['Puesto'].value_counts().reset_index()
        renuncias_jobrole.columns = ['Puesto', 'Renuncias']
        fig_jr = px.bar(
            renuncias_jobrole.head(7), 
            x='Puesto', 
            y='Renuncias', 
            title="Top Puestos con Mayor Rotación",
            color='Renuncias',
            color_continuous_scale=px.colors.sequential.Sunsetdark
        )
        st.plotly_chart(fig_jr, use_container_width=True)
        
        # Renuncias por Años Desde Última Promoción
        ultima_promocion = data_filtered_renuncias['YearsSinceLastPromotion'].value_counts().reset_index()
        ultima_promocion.columns = ['Años S/Promoción', 'Renuncias']
        fig_promo = px.bar(
            ultima_promocion.sort_values('Años S/Promoción', ascending=False).head(5), 
            x='Años S/Promoción', 
            y='Renuncias', 
            title="Renuncias por Estancamiento",
            color_discrete_sequence=['#FF8C00']
        )
        st.plotly_chart(fig_promo, use_container_width=True)


    # ==============================================================================
    # 5. ANÁLISIS DE TENDENCIA SECUNDARIO
    # ==============================================================================

    st.markdown("---")
    st.header("4. 🗓️ Clima Laboral y Antigüedad")
    
    col_trend_left, col_trend_right = st.columns(2)

    with col_trend_left:
        st.subheader("Satisfacción y Clima Laboral")
        # Renuncias por Satisfacción Laboral
        carga_laboral = data_filtered_renuncias['JobSatisfaction'].value_counts().reset_index()
        carga_laboral.columns = ['Satisfacción Laboral', 'Renuncias']
        carga_laboral['Satisfacción Laboral'] = carga_laboral['Satisfacción Laboral'].astype(str)
        fig_sat = px.bar(
            carga_laboral.sort_values('Satisfacción Laboral'), 
            x='Satisfacción Laboral', 
            y='Renuncias', 
            title="Impacto de la Satisfacción Laboral (1=Baja, 4=Alta)",
            color='Renuncias',
            color_continuous_scale=px.colors.sequential.Plasma
        )
        st.plotly_chart(fig_sat, use_container_width=True)

    with col_trend_right:
        st.subheader("Distribución de Antigüedad")
        # Distribución de Antigüedad al Renunciar
        fig_hist = px.histogram(
            data_filtered_renuncias, 
            x='AntigüedadAños', 
            nbins=20, 
            title="Distribución de Antigüedad al Renunciar",
            color_discrete_sequence=['#3CB371']
        )
        fig_hist.update_layout(xaxis_title="Antigüedad (Años)")
        st.plotly_chart(fig_hist, use_container_width=True)