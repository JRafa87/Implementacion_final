import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from typing import Optional
from datetime import date

# ==============================================================================
# 1. CONFIGURACIÓN Y CARGA DE DATOS
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

    # Procesamiento de Fechas
    df['FechaIngreso'] = pd.to_datetime(df['FechaIngreso'], errors='coerce')
    df['FechaSalida'] = pd.to_datetime(df['FechaSalida'], errors='coerce')

    # --- TRADUCCIÓN DE GÉNERO ---
    if 'Gender' in df.columns:
        df['Género'] = df['Gender'].map({'Male': 'Masculino', 'Female': 'Femenino'}).fillna(df['Gender'])
    else:
        df['Género'] = "No definido"

    # --- TRADUCCIÓN DE TIPO DE CONTRATO (Manejo de error si no existe) ---
    # Verifica si la columna existe en Supabase (ajusta 'tipo_contrato' si tiene otro nombre)
    col_contrato_original = 'tipo_contrato' 
    if col_contrato_original in df.columns:
        df['Tipo de Contrato'] = df[col_contrato_original].map({
            'Full-time': 'Tiempo Completo',
            'Part-time': 'Medio Tiempo',
            'Contractor': 'Contratista',
            'Freelance': 'Freelance'
        }).fillna(df[col_contrato_original])
    else:
        # Si no existe, creamos una columna genérica para que el código no falle
        df['Tipo de Contrato'] = "No especificado"

    # Renombrar columnas para Tooltips en español
    df = df.rename(columns={
        'MonthlyIncome': 'Ingreso Mensual',
        'Age': 'Edad',
        'YearsSinceLastPromotion': 'Años sin promoción',
        'JobRole': 'Puesto',
        'Department': 'Departamento'
    })

    # Lógica de estados
    if 'Attrition' not in df.columns:
        df['Attrition'] = df['FechaSalida'].apply(lambda x: 'No' if pd.isna(x) else 'Yes')
    
    df['Estado de Empleado'] = df['Attrition'].map({'Yes': 'Renunció', 'No': 'Permanece'})
    
    # Cálculo de antigüedad
    df['Fecha_Fin_Calc'] = df.apply(lambda r: FECHA_ACTUAL if pd.isna(r['FechaSalida']) and r['Attrition'] == 'No' else r['FechaSalida'], axis=1)
    df['AntiguedadMeses'] = (df['Fecha_Fin_Calc'] - df['FechaIngreso']).dt.days / 30

    # Crear tramos de antigüedad
    bins = [0, 6, 12, 24, 60, 1000]
    labels_tramos = ['0–6 meses', '6–12 meses', '1–2 años', '2–5 años', 'Más de 5 años']
    df['Tramo de antigüedad'] = pd.cut(df['AntiguedadMeses'], bins=bins, labels=labels_tramos)

    return df.dropna(subset=['FechaIngreso'])

# ==============================================================================
# 2. INTERFAZ DEL DASHBOARD
# ==============================================================================

def render_rotacion_dashboard():
    st.title("📊 Análisis Descriptivo de Rotación de Personal")
    
    data = load_data()
    if data.empty:
        st.error("No se encontraron datos disponibles.")
        return

    # --- FILTROS SUPERIORES ---
    st.markdown("### 🎯 Filtros Principales")
    c_f1, c_f2 = st.columns(2)
    with c_f1:
        genero = st.selectbox("Filtrar por Género:", ['Todos'] + sorted(data['Género'].unique().tolist()))
    with c_f2:
        contrato = st.selectbox("Filtrar por Tipo de Contrato:", ['Todos'] + sorted(data['Tipo de Contrato'].unique().tolist()))

    # Aplicar filtros
    df_f = data.copy()
    if genero != 'Todos': df_f = df_f[df_f['Género'] == genero]
    if contrato != 'Todos': df_f = df_f[df_f['Tipo de Contrato'] == contrato]

    df_ren = df_f[df_f['Estado de Empleado'] == 'Renunció']

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("👥 Total Empleados", len(df_f))
    k2.metric("🚪 Renuncias", len(df_ren))
    tasa = (len(df_ren) / len(df_f) * 100) if len(df_f) > 0 else 0
    k3.metric("📉 Tasa de Rotación", f"{tasa:.1f}%")
    promedio = df_ren['AntiguedadMeses'].mean() if not df_ren.empty else 0
    k4.metric("⏱️ Promedio Salida", f"{promedio:.1f} meses")

    st.markdown("---")

    # --- GRÁFICOS ---
    
    st.subheader("🔥 ¿Cuándo se producen las renuncias?")
    fig_hist = px.histogram(df_ren, x='AntiguedadMeses', nbins=20,
                            title="Distribución de renuncias por meses",
                            labels={'AntiguedadMeses': 'Meses de antigüedad', 'count': 'Frecuencia'},
                            color_discrete_sequence=['#E74C3C'])
    st.plotly_chart(fig_hist, use_container_width=True)

    st.subheader("⏳ ¿En qué etapa ocurre la rotación?")
    # Agrupación para evitar errores de división por cero
    total_t = df_f['Tramo de antigüedad'].value_counts()
    ren_t = df_ren['Tramo de antigüedad'].value_counts()
    stats_t = (ren_t / total_t * 100).reset_index().fillna(0)
    stats_t.columns = ['Tramo', 'Porcentaje']
    
    fig_bar = px.bar(stats_t, x='Tramo', y='Porcentaje', text='Porcentaje',
                     title="Tasa de deserción por etapa laboral",
                     labels={'Porcentaje': 'Tasa (%)', 'Tramo': 'Antigüedad'},
                     color='Porcentaje', color_continuous_scale='Reds')
    fig_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("💰 Relación entre Ingresos, Edad y Rotación")
    fig_scat = px.scatter(df_f, x='Edad', y='Ingreso Mensual', color='Estado de Empleado',
                          labels={'Edad': 'Edad', 'Ingreso Mensual': 'Sueldo (USD)', 'Estado de Empleado': 'Situación'},
                          color_discrete_map={'Renunció': '#E74C3C', 'Permanece': '#2ECC71'},
                          hover_data=['Puesto', 'Departamento', 'Tipo de Contrato'])
    st.plotly_chart(fig_scat, use_container_width=True)

    st.subheader("📆 Evolución histórica de bajas")
    if not df_ren.empty:
        ren_mes = df_ren.groupby(pd.Grouper(key='FechaSalida', freq='M')).size().reset_index(name='Total')
        fig_line = px.line(ren_mes, x='FechaSalida', y='Total', markers=True,
                           title="Tendencia de salidas mensuales",
                           labels={'Total': 'Cantidad', 'FechaSalida': 'Mes'})
        st.plotly_chart(fig_line, use_container_width=True)

    # --- LECTURA EJECUTIVA ---
    st.markdown("---")
    st.subheader("🧠 Lectura ejecutiva")
    pct_ano = (df_ren['AntiguedadMeses'] <= 12).mean() * 100 if not df_ren.empty else 0

    st.info(
        f"🔍 **Análisis de Permanencia:** El **{pct_ano:.0f}%** de las bajas ocurren en el primer año de contrato.\n\n"
        f"⚠️ **Observación:** El filtro actual por contrato **({contrato})** permite identificar patrones de salida específicos vinculados al nivel de ingresos y edad."
    )

if __name__ == "__main__":
    render_rotacion_dashboard()