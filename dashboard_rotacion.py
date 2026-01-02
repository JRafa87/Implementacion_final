import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from typing import Optional
from datetime import date

# ==============================================================================
# 1. CONFIGURACIÓN Y CARGA DE DATOS
# ==============================================================================

st.set_page_config(page_title="Dashboard de Rotación", layout="wide")
FECHA_ACTUAL = pd.to_datetime(date.today())

@st.cache_resource
def get_supabase() -> Optional[Client]:
    """Conexión a Supabase."""
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    return create_client(url, key) if url and key else None

supabase = get_supabase()

@st.cache_data(ttl=3600)
def load_data():
    """Carga, limpia y traduce los datos."""
    response = supabase.table("consolidado").select("*").execute()
    df = pd.DataFrame(response.data)

    # Procesamiento de Fechas
    df['FechaIngreso'] = pd.to_datetime(df['FechaIngreso'], errors='coerce')
    df['FechaSalida'] = pd.to_datetime(df['FechaSalida'], errors='coerce')

    # TRADUCCIONES DE DATOS
    if 'Gender' in df.columns:
        df['Gender'] = df['Gender'].map({
            'Male': 'Masculino', 
            'Female': 'Femenino', 
            'Non-binary': 'No binario'
        }).fillna(df['Gender'])

    # Traducción de Departamentos (Limpieza de I+D)
    diccionario_deptos = {
        'Sales': 'Ventas',
        'Human Resources': 'Recursos Humanos',
        'Research & Development': 'Investigación y Desarrollo',
        'Hardware': 'Hardware',
        'Software': 'Software',
        'Support': 'Soporte',
        'Marketing': 'Marketing'
    }
    
    if 'Department' in df.columns:
        df['Department'] = df['Department'].map(diccionario_deptos).fillna(df['Department'])

    # Renombrar columnas para el usuario
    df = df.rename(columns={
        'Department': 'Departamento',
        'JobRole': 'Puesto',
        'MonthlyIncome': 'IngresoMensual',
        'Age': 'Edad',
        'YearsSinceLastPromotion': 'AnosUltimaPromocion'
    })

    # Lógica de Attrition/Estado
    if 'Attrition' not in df.columns:
        df['Attrition'] = df['FechaSalida'].apply(lambda x: 'No' if pd.isna(x) else 'Yes')

    df['EstadoEmpleado'] = df['Attrition'].map({'Yes': 'Renunció', 'No': 'Permanece'})

    # Cálculos de Antigüedad
    df['FechaSalida_Calc'] = df.apply(
        lambda r: FECHA_ACTUAL if pd.isna(r['FechaSalida']) and r['Attrition'] == 'No' else r['FechaSalida'],
        axis=1
    )
    df['DuracionDias'] = (df['FechaSalida_Calc'] - df['FechaIngreso']).dt.days
    df['AntiguedadMeses'] = df['DuracionDias'] / 30

    # Tramos de Antigüedad
    bins = [0, 6, 12, 24, 60, 1000]
    labels_tramos = ['0–6 meses', '6–12 meses', '1–2 años', '2–5 años', 'Más de 5 años']
    df['TramoAntiguedad'] = pd.cut(df['AntiguedadMeses'], bins=bins, labels=labels_tramos)

    return df.dropna(subset=['FechaIngreso'])

# ==============================================================================
# 2. RENDERIZADO DEL DASHBOARD
# ==============================================================================

