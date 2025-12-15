import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client, Client

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
    latest = employee_data.iloc[-1]
    signals = []

    if latest["IntencionPermanencia"] <= 2:
        signals.append("Riesgo de salida")
    if latest["ConfianzaEmpresa"] <= 2:
        signals.append("Baja confianza")
    if latest["CargaLaboralPercibida"] >= 4:
        signals.append("Sobrecarga laboral")
    if latest["SatisfaccionSalarial"] <= 1:
        signals.append("Insatisfacción salarial")

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
    categories = [
        "Ambiente", "Involucramiento", "Satisfacción Laboral",
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
            mode="lines+markers"
        )
    )

    fig.update_layout(
        polar=dict(radialaxis=dict(range=[1, 5])),
        showlegend=False,
        height=400
    )

    return fig

# =================================================================
# 4. MÓDULO PRINCIPAL
# =================================================================

def historial_encuestas_module():
    st.title("📜 Historial de Encuestas por Empleado")

    df_maestro = get_survey_data()

    if df_maestro.empty:
        st.warning("No existen encuestas registradas.")
        return

    empleados = sorted(df_maestro["EmployeeNumber"].unique())
    empleado = st.selectbox("Selecciona empleado", empleados)

    data_emp = df_maestro[df_maestro["EmployeeNumber"] == empleado]

    riesgo = get_risk_analysis(data_emp)
    ultima = data_emp.iloc[-1]

    col1, col2 = st.columns([1, 3])

    with col1:
        st.markdown(
            f"""
            <div style="background:{riesgo['color']};
                        color:white;
                        padding:15px;
                        border-radius:10px;
                        text-align:center;">
                <h4>RIESGO {riesgo['riesgo']}</h4>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.caption(f"Última encuesta: {ultima['Fecha'].date()}")

    with col2:
        if riesgo["señales"]:
            for s in riesgo["señales"]:
                st.error(s)
        else:
            st.success("Sin alertas activas")

    st.markdown("---")

    col_radar, col_line = st.columns(2)

    with col_radar:
        st.plotly_chart(create_radar_chart(ultima), use_container_width=True)

    with col_line:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=data_emp["Fecha"],
            y=data_emp["IntencionPermanencia"],
            mode="lines+markers"
        ))
        fig.add_hline(y=2, line_dash="dash", line_color="red")
        fig.update_xaxes(
        tickformat="%d/%m/%Y"
    )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.dataframe(data_emp, use_container_width=True)

