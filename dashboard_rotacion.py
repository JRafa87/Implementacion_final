import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from typing import Optional
from datetime import date

# ==============================================================================
# 1. CONFIGURACIÓN Y CONEXIÓN
# ==============================================================================

FECHA_ACTUAL = pd.to_datetime(date.today())

@st.cache_resource
def get_supabase() -> Optional[Client]:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key) if url and key else None

supabase = get_supabase()

@st.cache_data(ttl=3600)
def load_data():
    response = supabase.table("consolidado").select("*").execute()
    df = pd.DataFrame(response.data)

    # Fechas
    df['FechaIngreso'] = pd.to_datetime(df['FechaIngreso'], errors='coerce')
    df['FechaSalida'] = pd.to_datetime(df['FechaSalida'], errors='coerce')

    # Attrition
    if 'Attrition' not in df.columns:
        df['Attrition'] = df['FechaSalida'].apply(lambda x: 'No' if pd.isna(x) else 'Yes')

    df['FechaSalida'] = df.apply(
        lambda r: FECHA_ACTUAL if pd.isna(r['FechaSalida']) and r['Attrition'] == 'No' else r['FechaSalida'],
        axis=1
    )

    # Tiempo
    df['DuracionDias'] = (df['FechaSalida'] - df['FechaIngreso']).dt.days
    df['AntiguedadMeses'] = df['DuracionDias'] / 30

    # Contexto humano
    df['EstadoEmpleado'] = df['Attrition'].map({
        'Yes': 'Renunció',
        'No': 'Permanece'
    })

    # Renombres
    df = df.rename(columns={
        'Department': 'Departamento',
        'JobRole': 'Puesto',
        'MonthlyIncome': 'IngresoMensual'
    })

    return df.dropna(subset=['FechaIngreso'])

# ==============================================================================
# 2. DASHBOARD
# ==============================================================================

