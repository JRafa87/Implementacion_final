import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client, Client
from typing import Optional
import warnings

warnings.filterwarnings("ignore")

# =================================================================
# 1. CONFIGURACIÓN Y CONEXIÓN A SUPABASE
# =================================================================

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("❌ Faltan credenciales de Supabase en secrets.toml")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

@st.cache_data(ttl=600)
def get_survey_data() -> pd.DataFrame:
    try:
        response = (
            supabase
            .table("encuestas")
            .select("*")
            .order("EmployeeNumber")
            .order("Fecha")
            .execute()
        )

        if not response.data:
            return pd.DataFrame()

        df = pd.DataFrame(response.data)
        df["Fecha"] = pd.to_datetime(df["Fecha"])
        return df

    except Exception as e:
        st.error(f"❌ Error al consultar encuestas: {e}")
        return pd.DataFrame()

# =================================================================
# 2. ANÁLISIS DE RIESGO
# =================================================================

def get_risk_analysis(employee_data: pd.DataFrame):
    """Analiza la última encuesta para determinar el nivel de riesgo."""
    latest = employee_data.iloc[-1]
    signals = []

    if latest["IntencionPermanencia"] <= 2:
        signals.append("Riesgo de salida (Baja intención de permanencia)")
    if latest["ConfianzaEmpresa"] <= 2:
        signals.append("Baja confianza en la organización")
    if latest["CargaLaboralPercibida"] >= 4:
        signals.append("Sobrecarga laboral detectada")
    if latest["SatisfaccionSalarial"] <= 1:
        signals.append("Insatisfacción salarial crítica")

    if len(signals) >= 2:
        return {"riesgo": "CRÍTICO", "color": "#dc3545", "señales": signals}
    elif len(signals) == 1:
        return {"riesgo": "ADVERTENCIA", "color": "#ffc107", "señales": signals}
    else:
        return {"riesgo": "BAJO", "color": "#28a745", "señales": []}

# =================================================================
# 3. VISUALIZACIONES
# =================================================================

def create_radar_chart(data: pd.Series):
    """Crea un gráfico radial con las dimensiones de satisfacción."""
    categories = [
        "Ambiente", "Compromiso", "Satisfacción",
        "Relación", "Balance Vida/Trabajo", "Confianza"
    ]

    values = [
        data["EnvironmentSatisfaction"],
        data["JobInvolvement"],
        data["JobSatisfaction"],
        data["RelationshipSatisfaction"],
        data["WorkLifeBalance"],
        data["ConfianzaEmpresa"]
    ]

    fig = go.Figure(
        go.Scatterpolar(
            r=values,
            theta=categories,
            fill="toself",
            mode="lines+markers",
            line_color="#1f77b4"
        )
    )

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[1, 5])),
        showlegend=False,
        height=350,
        margin=dict(l=40, r=40, t=40, b=40)
    )

    return fig

# =================================================================
# 4. MÓDULO PRINCIPAL
# =================================================================

def historial_encuestas_module():
    st.title("📜 Historial de Encuestas por Empleado")

    df_maestro = get_survey_data()

    if df_maestro.empty:
        st.warning("No existen encuestas registradas en la base de datos.")
        return

    # Diccionario maestro para traducir encabezados de tabla
    TRAD_COLUMNAS = {
        "EmployeeNumber": "ID Empleado",
        "Fecha": "Fecha de Medición",
        "EnvironmentSatisfaction": "Satis. Ambiental",
        "JobInvolvement": "Compromiso",
        "JobSatisfaction": "Satis. Laboral",
        "RelationshipSatisfaction": "Satis. Relacional",
        "WorkLifeBalance": "Equilibrio Vida-Trabajo",
        "IntencionPermanencia": "Permanencia",
        "CargaLaboralPercibida": "Carga Laboral",
        "SatisfaccionSalarial": "Satis. Salarial",
        "ConfianzaEmpresa": "Confianza",
        "NumeroTardanzas": "Tardanzas",
        "NumeroFaltas": "Faltas"
    }

    # Selector de empleado
    empleados = sorted(df_maestro["EmployeeNumber"].unique())
    empleado_id = st.selectbox("Seleccione el ID del Colaborador:", empleados)

    # Filtrar datos del empleado
    data_emp = df_maestro[df_maestro["EmployeeNumber"] == empleado_id].copy()
    data_emp["Fecha_str"] = data_emp["Fecha"].dt.strftime("%d/%m/%Y")
    
    # Análisis
    riesgo = get_risk_analysis(data_emp)
    ultima = data_emp.iloc[-1]

    # --- Sección de Alertas ---
    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown(
            f"""
            <div style="background:{riesgo['color']};
                        color:white;
                        padding:20px;
                        border-radius:10px;
                        text-align:center;
                        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);">
                <h3 style="margin:0; font-size: 1.2em;">RIESGO {riesgo['riesgo']}</h3>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.caption(f"Última actualización: {ultima['Fecha'].strftime('%d de %B, %Y')}")

    with col2:
        if riesgo["señales"]:
            for s in riesgo["señales"]:
                st.error(f"⚠️ {s}")
        else:
            st.success("✅ El colaborador presenta indicadores de satisfacción saludables.")

    st.divider()

    # --- Gráficos Comparativos ---
    c_radar, c_line = st.columns(2)

    with c_radar:
        st.subheader("🎡 Perfil Actual de Satisfacción")
        st.plotly_chart(create_radar_chart(ultima), use_container_width=True)

    with c_line:
        st.subheader("📈 Evolución: Intención de Permanencia")
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=data_emp["Fecha_str"],
            y=data_emp["IntencionPermanencia"],
            mode="lines+markers",
            name="Nivel",
            line=dict(color="#636EFA", width=3),
            marker=dict(size=10)
        ))
        # Línea de umbral crítico
        fig_line.add_hline(y=2, line_dash="dash", line_color="#dc3545", 
                          annotation_text="Límite Crítico", annotation_position="bottom right")
        
        fig_line.update_layout(
            height=350,
            yaxis=dict(range=[0.5, 5.5], title="Puntuación (1-5)"),
            xaxis=dict(title="Fecha de Encuesta"),
            margin=dict(l=20, r=20, t=20, b=20)
        )
        st.plotly_chart(fig_line, use_container_width=True)

    st.divider()

    # --- Tabla Histórica Traducida ---
    st.subheader("📋 Registro Histórico de Respuestas")
    
    # Preparamos el DF para la vista traduciendo nombres y quitando columnas técnicas
    df_vista = data_emp.drop(columns=["id", "Fecha_str"], errors="ignore")
    df_vista = df_vista.rename(columns=TR_COLUMNAS if 'TR_COLUMNAS' in locals() else TRAD_COLUMNAS)
    
    # Reordenar para que la Fecha sea la primera columna
    cols = df_vista.columns.tolist()
    if "Fecha de Medición" in cols:
        cols.insert(0, cols.pop(cols.index("Fecha de Medición")))
        df_vista = df_vista[cols]

    st.dataframe(
        df_vista,
        use_container_width=True,
        hide_index=True
    )

if __name__ == '__main__':
    st.set_page_config(page_title="Historial de Encuestas", layout="wide")
    historial_encuestas_module()

