import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from typing import Optional
from datetime import date

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y DATOS
# ==============================================================================

st.set_page_config(page_title="Dashboard de Rotación", layout="wide")
FECHA_ACTUAL = pd.to_datetime(date.today())

@st.cache_resource
def get_supabase() -> Optional[Client]:
    """Establece la conexión con la base de datos Supabase."""
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key) if url and key else None

supabase = get_supabase()

@st.cache_data(ttl=3600)
def load_data():
    """Carga y procesa los datos desde Supabase con traducciones."""
    response = supabase.table("consolidado").select("*").execute()
    df = pd.DataFrame(response.data)

    # Procesamiento de Fechas
    df['FechaIngreso'] = pd.to_datetime(df['FechaIngreso'], errors='coerce')
    df['FechaSalida'] = pd.to_datetime(df['FechaSalida'], errors='coerce')

    # 1. TRADUCCIÓN DE DATOS (Mapeo Inglés -> Español)
    if 'Gender' in df.columns:
        df['Gender'] = df['Gender'].map({
            'Male': 'Masculino', 
            'Female': 'Femenino', 
            'Non-binary': 'No binario'
        }).fillna(df['Gender'])

    # 2. TRADUCCIÓN DE COLUMNAS (Para manejo interno y visual)
    df = df.rename(columns={
        'Department': 'Departamento',
        'JobRole': 'Puesto',
        'MonthlyIncome': 'IngresoMensual',
        'Age': 'Edad',
        'YearsSinceLastPromotion': 'AnosUltimaPromocion',
        'JobSatisfaction': 'SatisfaccionLaboral'
    })

    # Lógica de Attrition (Si no existe, se calcula por Fecha de Salida)
    if 'Attrition' not in df.columns:
        df['Attrition'] = df['FechaSalida'].apply(lambda x: 'No' if pd.isna(x) else 'Yes')

    df['FechaSalida'] = df.apply(
        lambda r: FECHA_ACTUAL if pd.isna(r['FechaSalida']) and r['Attrition'] == 'No' else r['FechaSalida'],
        axis=1
    )

    # Cálculo de métricas de tiempo
    df['DuracionDias'] = (df['FechaSalida'] - df['FechaIngreso']).dt.days
    df['AntiguedadMeses'] = df['DuracionDias'] / 30

    # Mapeo de contexto humano
    df['EstadoEmpleado'] = df['Attrition'].map({
        'Yes': 'Renunció',
        'No': 'Permanece'
    })

    return df.dropna(subset=['FechaIngreso'])

# ==============================================================================
# 2. RENDERIZADO DEL DASHBOARD
# ==============================================================================