def render_rotacion_dashboard():
    st.title("📊 Análisis Descriptivo de Rotación de Personal")
    st.caption("Filtros superiores • Datos en Español • Todos los gráficos restaurados")
    
    data = load_data()
    if data.empty:
        st.error("No se pudieron cargar los datos.")
        return

    # --- PANEL DE FILTROS SUPERIORES ---
    st.markdown("### 🎯 Filtros")
    c_filt1, c_filt2 = st.columns(2)

    with c_filt1:
        genero = st.selectbox("Seleccionar Género:", ['Todos'] + sorted(data['Gender'].dropna().unique().tolist()))
    
    with c_filt2:
        departamento = st.selectbox("Seleccionar Departamento:", ['Todos'] + sorted(data['Departamento'].dropna().unique().tolist()))

    # Aplicar Filtros
    df_f = data.copy()
    if genero != 'Todos':
        df_f = df_f[df_f['Gender'] == genero]
    if departamento != 'Todos':
        df_f = df_f[df_f['Departamento'] == departamento]

    df_renuncias = df_f[df_f['EstadoEmpleado'] == 'Renunció']

    st.markdown("---")

    # --- KPIs ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 Total Colaboradores", len(df_f))
    col2.metric("🚪 Bajas (Renuncias)", len(df_renuncias))
    tasa = (len(df_renuncias) / len(df_f) * 100) if len(df_f) > 0 else 0
    col3.metric("📉 Tasa de Rotación", f"{tasa:.1f}%")
    promedio_meses = df_renuncias['AntiguedadMeses'].mean() if not df_renuncias.empty else 0
    col4.metric("⏱️ Permanencia Promedio", f"{promedio_meses:.1f} meses")

    st.markdown("---")

    # --- BLOQUE 1: DISTRIBUCIÓN Y TRAMOS ---
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("🔥 Frecuencia de Salidas")
        fig_hist = px.histogram(
            df_renuncias, x='AntiguedadMeses', nbins=15,
            title="Distribución de renuncias por meses",
            labels={'AntiguedadMeses': 'Meses', 'count': 'Personas'},
            color_discrete_sequence=['#E74C3C']
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_b:
        st.subheader("⏳ Riesgo por Etapa")
        total_tramo = df_f['TramoAntiguedad'].value_counts()
        renuncias_tramo = df_renuncias['TramoAntiguedad'].value_counts()
        stats_tramo = (renuncias_tramo / total_tramo * 100).reset_index()
        stats_tramo.columns = ['Tramo', 'Porcentaje']

        fig_tramos = px.bar(
            stats_tramo, x='Tramo', y='Porcentaje',
            title="% de Bajas según tramo laboral",
            text='Porcentaje', color='Porcentaje',
            color_continuous_scale='Reds',
            labels={'Porcentaje': 'Tasa (%)'}
        )
        fig_tramos.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        st.plotly_chart(fig_tramos, use_container_width=True)

    # --- BLOQUE 2: DEPARTAMENTOS E INGRESOS ---
    st.markdown("---")
    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("🏢 Rotación por Departamento")
        tasa_depto = (
            data.groupby('Departamento')['EstadoEmpleado']
            .apply(lambda x: (x == 'Renunció').mean() * 100)
            .reset_index(name='TasaRotacion')
            .sort_values('TasaRotacion', ascending=True)
        )
        fig_depto = px.bar(
            tasa_depto, x='TasaRotacion', y='Departamento',
            orientation='h', title="Índice de rotación por área",
            labels={'TasaRotacion': 'Tasa (%)', 'Departamento': ''},
            color='TasaRotacion', color_continuous_scale='Reds'
        )
        st.plotly_chart(fig_depto, use_container_width=True)

    with col_d:
        st.subheader("💰 Ingresos vs Edad")
        fig_scatter = px.scatter(
            df_f, x='Edad', y='IngresoMensual', color='EstadoEmpleado',
            labels={'Edad': 'Edad', 'IngresoMensual': 'Salario', 'EstadoEmpleado': 'Situación'},
            color_discrete_map={'Renunció': '#E74C3C', 'Permanece': '#2ECC71'},
            hover_data=['Puesto']
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    # --- BLOQUE 3: TENDENCIA Y CONCLUSIONES ---
    st.markdown("---")
    st.subheader("📆 Evolución de Salidas")
    renuncias_mes = df_renuncias.groupby(pd.Grouper(key='FechaSalida', freq='M')).size().reset_index(name='Renuncias')
    fig_tiempo = px.line(renuncias_mes, x='FechaSalida', y='Renuncias', markers=True,
                         title="Tendencia mensual de bajas",
                         labels={'FechaSalida': 'Mes', 'Renuncias': 'Cantidad'})
    st.plotly_chart(fig_tiempo, use_container_width=True)

    st.markdown("---")
    st.subheader("🧠 Conclusiones Ejecutivas")
    
    if not df_renuncias.empty:
        pct_12m = (df_renuncias['AntiguedadMeses'] <= 12).mean() * 100
        st.info(f"✅ **Análisis de Permanencia:** El **{pct_12m:.0f}%** de las bajas ocurren durante el primer año de labores.")
    
    depto_max = tasa_depto.iloc[-1]['Departamento'] if not tasa_depto.empty else "N/A"
    st.warning(f"✅ **Área Crítica:** El departamento de **{depto_max}** presenta el índice de rotación más alto actualmente.")
    st.success(f"✅ **Filtros Aplicados:** Mostrando datos para el género **{genero}** en el área de **{departamento}**.")

if __name__ == "__main__":
    render_rotacion_dashboard()
