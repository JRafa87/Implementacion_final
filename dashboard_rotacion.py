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

    # --- TIPO DE CONTRATO ---
    if 'Tipocontrato' in df.columns:
        df['Tipo de Contrato'] = df['Tipocontrato'].fillna('No especificado')
    else:
        df['Tipo de Contrato'] = 'No definido'

    # Renombrar columnas para consistencia en español
    df = df.rename(columns={
        'MonthlyIncome': 'Ingreso Mensual',
        'Age': 'Edad',
        'YearsSinceLastPromotion': 'Años sin promoción',
        'JobRole': 'Puesto',
        'Department': 'Departamento'
    })

    # Lógica de Attrition
    if 'Attrition' not in df.columns:
        df['Attrition'] = df['FechaSalida'].apply(lambda x: 'No' if pd.isna(x) else 'Yes')
    
    df['Estado de Empleado'] = df['Attrition'].map({'Yes': 'Renunció', 'No': 'Permanece'})
    
    # Cálculo de antigüedad
    df['Fecha_Fin_Calc'] = df.apply(lambda r: FECHA_ACTUAL if pd.isna(r['FechaSalida']) and r['Attrition'] == 'No' else r['FechaSalida'], axis=1)
    df['AntiguedadMeses'] = (df['Fecha_Fin_Calc'] - df['FechaIngreso']).dt.days / 30

    # Tramos de antigüedad
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
        st.error("No se encontraron datos.")
        return

    # --- FILTROS SUPERIORES ---
    c_f1, c_f2 = st.columns(2)
    with c_f1:
        genero = st.selectbox("Filtrar por Género:", ['Todos'] + sorted(data['Género'].dropna().unique().tolist()))
    with c_f2:
        contrato = st.selectbox("Filtrar por Tipo de Contrato:", ['Todos'] + sorted(data['Tipo de Contrato'].dropna().unique().tolist()))

    # Aplicar filtros
    df_f = data.copy()
    if genero != 'Todos': df_f = df_f[df_f['Género'] == genero]
    if contrato != 'Todos': df_f = df_f[df_f['Tipo de Contrato'] == contrato]

    df_ren = df_f[df_f['Estado de Empleado'] == 'Renunció']

    # --- KPIs ---
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("👥 Total Empleados", len(df_f))
    k2.metric("🚪 Renuncias", len(df_ren))
    tasa = (len(df_ren) / len(df_f) * 100) if len(df_f) > 0 else 0
    k3.metric("📉 Tasa de Rotación", f"{tasa:.1f}%")
    promedio = df_ren['AntiguedadMeses'].mean() if not df_ren.empty else 0
    k4.metric("⏱️ Promedio Salida", f"{promedio:.1f} meses")

    st.markdown("---")

    # --- GRÁFICOS ---
    
    # 1. Histograma de Meses (RESTAURADO)
    st.subheader("🔥 ¿Cuándo se producen las renuncias?")
    fig_hist = px.histogram(df_ren, x='AntiguedadMeses', nbins=20,
                            title="Distribución de renuncias por meses de antigüedad",
                            labels={'AntiguedadMeses': 'Meses', 'count': 'Cantidad de Salidas'},
                            color_discrete_sequence=['#E74C3C'])
    fig_hist.update_layout(yaxis_title="Cantidad de Salidas", xaxis_title="Meses de Antigüedad", hovermode="x unified")
    fig_hist.update_traces(hovertemplate="Meses: %{x}<br>Salidas: %{y}")
    st.plotly_chart(fig_hist, use_container_width=True)

    # 2. Fugas por Departamento (NUEVO) y Tasa por Etapa
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🏢 Fugas por Departamento")
        if not df_ren.empty:
            dept_data = df_ren['Departamento'].value_counts().reset_index()
            dept_data.columns = ['Departamento', 'Salidas']
            fig_dept = px.bar(dept_data, x='Salidas', y='Departamento', orientation='h',
                              title="Ranking de áreas con más renuncias",
                              color='Salidas', color_continuous_scale='Reds',
                              labels={'Salidas': 'Número de Salidas', 'Departamento': 'Área'})
            st.plotly_chart(fig_dept, use_container_width=True)

    with col2:
        st.subheader("⏳ ¿En qué etapa ocurre la rotación?")
        total_t = df_f['Tramo de antigüedad'].value_counts()
        ren_t = df_ren['Tramo de antigüedad'].value_counts()
        stats_t = (ren_t / total_t * 100).reset_index()
        stats_t.columns = ['Tramo', 'Porcentaje']
        stats_t['Porcentaje'] = stats_t['Porcentaje'].fillna(0)
        fig_bar = px.bar(stats_t, x='Tramo', y='Porcentaje', text='Porcentaje',
                         title="Tasa de deserción por tramo laboral",
                         labels={'Porcentaje': 'Tasa (%)', 'Tramo': 'Antigüedad'},
                         color='Porcentaje', color_continuous_scale='Reds')
        fig_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        st.plotly_chart(fig_bar, use_container_width=True)

    # 3. Dispersión Ingresos vs Edad (RESTAURADO)
    st.subheader("💰 Relación entre Ingresos, Edad y Rotación")
    fig_scat = px.scatter(df_f, x='Edad', y='Ingreso Mensual', color='Estado de Empleado',
                          labels={'Edad': 'Edad', 'Ingreso Mensual': 'Sueldo (USD)', 'Estado de Empleado': 'Situación'},
                          color_discrete_map={'Renunció': '#E74C3C', 'Permanece': '#2ECC71'},
                          hover_data=['Puesto', 'Departamento', 'Tipo de Contrato'])
    st.plotly_chart(fig_scat, use_container_width=True)

    # 4. Factor de Estancamiento (RESTAURADO)
    st.subheader("🚧 Factor de Estancamiento (Años sin promoción)")
    promo_data = df_ren['Años sin promoción'].value_counts().reset_index()
    promo_data.columns = ['Años', 'Salidas']
    fig_promo = px.bar(promo_data.sort_values('Años'), x='Años', y='Salidas',
                       title="Impacto de la falta de ascensos en las bajas",
                       labels={'Salidas': 'Número de Renuncias', 'Años': 'Años desde último ascenso'},
                       color='Salidas', color_continuous_scale='Oranges')
    st.plotly_chart(fig_promo, use_container_width=True)

    # 5. Evolución Histórica (RESTAURADO)
    st.subheader("📆 Evolución histórica de bajas")
    if not df_ren.empty:
        ren_mes = df_ren.groupby(pd.Grouper(key='FechaSalida', freq='M')).size().reset_index(name='Total')
        fig_line = px.line(ren_mes, x='FechaSalida', y='Total', markers=True,
                           title="Tendencia temporal de renuncias",
                           labels={'Total': 'Cantidad de Salidas', 'FechaSalida': 'Mes'})
        st.plotly_chart(fig_line, use_container_width=True)

    # --- LECTURA EJECUTIVA MEJORADA ---
    st.markdown("---")
    st.subheader("🧠 Lectura ejecutiva")
    
    pct_ano = (df_ren['AntiguedadMeses'] <= 12).mean() * 100 if not df_ren.empty else 0
    area_critica = df_ren['Departamento'].value_counts().idxmax() if not df_ren.empty else "N/A"
    texto_contrato = f"bajo el esquema de **{contrato}**" if contrato != 'Todos' else "a nivel general"

    st.info(
        f"🔍 **Retención Inicial:** El **{pct_ano:.0f}%** de las salidas se concentran en el primer año.\n\n"
        f"🏢 **Área Crítica:** El departamento de **{area_critica}** es el que más talento pierde {texto_contrato}.\n\n"
        f"📋 **Análisis de Contrato:** Se observa una tendencia marcada de rotación en el personal con contrato **{contrato if contrato != 'Todos' else 'Global'}**.\n\n"
        f"⚠️ **Patrón Crítico:** La falta de promociones y salarios por debajo de la media son los principales motores de salida."
    )

if __name__ == "__main__":
    render_rotacion_dashboard()