def render_rotacion_dashboard():
    # Títulos
    st.title("📊 Análisis Descriptivo de Rotación de Personal")
    st.caption("Análisis histórico basado en datos de Supabase • Interfaz en Español")
    
    data = load_data()

    if data.empty:
        st.error("No se pudieron cargar los datos desde la base de datos.")
        return

    # --- PANEL DE FILTROS SUPERIORES ---
    st.markdown("### 🎯 Filtros de Visualización")
    c_filt1, c_filt2, c_filt3 = st.columns(3)

    with c_filt1:
        genero = st.selectbox(
            "Filtrar por Género:",
            ['Todos'] + sorted(data['Gender'].dropna().unique().tolist())
        )

    with c_filt2:
        departamento = st.selectbox(
            "Filtrar por Departamento:",
            ['Todos'] + sorted(data['Departamento'].dropna().unique().tolist())
        )
    
    with c_filt3:
        # Filtro de búsqueda por puesto
        puesto = st.selectbox(
            "Filtrar por Puesto:",
            ['Todos'] + sorted(data['Puesto'].dropna().unique().tolist())
        )

    # Aplicar Filtros
    data_filtered = data.copy()
    if genero != 'Todos':
        data_filtered = data_filtered[data_filtered['Gender'] == genero]
    if departamento != 'Todos':
        data_filtered = data_filtered[data_filtered['Departamento'] == departamento]
    if puesto != 'Todos':
        data_filtered = data_filtered[data_filtered['Puesto'] == puesto]

    data_renuncias = data_filtered[data_filtered['EstadoEmpleado'] == 'Renunció']

    st.markdown("---")

    # --- BLOQUE DE KPIs ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 Empleados Totales", len(data_filtered))
    col2.metric("🚪 Total Renuncias", len(data_renuncias))
    
    tasa_rotacion = (len(data_renuncias) / len(data_filtered) * 100) if len(data_filtered) > 0 else 0
    col3.metric("📉 Tasa de Rotación", f"{tasa_rotacion:.1f}%")

    if not data_renuncias.empty:
        col4.metric("⏱️ Promedio Meses de Salida", f"{data_renuncias['AntiguedadMeses'].mean():.1f}")
    else:
        col4.metric("⏱️ Promedio Meses de Salida", "—")

    st.markdown("---")

    # --- BLOQUE 1: ¿CUÁNDO Y EN QUÉ ETAPA? ---
    st.subheader("🔥 Análisis Crítico de Permanencia")
    col_a, col_b = st.columns(2)

    with col_a:
        # Histograma de antigüedad
        fig_hist = px.histogram(
            data_renuncias,
            x='AntiguedadMeses',
            nbins=20,
            title="Distribución de renuncias por meses",
            labels={'AntiguedadMeses': 'Meses en la empresa', 'count': 'Número de renuncias'},
            color_discrete_sequence=['#E74C3C']
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_b:
        # Tramos de antigüedad
        bins = [0, 6, 12, 24, 60]
        labels_tramos = ['0–6 meses', '6–12 meses', '1–2 años', '2–5 años']
        data_filtered['TramoAntiguedad'] = pd.cut(data_filtered['AntiguedadMeses'], bins=bins, labels=labels_tramos)
        
        total_tramo = data_filtered['TramoAntiguedad'].value_counts().sort_index()
        renuncias_tramo = data_renuncias['TramoAntiguedad'].value_counts().reindex(labels_tramos).fillna(0)
        porcentaje_tramo = (renuncias_tramo / total_tramo * 100).reset_index()
        porcentaje_tramo.columns = ['Tramo', '% de Salidas']

        fig_tramos = px.bar(
            porcentaje_tramo,
            x='Tramo', y='% de Salidas',
            title="Riesgo de salida según etapa laboral",
            text='% de Salidas',
            color='% de Salidas',
            color_continuous_scale='Reds',
            labels={'% de Salidas': 'Tasa de bajas (%)'}
        )
        fig_tramos.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        st.plotly_chart(fig_tramos, use_container_width=True)

    # --- BLOQUE 2: ¿DÓNDE Y POR QUÉ? ---
    st.markdown("---")
    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("🟥 Rotación por Departamento")
        tasa_depto = (
            data.groupby('Departamento')['EstadoEmpleado']
            .apply(lambda x: (x == 'Renunció').mean() * 100)
            .reset_index(name='TasaRotacion')
            .sort_values('TasaRotacion', ascending=True)
        )
        fig_depto = px.bar(
            tasa_depto, x='TasaRotacion', y='Departamento',
            orientation='h',
            title="Departamentos con mayor índice de rotación",
            labels={'TasaRotacion': 'Tasa (%)', 'Departamento': ''},
            color='TasaRotacion',
            color_continuous_scale='Reds'
        )
        st.plotly_chart(fig_depto, use_container_width=True)

    with col_d:
        st.subheader("💰 Ingresos vs Edad")
        fig_scatter = px.scatter(
            data_filtered, x='Edad', y='IngresoMensual',
            color='EstadoEmpleado',
            labels={'Edad': 'Edad', 'IngresoMensual': 'Sueldo Mensual', 'EstadoEmpleado': 'Situación'},
            color_discrete_map={'Renunció': '#E74C3C', 'Permanece': '#2ECC71'},
            opacity=0.6,
            hover_data=['Puesto', 'Departamento']
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    # --- BLOQUE 3: TENDENCIA TEMPORAL ---
    st.markdown("---")
    st.subheader("📆 Evolución de Salidas en el Tiempo")
    renuncias_mes = (
        data_renuncias
        .groupby(pd.Grouper(key='FechaSalida', freq='M'))
        .size()
        .reset_index(name='Renuncias')
    )
    fig_tiempo = px.line(
        renuncias_mes, x='FechaSalida', y='Renuncias',
        markers=True,
        title="Tendencia mensual de renuncias registradas",
        labels={'FechaSalida': 'Mes de Salida', 'Renuncias': 'Cantidad'}
    )
    st.plotly_chart(fig_tiempo, use_container_width=True)

    # --- LECTURA EJECUTIVA ---
    st.markdown("---")
    st.subheader("🧠 Conclusiones del Análisis")
    
    pct_primer_ano = (data_renuncias['AntiguedadMeses'] <= 12).mean() * 100
    depto_max = tasa_depto.iloc[-1]['Departamento'] if not tasa_depto.empty else "N/A"

    st.info(
        f"✅ **Análisis de Onboarding:** El **{pct_primer_ano:.0f}%** de las salidas ocurren en el primer año. "
        f"Se recomienda reforzar el proceso de inducción.\n\n"
        f"✅ **Área Crítica:** El departamento de **{depto_max}** presenta la mayor vulnerabilidad actual.\n\n"
        f"✅ **Factores Económicos:** Se observa una correlación entre salarios en niveles iniciales y la decisión de salida."
    )

if __name__ == "__main__":
    render_rotacion_dashboard()
