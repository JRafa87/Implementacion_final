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

    # Traducción de Datos para Tooltips y Filtros
    if 'Gender' in df.columns:
        df['Género'] = df['Gender'].map({'Male': 'Masculino', 'Female': 'Femenino'}).fillna(df['Gender'])

    # Traducción y limpieza de Departamentos
    diccionario_deptos = {
        'Sales': 'Ventas',
        'Human Resources': 'Recursos Humanos',
        'Research & Development': 'Investigación y Desarrollo',
        'Hardware': 'Hardware',
        'Software': 'Software',
        'Support': 'Soporte'
    }
    if 'Department' in df.columns:
        df['Departamento'] = df['Department'].map(diccionario_deptos).fillna(df['Department'])

    # Renombrar columnas para que el mouse (tooltip) hable español
    df = df.rename(columns={
        'MonthlyIncome': 'Ingreso Mensual',
        'Age': 'Edad',
        'YearsSinceLastPromotion': 'Años sin promoción',
        'JobRole': 'Puesto'
    })

    # Lógica de estados
    if 'Attrition' not in df.columns:
        df['Attrition'] = df['FechaSalida'].apply(lambda x: 'No' if pd.isna(x) else 'Yes')
    
    df['Estado de Empleado'] = df['Attrition'].map({'Yes': 'Renunció', 'No': 'Permanece'})
    
    # Cálculo de antigüedad
    df['Fecha_Fin_Calc'] = df.apply(lambda r: FECHA_ACTUAL if pd.isna(r['FechaSalida']) and r['Attrition'] == 'No' else r['FechaSalida'], axis=1)
    df['AntiguedadMeses'] = (df['Fecha_Fin_Calc'] - df['FechaIngreso']).dt.days / 30

    # --- SOLUCIÓN AL KEYERROR: Crear tramos AQUÍ para que existan en todos los filtros ---
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
    if data.empty: return

    # --- FILTROS SUPERIORES ---
    c_f1, c_f2 = st.columns(2)
    with c_f1:
        genero = st.selectbox("Filtrar por Género:", ['Todos'] + sorted(data['Género'].dropna().unique().tolist()))
    with c_f2:
        depto = st.selectbox("Filtrar por Departamento:", ['Todos'] + sorted(data['Departamento'].dropna().unique().tolist()))

    # Aplicar filtros al dataframe base
    df_f = data.copy()
    if genero != 'Todos': df_f = df_f[df_f['Género'] == genero]
    if depto != 'Todos': df_f = df_f[df_f['Departamento'] == depto]

    # Dataset de renuncias (Ya contiene 'Tramo de antigüedad')
    df_ren = df_f[df_f['Estado de Empleado'] == 'Renunció']

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("👥 Empleados", len(df_f))
    k2.metric("🚪 Renuncias", len(df_ren))
    tasa = (len(df_ren) / len(df_f) * 100) if len(df_f) > 0 else 0
    k3.metric("📉 Tasa de Rotación", f"{tasa:.1f}%")
    promedio = df_ren['AntiguedadMeses'].mean() if not df_ren.empty else 0
    k4.metric("⏱️ Promedio Salida", f"{promedio:.1f} meses")

    st.markdown("---")

    # --- GRÁFICOS (Mismo orden que solicitaste) ---
    
    st.subheader("🔥 ¿Cuándo se producen las renuncias?")
    fig_hist = px.histogram(df_ren, x='AntiguedadMeses', nbins=20,
                            title="Distribución de renuncias por meses de antigüedad",
                            labels={'AntiguedadMeses': 'Meses de antigüedad', 'count': 'Renuncias'},
                            color_discrete_sequence=['#E74C3C'])
    st.plotly_chart(fig_hist, use_container_width=True)

    st.subheader("⏳ ¿En qué etapa ocurre la rotación?")
    # Cálculo de tasa por tramo
    total_t = df_f['Tramo de antigüedad'].value_counts()
    ren_t = df_ren['Tramo de antigüedad'].value_counts()
    stats_t = (ren_t / total_t * 100).reset_index()
    stats_t.columns = ['Tramo', 'Porcentaje']
    
    fig_bar = px.bar(stats_t, x='Tramo', y='Porcentaje', text='Porcentaje',
                     title="Riesgo de salida por etapa laboral",
                     labels={'Porcentaje': 'Tasa de Renuncia (%)', 'Tramo': 'Antigüedad'},
                     color='Porcentaje', color_continuous_scale='Reds')
    fig_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("🟥 ¿Dónde se concentra la rotación?")
    tasa_d = data.groupby('Departamento')['Estado de Empleado'].apply(lambda x: (x == 'Renunció').mean() * 100).reset_index()
    tasa_d.columns = ['Departamento', 'Tasa']
    fig_depto = px.bar(tasa_d.sort_values('Tasa'), x='Tasa', y='Departamento', orientation='h',
                       title="Tasa de rotación por departamento",
                       labels={'Tasa': 'Tasa (%)'}, color='Tasa', color_continuous_scale='Reds')
    st.plotly_chart(fig_depto, use_container_width=True)

    # --- GRÁFICO ANCHO COMPLETO ---
    st.subheader("💰 ¿Qué relación existe entre ingreso, edad y rotación?")
    fig_scat = px.scatter(df_f, x='Edad', y='Ingreso Mensual', color='Estado de Empleado',
                          labels={'Edad': 'Edad', 'Ingreso Mensual': 'Sueldo (USD)', 'Estado de Empleado': 'Situación'},
                          color_discrete_map={'Renunció': '#E74C3C', 'Permanece': '#2ECC71'},
                          hover_data=['Puesto', 'Departamento'])
    st.plotly_chart(fig_scat, use_container_width=True)

    st.subheader("🚧 El estancamiento laboral")
    promo_data = df_ren['Años sin promoción'].value_counts().reset_index()
    promo_data.columns = ['Años', 'Salidas']
    fig_promo = px.bar(promo_data.sort_values('Años'), x='Años', y='Salidas',
                       title="Salidas según años desde el último ascenso",
                       labels={'Salidas': 'Número de Renuncias', 'Años': 'Años sin promoción'},
                       color='Salidas', color_continuous_scale='Oranges')
    st.plotly_chart(fig_promo, use_container_width=True)

    st.subheader("📆 Evolución temporal")
    ren_mes = df_ren.groupby(pd.Grouper(key='FechaSalida', freq='M')).size().reset_index(name='Total')
    fig_line = px.line(ren_mes, x='FechaSalida', y='Total', markers=True,
                       title="Tendencia histórica de bajas mensuales",
                       labels={'Total': 'Cantidad', 'FechaSalida': 'Fecha'})
    st.plotly_chart(fig_line, use_container_width=True)

    # --- CONCLUSIONES ---
    st.markdown("---")
    st.subheader("🧠 Lectura ejecutiva")
    pct_ano = (df_ren['AntiguedadMeses'] <= 12).mean() * 100 if not df_ren.empty else 0
    depto_critico = tasa_d.sort_values('Tasa').iloc[-1]['Departamento']

    st.info(
        f"🔍 **El {pct_ano:.0f}% de las renuncias ocurre en el primer año**, lo que sugiere problemas en el onboarding.\n\n"
        f"🏢 **{depto_critico}** es el área con mayor urgencia de retención.\n\n"
        f"⚠️ **Sueldos bajos y falta de promociones** son los detonantes principales detectados."
    )

if __name__ == "__main__":
    render_rotacion_dashboard()
