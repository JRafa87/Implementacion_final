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
    """Establece la conexión con la base de datos Supabase."""
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key) if url and key else None

supabase = get_supabase()

@st.cache_data(ttl=3600)
def load_data():
    """Carga y procesa los datos con etiquetas en español."""
    response = supabase.table("consolidado").select("*").execute()
    df = pd.DataFrame(response.data)

    # Procesamiento de Fechas
    df['FechaIngreso'] = pd.to_datetime(df['FechaIngreso'], errors='coerce')
    df['FechaSalida'] = pd.to_datetime(df['FechaSalida'], errors='coerce')

    # Lógica de Attrition
    if 'Attrition' not in df.columns:
        df['Attrition'] = df['FechaSalida'].apply(lambda x: 'No' if pd.isna(x) else 'Yes')

    df['FechaSalida'] = df.apply(
        lambda r: FECHA_ACTUAL if pd.isna(r['FechaSalida']) and r['Attrition'] == 'No' else r['FechaSalida'],
        axis=1
    )

    # Cálculo de métricas
    df['DuracionDias'] = (df['FechaSalida'] - df['FechaIngreso']).dt.days
    df['AntiguedadMeses'] = df['DuracionDias'] / 30

    # Mapeo de contexto humano (Para que el tooltip salga en español)
    df['Estado de Empleado'] = df['Attrition'].map({'Yes': 'Renunció', 'No': 'Permanece'})
    
    # Traducción de Género para el filtro y tooltips
    if 'Gender' in df.columns:
        df['Género'] = df['Gender'].map({'Male': 'Masculino', 'Female': 'Femenino'}).fillna(df['Gender'])

    # Normalización de nombres de columnas
    df = df.rename(columns={
        'Department': 'Departamento',
        'JobRole': 'Puesto',
        'MonthlyIncome': 'Ingreso Mensual',
        'Age': 'Edad',
        'YearsSinceLastPromotion': 'Años desde última promoción'
    })

    return df.dropna(subset=['FechaIngreso'])

# ==============================================================================
# 2. RENDERIZADO DEL DASHBOARD
# ==============================================================================

