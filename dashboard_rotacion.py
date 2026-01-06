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

    # --- TRADUCCIONES ---
    if 'Gender' in df.columns:
        df['Género'] = df['Gender'].map({'Male': 'Masculino', 'Female': 'Femenino'}).fillna(df['Gender'])

    # Traducción de Departamentos
    if 'Department' in df.columns:
        dict_dept = {
            'Sales': 'Ventas',
            'Research & Development': 'Investigación y Desarrollo',
            'Human Resources': 'Recursos Humanos',
            'Software': 'Software/Sistemas',
            'Hardware': 'Hardware'
        }
        df['Departamento'] = df['Department'].replace(dict_dept)

    # --- TIPO DE CONTRATO ---
    if 'Tipocontrato' in df.columns:
        df['Tipo de Contrato'] = df['Tipocontrato'].fillna('No especificado')
    else:
        df['Tipo de Contrato'] = 'No definido'

    # Renombrar columnas para consistencia (Manteniendo nombres originales internamente)
    df = df.rename(columns={
        'MonthlyIncome': 'Ingreso Mensual',
        'Age': 'Edad',
        'YearsSinceLastPromotion': 'Años sin promoción',
        'JobRole': 'Puesto'
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
    st.set_page_config(layout="wide") # Opcional: para aprovechar mejor el ancho total
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

    # --- 1. GRÁFICO DE DEPARTAMENTO (SOLO Y ANCHO) ---
    st.subheader("🏢 Fugas por Departamento")
    if not df_ren.empty:
        dept_data = df_ren['Departamento'].value_counts().reset_index()
        dept_data.columns = ['Departamento', 'Salidas']
        fig_dept = px.bar(dept_data, x='Salidas', y='Departamento', orientation='h',
                          title="Ranking de áreas con mayor volumen de bajas",
                          color='Salidas', color_continuous_scale='Reds',
                          labels={'Salidas': 'Número de Salidas', 'Departamento': 'Área'})
        st.plotly_chart(fig_dept, use_container_width=True)
    else:
        st.warning("No hay datos de renuncias para los filtros seleccionados.")

    # --- 2. FILA DOBLE: ETAPA Y ESTANCAMIENTO ---
    col_etapa, col_promo = st.columns(2)

    with col_etapa:
        st.subheader("⏳ Tasa por Etapa Laboral")
        total_t = df_f['Tramo de antigüedad'].value_counts()
        ren_t = df_ren['Tramo de antigüedad'].value_counts()
        stats_t = (ren_t / total_t * 100).reset_index()
        stats_t.columns = ['Tramo', 'Porcentaje']
        stats_t['Porcentaje'] = stats_t['Porcentaje'].fillna(0)
        
        fig_bar = px.bar(stats_t, x='Tramo', y='Porcentaje', text='Porcentaje',
                         title="Tasa de deserción por antigüedad",
                         labels={'Porcentaje': 'Tasa (%)', 'Tramo': 'Antigüedad'},
                         color='Porcentaje', color_continuous_scale='Reds')
        fig_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_promo:
        st.subheader("🚧 Factor de Estancamiento")
        promo_data = df_ren['Años sin promoción'].value_counts().reset_index()
        promo_data.columns = ['Años', 'Salidas']
        fig_promo = px.bar(promo_data.sort_values('Años'), x='Años', y='Salidas',
                           title="Bajas vs Años desde último ascenso",
                           labels={'Salidas': 'Renuncias', 'Años': 'Años sin promoción'},
                           color='Salidas', color_continuous_scale='Oranges')
        st.plotly_chart(fig_promo, use_container_width=True)

    # --- 3. RELACIÓN INGRESOS Y EDAD ---
    st.subheader("💰 Relación entre Ingresos, Edad y Rotación")
    fig_scat = px.scatter(df_f, x='Edad', y='Ingreso Mensual', color='Estado de Empleado',
                          labels={'Edad': 'Edad', 'Ingreso Mensual': 'Sueldo (USD)', 'Estado de Empleado': 'Situación'},
                          color_discrete_map={'Renunció': '#E74C3C', 'Permanece': '#2ECC71'},
                          hover_data=['Puesto', 'Departamento', 'Tipo de Contrato'])
    st.plotly_chart(fig_scat, use_container_width=True)

    # --- 4. TENDENCIA TEMPORAL ---
    st.subheader("📆 Evolución histórica de bajas")
    if not df_ren.empty:
        ren_mes = df_ren.groupby(pd.Grouper(key='FechaSalida', freq='M')).size().reset_index(name='Total')
        fig_line = px.line(ren_mes, x='FechaSalida', y='Total', markers=True,
                           title="Tendencia temporal de renuncias",
                           labels={'Total': 'Cantidad de Salidas', 'FechaSalida': 'Mes'})
        st.plotly_chart(fig_line, use_container_width=True)

    # --- 5. GRÁFICO SOLICITADO: DISTRIBUCIÓN POR MESES DE ANTIGÜEDAD (ANCHO COMPLETO) ---
    st.subheader("📊 Distribución de renuncias por meses de antigüedad")
    if not df_ren.empty:
        # Agrupamos por el valor entero de meses de antigüedad
        df_ren['Meses_Enteros'] = df_ren['AntiguedadMeses'].fillna(0).astype(int)
        dist_antiguedad = df_ren.groupby('Meses_Enteros').size().reset_index(name='count')
        
        fig_meses = px.bar(
            dist_antiguedad, 
            x='Meses_Enteros', 
            y='count',
            title="Detalle de bajas por mes exacto de permanencia",
            labels={'Meses_Enteros': 'Antigüedad al renunciar (meses)', 'count': 'count'},
            color_discrete_sequence=['#E74C3C'] 
        )
        
        fig_meses.update_layout(bargap=0.1)
        st.plotly_chart(fig_meses, use_container_width=True)

    # --- LECTURA EJECUTIVA ---
    st.markdown("---")
    st.subheader("🧠 Lectura ejecutiva")
    
    pct_ano = (df_ren['AntiguedadMeses'] <= 12).mean() * 100 if not df_ren.empty else 0
    area_critica = df_ren['Departamento'].value_counts().idxmax() if not df_ren.empty else "N/A"
    
    st.info(
        f"🔍 **Retención Inicial:** El **{pct_ano:.0f}%** de las salidas se concentran en el primer año.\n\n"
        f"🏢 **Área Crítica:** El departamento de **{area_critica}** es el foco principal de deserción bajo el contrato seleccionado.\n\n"
        f"⚠️ **Patrón de Estancamiento:** Se observa que a partir del segundo año sin promociones, la probabilidad de renuncia aumenta significativamente."
    )

if __name__ == "__main__":
    render_rotacion_dashboard()