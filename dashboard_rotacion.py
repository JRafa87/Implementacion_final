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

    # --- TRADUCCIÓN DE DATOS (Contenido de las celdas) ---
    
    # 1. Traducción de Género
    if 'Gender' in df.columns:
        df['Gender'] = df['Gender'].map({
            'Male': 'Masculino', 
            'Female': 'Femenino', 
            'Non-binary': 'No binario'
        }).fillna(df['Gender'])

    # 2. Traducción de Departamentos (Mapeo Inglés -> Español)
    # Aquí puedes agregar más departamentos si existen en tu base de datos
    diccionario_deptos = {
        'Sales': 'Ventas',
        'Human Resources': 'Recursos Humanos',
        'Research & Development': 'I+D / Desarrollo',
        'Hardware': 'Hardware',
        'Software': 'Software',
        'Support': 'Soporte',
        'Marketing': 'Marketing'
    }
    
    if 'Department' in df.columns:
        df['Department'] = df['Department'].map(diccionario_deptos).fillna(df['Department'])

    # 3. Traducción de nombres de Columnas
    df = df.rename(columns={
        'Department': 'Departamento',
        'JobRole': 'Puesto',
        'MonthlyIncome': 'IngresoMensual',
        'Age': 'Edad'
    })

    # Lógica de Attrition
    if 'Attrition' not in df.columns:
        df['Attrition'] = df['FechaSalida'].apply(lambda x: 'No' if pd.isna(x) else 'Yes')

    df['FechaSalida'] = df.apply(
        lambda r: FECHA_ACTUAL if pd.isna(r['FechaSalida']) and r['Attrition'] == 'No' else r['FechaSalida'],
        axis=1
    )

    # Métricas de tiempo
    df['DuracionDias'] = (df['FechaSalida'] - df['FechaIngreso']).dt.days
    df['AntiguedadMeses'] = df['DuracionDias'] / 30
    df['EstadoEmpleado'] = df['Attrition'].map({'Yes': 'Renunció', 'No': 'Permanece'})
    
    # Tramos de Antigüedad (Se crean aquí para evitar el KeyError)
    bins = [0, 6, 12, 24, 60, 1000]
    labels_tramos = ['0–6 meses', '6–12 meses', '1–2 años', '2–5 años', 'Más de 5 años']
    df['TramoAntiguedad'] = pd.cut(df['AntiguedadMeses'], bins=bins, labels=labels_tramos)

    return df.dropna(subset=['FechaIngreso'])

# ==============================================================================
# 2. RENDERIZADO DEL DASHBOARD
# ==============================================================================

def render_rotacion_dashboard():
    st.title("📊 Análisis Descriptivo de Rotación de Personal")
    st.caption("Filtros en la parte superior • Departamentos traducidos al Español")
    
    data = load_data()

    if data.empty:
        st.error("No se pudieron cargar los datos.")
        return

    # --- PANEL DE FILTROS SUPERIORES (Solo 2 columnas ahora) ---
    st.markdown("### 🎯 Panel de Control")
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

    # --- GRÁFICOS ---
    col_izq, col_der = st.columns(2)

    with col_izq:
        st.subheader("🔥 Distribución de Salidas")
        fig_hist = px.histogram(
            df_renuncias, x='AntiguedadMeses', nbins=15,
            title="Cantidad de renuncias según meses de antigüedad",
            labels={'AntiguedadMeses': 'Meses transcurridos', 'count': 'Número de personas'},
            color_discrete_sequence=['#E74C3C']
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_der:
        st.subheader("⏳ Análisis por Etapas")
        # Porcentajes por tramo
        total_tramo = df_f['TramoAntiguedad'].value_counts()
        renuncias_tramo = df_renuncias['TramoAntiguedad'].value_counts()
        stats_tramo = (renuncias_tramo / total_tramo * 100).reset_index()
        stats_tramo.columns = ['Tramo', 'Porcentaje']

        fig_tramos = px.bar(
            stats_tramo, x='Tramo', y='Porcentaje',
            title="Porcentaje de deserción por tramo laboral",
            text='Porcentaje', color='Porcentaje',
            color_continuous_scale='Reds',
            labels={'Porcentaje': '% de Bajas'}
        )
        fig_tramos.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        st.plotly_chart(fig_tramos, use_container_width=True)

    st.markdown("---")
    
    # Gráfico de Ingresos vs Edad
    st.subheader("💰 Panorama de Ingresos y Edad")
    fig_scatter = px.scatter(
        df_f, x='Edad', y='IngresoMensual', color='EstadoEmpleado',
        labels={'Edad': 'Edad del empleado', 'IngresoMensual': 'Salario Mensual', 'EstadoEmpleado': 'Estado'},
        color_discrete_map={'Renunció': '#E74C3C', 'Permanece': '#2ECC71'},
        hover_data=['Departamento', 'Puesto']
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

    # --- NOTA FINAL ---
    st.info(f"💡 Datos filtrados para **{genero}** en el departamento de **{departamento}**.")

if __name__ == "__main__":
    render_rotacion_dashboard()
