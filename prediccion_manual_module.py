import streamlit as st
import pandas as pd
import joblib
from supabase import create_client
from typing import Dict, Any

# ===============================
# CONFIG
# ===============================

MODEL_PATH = "models/xgboost_model.pkl"
SCALER_PATH = "models/scaler.pkl"
MAPPING_PATH = "models/categorical_mapping.pkl"

EMPLOYEE_TABLE = "consolidado"
KEY_COLUMN = "EmployeeNumber"

MODEL_COLUMNS = [
    'Age','BusinessTravel','Department','DistanceFromHome','Education',
    'EducationField','EnvironmentSatisfaction','Gender','JobInvolvement',
    'JobLevel','JobRole','JobSatisfaction','MaritalStatus','MonthlyIncome',
    'NumCompaniesWorked','OverTime','PercentSalaryHike','PerformanceRating',
    'RelationshipSatisfaction','TotalWorkingYears','TrainingTimesLastYear',
    'WorkLifeBalance','YearsAtCompany','YearsInCurrentRole',
    'YearsSinceLastPromotion','YearsWithCurrManager',
    'IntencionPermanencia','CargaLaboralPercibida','SatisfaccionSalarial',
    'ConfianzaEmpresa','NumeroTardanzas','NumeroFaltas','tipo_contrato'
]

LOCKED_WHEN_FROM_DB = ['Age', 'Gender', 'MaritalStatus']

# ===============================
# SUPABASE
# ===============================

@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

supabase = get_supabase()

# ===============================
# MODEL
# ===============================

@st.cache_resource
def load_model():
    return (
        joblib.load(MODEL_PATH),
        joblib.load(SCALER_PATH),
        joblib.load(MAPPING_PATH)
    )

model, scaler, mapping = load_model()

# ===============================
# HELPERS
# ===============================

def fetch_employee_ids():
    try:
        res = supabase.table(EMPLOYEE_TABLE).select(KEY_COLUMN).execute()
        return sorted([str(r[KEY_COLUMN]) for r in res.data])
    except:
        return []

def load_employee_data(emp_id: str) -> Dict[str, Any]:
    res = supabase.table(EMPLOYEE_TABLE).select("*").eq(KEY_COLUMN, emp_id).limit(1).execute()
    return res.data[0] if res.data else {}

def predict(data: Dict[str, Any]) -> float:
    df = pd.DataFrame([data])[MODEL_COLUMNS]
    for col, mp in mapping.items():
        if col in df:
            df[col] = df[col].map(mp).fillna(0)
    df = scaler.transform(df)
    return model.predict_proba(df)[0][1]

# ===============================
# RENDER
# ===============================

def render_manual_prediction_tab():
    st.subheader("🧪 Simulación y Predicción")

    employee_ids = fetch_employee_ids()
    selected = st.selectbox(
        "EmployeeNumber",
        ["---"] + employee_ids
    )

    base_data = load_employee_data(selected) if selected != "---" else {}

    manual = {}
    c1, c2 = st.columns(2)
    i = 0

    for col in MODEL_COLUMNS:
        base = base_data.get(col, 0)
        locked = col in LOCKED_WHEN_FROM_DB and selected != "---"
        cont = c1 if i % 2 == 0 else c2

        with cont:
            if col in mapping:
                opts = list(mapping[col].keys())
                manual[col] = st.selectbox(
                    col + (" 🔒" if locked else ""),
                    opts,
                    index=opts.index(base) if base in opts else 0,
                    disabled=locked
                )
            else:
                manual[col] = st.number_input(
                    col + (" 🔒" if locked else ""),
                    value=float(base) if base else 0.0,
                    disabled=locked
                )
        i += 1

    colA, colB = st.columns(2)

    with colA:
        if st.button("🔮 Predicción BASE", use_container_width=True):
            st.metric("Probabilidad", f"{predict(base_data):.2%}")

    with colB:
        if st.button("🧪 Predicción MANUAL", use_container_width=True):
            st.metric("Probabilidad", f"{predict(manual):.2%}")