def render_rotacion_dashboard():
    st.title("📊 Análisis Descriptivo de Rotación de Personal")
    st.caption("Dashboard descriptivo – análisis histórico basado en datos de Supabase")
    st.markdown("---")

    data = load_data()
    if data.empty:
        st.error("No se pudieron cargar los datos.")
        return

    # --- FILTROS ---
    st.sidebar.header("🎯 Filtros")
    genero = st.sidebar.selectbox("Género", ['Todos'] + sorted(data['Género'].dropna().unique().tolist()))
    depto = st.sidebar.selectbox("Departamento", ['Todos'] + sorted(data['Departamento'].dropna().unique().tolist()))

    data_filtered = data.copy()
    if genero != 'Todos':
        data_filtered = data_filtered[data_filtered['Género'] == genero]
    if depto != 'Todos':
        data_filtered = data_filtered[data_filtered['Departamento'] == depto]

    data_renuncias = data_filtered[data_filtered['Estado de Empleado'] == 'Renunció']

    # --- KPIs ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Empleados", len(data_filtered))
    c2.metric("🚪 Renuncias", len(data_renuncias))
    tasa = (len(data_renuncias) / len(data_filtered) * 100) if len(data_filtered) > 0 else 0
    c3.metric("📉 Tasa de rotación", f"{tasa:.1f}%")
    promedio = data_renuncias['AntiguedadMeses'].mean() if not data_renuncias.empty else 0
    c4.metric("⏱️ Mes promedio salida", f"{promedio:.1f}")

    st.markdown("---")

    # --- GRÁFICO 1: CUÁNDO (Histograma) ---
    st.subheader("🔥 ¿Cuándo se producen las renuncias?")
    fig_hist = px.histogram(
        data_renuncias,
        x='AntiguedadMeses',
        nbins=24,
        title="Distribución de renuncias por meses de antigüedad",
        labels={'AntiguedadMeses': 'Antigüedad al renunciar (meses)', 'count': 'Número de Renuncias'},
        color_discrete_sequence=['#E74C3C']
    )
    fig_hist.update_layout(hovermode="x unified")
    st.plotly_chart(fig_hist, use_container_width=True)

    # --- GRÁFICO 2: TRAMOS ---
    st.subheader("⏳ ¿En qué etapa ocurre la rotación?")
    bins = [0, 6, 12, 24, 60]
    labels = ['0–6 meses', '6–12 meses', '1–2 años', '2–5 años']
    data_filtered['Tramo de antigüedad'] = pd.cut(data_filtered['AntiguedadMeses'], bins=bins, labels=labels)
    
    total_t = data_filtered['Tramo de antigüedad'].value_counts().sort_index()
    ren_t = data_renuncias['Tramo de antigüedad'].value_counts().reindex(labels).fillna(0)
    df_tramo = (ren_t / total_t * 100).reset_index()
    df_tramo.columns = ['Tramo', 'Porcentaje']

    fig_t = px.bar(df_tramo, x='Tramo', y='Porcentaje', text='Porcentaje',
                   title="Riesgo de salida por tramo de antigüedad",
                   labels={'Porcentaje': 'Tasa de Renuncia (%)', 'Tramo': 'Etapa del ciclo laboral'},
                   color='Porcentaje', color_continuous_scale='Reds')
    fig_t.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    st.plotly_chart(fig_t, use_container_width=True)

    # --- GRÁFICO 3: DÓNDE (Departamento) ---
    st.subheader("🟥 ¿Dónde se concentra la rotación?")
    tasa_depto = data.groupby('Departamento')['Estado de Empleado'].apply(lambda x: (x == 'Renunció').mean() * 100).reset_index()
    tasa_depto.columns = ['Departamento', 'Tasa de Rotación']
    fig_d = px.bar(tasa_depto.sort_values('Tasa de Rotación'), x='Tasa de Rotación', y='Departamento',
                   orientation='h', color='Tasa de Rotación', color_continuous_scale='Reds',
                   labels={'Tasa de Rotación': 'Tasa de Rotación (%)'})
    st.plotly_chart(fig_d, use_container_width=True)

    # --- GRÁFICO 4: POR QUÉ (Ingreso vs Edad) - ANCHO COMPLETO ---
    st.subheader("💰 ¿Qué relación existe entre ingreso, edad y rotación?")
    fig_scatter = px.scatter(
        data_filtered, # Usar datos filtrados para coherencia
        x='Edad',
        y='Ingreso Mensual',
        color='Estado de Empleado',
        labels={'Edad': 'Edad del Colaborador', 'Ingreso Mensual': 'Ingreso Mensual (USD)', 'Estado de Empleado': 'Situación'},
        color_discrete_map={'Renunció': '#E74C3C', 'Permanece': '#2ECC71'},
        hover_data={'Puesto': True, 'Departamento': True, 'Edad': True, 'Ingreso Mensual': True}
    )
    fig_scatter.update_layout(legend_title_text='Estado')
    st.plotly_chart(fig_scatter, use_container_width=True)

    # --- GRÁFICO 5: GESTIÓN (Años sin promoción) ---
    st.subheader("🚧 El estancamiento laboral como factor de salida")
    promo_data = data_renuncias['Años desde última promoción'].value_counts().reset_index()
    promo_data.columns = ['Años sin promoción', 'Número de Renuncias']
    fig_p = px.bar(promo_data.sort_values('Años sin promoción'), x='Años sin promoción', y='Número de Renuncias',
                   color='Número de Renuncias', color_continuous_scale='Oranges',
                   labels={'Número de Renuncias': 'Cantidad de Salidas'})
    st.plotly_chart(fig_p, use_container_width=True)

    # --- GRÁFICO 6: TENDENCIA (Evolución) - ANCHO COMPLETO ---
    st.subheader("📆 Evolución temporal de las renuncias")
    ren_mes = data_renuncias.groupby(pd.Grouper(key='FechaSalida', freq='M')).size().reset_index(name='Total')
    fig_line = px.line(ren_mes, x='FechaSalida', y='Total', markers=True,
                       title="Tendencia mensual de salidas",
                       labels={'FechaSalida': 'Fecha de Salida', 'Total': 'Cantidad de Renuncias'})
    st.plotly_chart(fig_line, use_container_width=True)

    # --- LECTURA EJECUTIVA ---
    st.markdown("---")
    st.subheader("🧠 Lectura ejecutiva")
    pct_primer_ano = (data_renuncias['AntiguedadMeses'] <= 12).mean() * 100
    depto_critico = tasa_depto.sort_values('Tasa de Rotación').iloc[-1]['Departamento']

    st.info(
        f"🔍 **El {pct_primer_ano:.0f}% de las renuncias ocurre durante el primer año**, "
        "evidenciando un alto riesgo en las etapas iniciales.\n\n"
        f"🏢 **{depto_critico} presenta la mayor tasa de rotación**, "
        "requiriendo intervención prioritaria.\n\n"
        f"⚠️ **Menor ingreso y largos periodos sin promoción** son patrones recurrentes entre quienes abandonan la organización."
    )

# Ejecución
if __name__ == "__main__":
    render_rotacion_dashboard()
