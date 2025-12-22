import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from typing import Optional
from datetime import date

# ==============================================================================
# 1. CONFIGURACIÓN Y CONEXIÓN (CAPA DE DATOS)
# ==============================================================================

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
    """Carga y procesa los datos desde la tabla 'consolidado'."""
    response = supabase.table("consolidado").select("*").execute()
    df = pd.DataFrame(response.data)

    # Procesamiento de Fechas
    df['FechaIngreso'] = pd.to_datetime(df['FechaIngreso'], errors='coerce')
    df['FechaSalida'] = pd.to_datetime(df['FechaSalida'], errors='coerce')

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

    # Normalización de nombres de columnas
    df = df.rename(columns={
        'Department': 'Departamento',
        'JobRole': 'Puesto',
        'MonthlyIncome': 'IngresoMensual'
    })

    return df.dropna(subset=['FechaIngreso'])

# ==============================================================================
# 2. RENDERIZADO DEL DASHBOARD (CAPA DE INTERFAZ)
# ==============================================================================

def render_rotacion_dashboard():
    st.title("📊 Análisis Descriptivo de Rotación de Personal")
    st.caption("Dashboard descriptivo – análisis histórico basado en datos de Supabase")
    st.markdown("---")

    # 1. CARGA DE DATOS
    data = load_data()

    if data.empty:
        st.error("No se pudieron cargar los datos desde Supabase.")
        return

    # --- CORRECCIÓN CLAVE: Crear tramos ANTES de filtrar o separar datasets ---
    bins = [0, 6, 12, 24, 60]
    labels_tramos = ['0–6 meses', '6–12 meses', '1–2 años', '2–5 años']
    
    # Creamos la columna en el dataframe base
    data['TramoAntiguedad'] = pd.cut(
        data['AntiguedadMeses'], 
        bins=bins, 
        labels=labels_tramos
    )
    # -----------------------------------------------------------------------


    # Normalizar estado del empleado
    data['EstadoEmpleado'] = data['EstadoEmpleado'].fillna('Permanece')

    # 2. FILTROS EN BARRA LATERAL
    st.sidebar.header("🎯 Filtros")

    genero = st.sidebar.selectbox(
        "Género",
        ['All'] + sorted(data['Gender'].dropna().unique().tolist())
    )

    departamento = st.sidebar.selectbox(
        "Departamento",
        ['All'] + sorted(data['Departamento'].dropna().unique().tolist())
    )

    # Aplicar filtros
    data_filtered = data.copy()
    if genero != 'All':
        data_filtered = data_filtered[data_filtered['Gender'] == genero]
    if departamento != 'All':
        data_filtered = data_filtered[data_filtered['Departamento'] == departamento]

    # Dataset derivado para cálculos de renuncias
    data_renuncias = data_filtered[data_filtered['EstadoEmpleado'] == 'Renunció']

    # 3. INDICADORES CLAVE (KPIs)
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("👥 Empleados", len(data_filtered))
    col2.metric("🚪 Renuncias", len(data_renuncias))

    tasa_rotacion = (len(data_renuncias) / len(data_filtered) * 100) if len(data_filtered) > 0 else 0
    col3.metric("📉 Tasa de rotación", f"{tasa_rotacion:.1f}%")

    if not data_renuncias.empty:
        col4.metric("⏱️ Mes promedio de renuncia", f"{data_renuncias['AntiguedadMeses'].mean():.1f}")
    else:
        col4.metric("⏱️ Mes promedio de renuncia", "—")

    st.markdown("---")

    # BLOQUE 1 – ANÁLISIS DE TIEMPO (CUÁNDO)
    st.subheader("🔥 ¿Cuándo se producen las renuncias?")
    fig_hist = px.histogram(
        data_renuncias,
        x='AntiguedadMeses',
        nbins=24,
        title="Distribución de renuncias por meses de antigüedad",
        labels={'AntiguedadMeses': 'Antigüedad al renunciar (meses)'},
        color_discrete_sequence=['#E74C3C']
    )
    st.plotly_chart(fig_hist, use_container_width=True)
    st.caption("Cada barra muestra cuántos empleados renunciaron en ese tramo de antigüedad.")

    # BLOQUE – TRAMOS DE ANTIGÜEDAD
    st.markdown("## ⏳ ¿En qué etapa del ciclo laboral ocurre la rotación?")
    bins = [0, 6, 12, 24, 60]
    labels = ['0–6 meses', '6–12 meses', '1–2 años', '2–5 años']
    data_filtered['TramoAntiguedad'] = pd.cut(data_filtered['AntiguedadMeses'], bins=bins, labels=labels)

    total_tramo = data_filtered['TramoAntiguedad'].value_counts().sort_index()
    renuncias_tramo = data_renuncias['TramoAntiguedad'].value_counts().reindex(labels).fillna(0)
    porcentaje_tramo = (renuncias_tramo / total_tramo * 100).reset_index()
    porcentaje_tramo.columns = ['Tramo de antigüedad', '% de renuncias']

    fig_tramos = px.bar(
        porcentaje_tramo,
        x='Tramo de antigüedad',
        y='% de renuncias',
        title="Riesgo de salida concentrado en los primeros meses",
        text='% de renuncias',
        color='% de renuncias',
        color_continuous_scale='Reds'
    )
    fig_tramos.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    st.plotly_chart(fig_tramos, use_container_width=True)

    # BLOQUE 2 – ANÁLISIS POR DEPARTAMENTO (DÓNDE)
    st.markdown("---")
    st.subheader("🟥 ¿Dónde se concentra la rotación?")
    tasa_depto = (
        data.groupby('Departamento')['EstadoEmpleado']
        .apply(lambda x: (x == 'Renunció').mean() * 100)
        .reset_index(name='TasaRotacion')
        .sort_values('TasaRotacion', ascending=True)
    )
    fig_depto = px.bar(
        tasa_depto,
        x='TasaRotacion',
        y='Departamento',
        orientation='h',
        title="Departamentos con mayor tasa de rotación",
        labels={'TasaRotacion': 'Tasa de rotación (%)', 'Departamento': ''},
        color='TasaRotacion',
        color_continuous_scale='Reds'
    )
    st.plotly_chart(fig_depto, use_container_width=True)

    # BLOQUE 3 – ANÁLISIS MULTIVARIABLE (POR QUÉ)
    st.markdown("---")
    st.subheader("💰 ¿Qué relación existe entre ingreso, edad y rotación?")
    fig_scatter = px.scatter(
        data,
        x='Age',
        y='IngresoMensual',
        color='EstadoEmpleado',
        title="Dispersión: Empleados jóvenes con menor ingreso",
        labels={'Age': 'Edad', 'IngresoMensual': 'Ingreso mensual', 'EstadoEmpleado': 'Situación'},
        color_discrete_map={'Renunció': '#E74C3C', 'Permanece': '#2ECC71'},
        opacity=0.6,
        hover_data=['Puesto', 'Departamento']
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

    # BLOQUE – COMPARATIVA SE QUEDAN VS SE VAN
    st.markdown("## ⚖️ ¿En qué se diferencian quienes se quedan y quienes renuncian?")
    comparacion = data_filtered.groupby('EstadoEmpleado').agg({
        'JobSatisfaction': 'mean',
        'IngresoMensual': 'mean',
        'YearsSinceLastPromotion': 'mean'
    }).reset_index()
    comparacion_melt = comparacion.melt(id_vars='EstadoEmpleado', var_name='Variable', value_name='Promedio')

    fig_comp = px.bar(
        comparacion_melt,
        x='Variable',
        y='Promedio',
        color='EstadoEmpleado',
        barmode='group',
        title="Diferencias promedio: Permanencia vs Renuncia",
        color_discrete_map={'Renunció': '#E74C3C', 'Permanece': '#2ECC71'}
    )
    st.plotly_chart(fig_comp, use_container_width=True)

    # BLOQUE 4 – GESTIÓN Y DESARROLLO
    st.markdown("---")
    st.markdown("## 🧭 Factor de gestión y desarrollo profesional")
    st.subheader("🚧 El estancamiento laboral como factor de salida")
    ultima_promocion = (
        data_filtered['YearsSinceLastPromotion']
        .value_counts()
        .rename_axis('Años sin promoción')
        .reset_index(name='Renuncias')
    ).sort_values('Años sin promoción')

    fig_promo = px.bar(
        ultima_promocion,
        x='Años sin promoción',
        y='Renuncias',
        title="A mayor tiempo sin promoción, mayor probabilidad de renuncia",
        color='Renuncias',
        color_continuous_scale='Oranges'
    )
    fig_promo.update_layout(xaxis=dict(tickmode='linear'))
    st.plotly_chart(fig_promo, use_container_width=True)

    # BLOQUE – TENDENCIA TEMPORAL
    st.markdown("## 📆 Evolución temporal de las renuncias")
    renuncias_mes = (
        data_renuncias
        .groupby(pd.Grouper(key='FechaSalida', freq='M'))
        .size()
        .reset_index(name='Renuncias')
    )
    fig_tiempo = px.line(
        renuncias_mes,
        x='FechaSalida',
        y='Renuncias',
        markers=True,
        title="Tendencia mensual de salidas"
    )
    st.plotly_chart(fig_tiempo, use_container_width=True)

    # BLOQUE 5 – LECTURA EJECUTIVA (CONCLUSIONES DINÁMICAS)
    st.markdown("---")
    st.subheader("🧠 Lectura ejecutiva")
    
    # Cálculos para el texto dinámico
    pct_primer_ano = (data_renuncias['AntiguedadMeses'] <= 12).mean() * 100
    depto_max_rotacion = tasa_depto.iloc[-1]['Departamento']

    st.info(
        f"🔍 **El {pct_primer_ano:.0f}% de las renuncias ocurre durante el primer año**, "
        "evidenciando un alto riesgo en las etapas iniciales.\n\n"
        f"🏢 **{depto_max_rotacion} presenta la mayor tasa de rotación**, "
        "requiriendo intervención prioritaria.\n\n"
        "⚠️ **Menor satisfacción, menor ingreso y largos periodos sin promoción** "
        "son patrones recurrentes entre quienes abandonan la organización."
    )
