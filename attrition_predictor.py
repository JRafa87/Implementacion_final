import pandas as pd
import numpy as np
import joblib
import streamlit as st
import plotly.express as px
from datetime import datetime
from typing import Optional

# --- Configuración de Supabase (Manejo de Importación Robusto) ---
try:
    from supabase import create_client, Client
    SUPABASE_INSTALLED = True
except ImportError:
    # Definiciones de placeholder para evitar NameError en las anotaciones de tipo
    class Client:
        pass 
    SUPABASE_INSTALLED = False
    
# ==============================================================================
# 1. CONSTANTES Y CONFIGURACIÓN
# ==============================================================================

# Columnas que deben entrar al modelo, en el orden correcto (33 variables)
MODEL_COLUMNS = [
    'Age','BusinessTravel','DailyRate','Department','DistanceFromHome',
    'Education','EducationField','EnvironmentSatisfaction','Gender','HourlyRate',
    'JobInvolvement','JobLevel','JobRole','JobSatisfaction','MaritalStatus',
    'MonthlyIncome','MonthlyRate','NumCompaniesWorked','OverTime','PercentSalaryHike',
    'PerformanceRating','RelationshipSatisfaction','StockOptionLevel','TotalWorkingYears',
    'TrainingTimesLastYear','WorkLifeBalance','YearsAtCompany','YearsInCurrentRole',
    'YearsSinceLastPromotion','YearsWithCurrManager',
    'IntencionPermanencia','CargaLaboralPercibida','SatisfaccionSalarial',
    'ConfianzaEmpresa','NumeroTardanzas','NumeroFaltas', 
    'tipo_contrato' 
]

# Columnas categóricas que necesitan mapeo numérico
CATEGORICAL_COLS_TO_MAP = [
    'BusinessTravel', 'Department', 'EducationField', 'Gender', 'JobRole',
    'MaritalStatus', 'OverTime', 'tipo_contrato'
]


# ==============================================================================
# 2. CARGA DE MODELO Y ARTEFACTOS
# ==============================================================================

@st.cache_resource
def load_model_artefacts():
    """Carga el modelo pre-entrenado, el mapeo de categóricas y el escalador."""
    try:
        # Asegúrate de que estos archivos .pkl existan en la ruta 'models/'
        model = joblib.load('models/xgboost_model.pkl')
        categorical_mapping = joblib.load('models/categorical_mapping.pkl')
        scaler = joblib.load('models/scaler.pkl')
        st.success("✅ Modelo y artefactos cargados correctamente.")
        return model, categorical_mapping, scaler
    except FileNotFoundError as e:
        st.error(f"❌ Error: Archivo de modelo no encontrado: {e}. Asegúrate de que los .pkl estén en la carpeta 'models/'.")
        return None, None, None
    except Exception as e:
        st.error(f"❌ Error al cargar modelo o artefactos: {e}")
        return None, None, None


# ==============================================================================
# 3. PREPROCESAMIENTO
# ==============================================================================

def preprocess_data(df, model_columns, categorical_mapping, scaler):
    """
    Prepara el DataFrame de entrada (df) para la predicción, aplicando
    imputación, codificación de categóricas y escalado.
    """
    df_processed = df.copy()

    # 1. Asegurar la presencia de todas las columnas del modelo
    for col in model_columns:
        if col not in df_processed.columns:
            df_processed[col] = np.nan

    # 2. Imputación Numérica (rellenar NaN con la media)
    numeric_cols = df_processed.select_dtypes(include=np.number).columns.tolist()
    for col in numeric_cols:
        if col in df_processed.columns:
            if not df_processed[col].isnull().all():
                df_processed[col] = df_processed[col].fillna(df_processed[col].mean())
            else:
                df_processed[col] = df_processed[col].fillna(0) 

    # 3. Codificación Categórica
    for col in CATEGORICAL_COLS_TO_MAP:
        if col in df_processed.columns:
            df_processed[col] = df_processed[col].astype(str).str.strip().str.upper()
            
            if col in categorical_mapping:
                df_processed[col] = df_processed[col].map(categorical_mapping[col])
            
            df_processed[col] = df_processed[col].fillna(-1)

    # 4. Escalado
    try:
        present_cols = [c for c in model_columns if c in df_processed.columns]
        df_to_scale = df_processed[present_cols].copy()
        df_processed[present_cols] = scaler.transform(df_to_scale)
    except Exception as e:
        st.error(f"⚠️ Error al escalar datos: {e}. El DataFrame podría no ser apto.")
        return None

    # Devolver SOLO las columnas del modelo en el orden correcto
    return df_processed[model_columns]


# ==============================================================================
# 4. GENERACIÓN DE RECOMENDACIONES Y PREDICCIÓN
# ==============================================================================

def generar_recomendacion_personalizada(row):
    """Genera recomendaciones basadas en umbrales lógicos de las columnas de encuesta/RRHH."""
    recomendaciones = []