def render_rotacion_dashboard():

    st.title("📊 Análisis Descriptivo de Rotación de Personal")
    st.caption("Dashboard descriptivo – análisis histórico basado en datos de Supabase")
    st.markdown("---")

    # ==============================================================================
    # 1. CARGA DE DATOS
    # ==============================================================================
    data = load_data()

    if data.empty:
        st.error("No se pudieron cargar los datos desde Supabase.")
        return

    # Normalizar estado del empleado (clave para todo el dashboard)
    data['EstadoEmpleado'] = data['EstadoEmpleado'].fillna('Permanece')

    # ==============================================================================
    # 2. FILTROS
    # ==============================================================================
    st.sidebar.header("🎯 Filtros")

    genero = st.sidebar.selectbox(
        "Género",
        ['All'] + sorted(data['Gender'].dropna().unique().tolist())
    )

    departamento = st.sidebar.selectbox(
        "Departamento",
        ['All'] + sorted(data['Departamento'].dropna().unique().tolist())
    )

    data_filtered = data.copy()

    if genero != 'All':
        data_filtered = data_filtered[data_filtered['Gender'] == genero]

    if departamento != 'All':
        data_filtered = data_filtered[data_filtered['Departamento'] == departamento]

    # ==============================================================================
    # 3. DATASET DERIVADO – SOLO RENUNCIAS
    # ==============================================================================
    data_renuncias = data_filtered[
        data_filtered['EstadoEmpleado'] == 'Renunció'
    ]

    # ==============================================================================
    # 4. KPIs
    # ==============================================================================
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("👥 Empleados", len(data_filtered))
    col2.metric("🚪 Renuncias", len(data_renuncias))

    tasa_rotacion = (
        (len(data_renuncias) / len(data_filtered)) * 100
        if len(data_filtered) > 0 else 0
    )

    col3.metric("📉 Tasa de rotación", f"{tasa_rotacion:.1f}%")

    if not data_renuncias.empty:
        col4.metric(
            "⏱️ Mes promedio de renuncia",
            f"{data_renuncias['AntiguedadMeses'].mean():.1f}"
        )
    else:
        col4.metric("⏱️ Mes promedio de renuncia", "—")

    st.markdown("---")


    # ==============================================================================
    # BLOQUE 1 – CUÁNDO SE VAN
    # ==============================================================================
    st.subheader("🔥 ¿Cuándo se producen las renuncias?")

    fig_hist = px.histogram(
        data_renuncias,
        x='AntiguedadMeses',
        nbins=24,
        title="La mayoría de renuncias ocurre durante los primeros meses",
        labels={'AntiguedadMeses': 'Antigüedad al renunciar (meses)'},
        color_discrete_sequence=['#E74C3C']
    )
    st.plotly_chart(fig_hist, use_container_width=True)

    st.caption("Cada barra muestra cuántos empleados renunciaron en ese tramo de antigüedad.")

    st.markdown("---")

    # ==============================================================================
    # BLOQUE 2 – DÓNDE ESTÁ EL PROBLEMA
    # ==============================================================================
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

    st.markdown("---")

    # ==============================================================================
    # BLOQUE 3 – POR QUÉ PASA (GRÁFICO ESTRELLA)
    # ==============================================================================
    st.subheader("💰 ¿Qué relación existe entre ingreso, edad y rotación?")

    fig_scatter = px.scatter(
        data,
        x='Age',
        y='IngresoMensual',
        color='EstadoEmpleado',
        title="Empleados jóvenes con menor ingreso concentran la rotación",
        labels={
            'Age': 'Edad',
            'IngresoMensual': 'Ingreso mensual',
            'EstadoEmpleado': 'Situación del empleado'
        },
        color_discrete_map={
            'Renunció': '#E74C3C',
            'Permanece': '#2ECC71'
        },
        opacity=0.6,
        hover_data=['Puesto', 'Departamento']
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.caption("Cada punto representa un empleado. El color indica si renunció o permanece en la empresa.")

    st.markdown("---")


    # ==============================================================================
    # BLOQUE 4 – 🧭 FACTOR DE GESTIÓN
    # ==============================================================================
    st.markdown("---")
    st.markdown("## 🧭 Factor de gestión y desarrollo profesional")

    st.markdown(
        "Este bloque muestra cómo la **falta de crecimiento interno** "
        "incrementa la probabilidad de renuncia."
    )

    st.subheader("🚧 El estancamiento laboral como factor de salida")

    ultima_promocion = (
        data_filtered['YearsSinceLastPromotion']
        .value_counts()
        .rename_axis('Años sin promoción')
        .reset_index(name='Renuncias')
    )

    ultima_promocion['Años sin promoción'] = pd.to_numeric(
        ultima_promocion['Años sin promoción'],
        errors='coerce'
    )

    ultima_promocion = ultima_promocion.sort_values('Años sin promoción')

    fig_promo = px.bar(
        ultima_promocion,
        x='Años sin promoción',
        y='Renuncias',
        title="📉 A mayor tiempo sin promoción, mayor probabilidad de renuncia",
        labels={
            'Años sin promoción': 'Años sin promoción',
            'Renuncias': 'Número de renuncias'
        },
        color='Renuncias',
        color_continuous_scale=px.colors.sequential.Oranges
    )

    fig_promo.update_layout(
        xaxis=dict(tickmode='linear'),
        title_font_size=18
    )

    st.plotly_chart(fig_promo, use_container_width=True)
    



    # ==============================================================================
    # BLOQUE 5 – LECTURA EJECUTIVA
    # ==============================================================================
    st.subheader("🧠 Lectura ejecutiva")

    st.info(
        f"🔍 El {((data_renuncias['AntiguedadMeses'] <= 12).mean()*100):.0f}% de las renuncias ocurre durante el primer año.\n\n"
        f"🏢 El departamento con mayor rotación es **{tasa_depto.iloc[-1]['Departamento']}**.\n\n"
        "⚠️ Baja compensación y estancamiento laboral aparecen recurrentemente en los casos de renuncia."
    )
