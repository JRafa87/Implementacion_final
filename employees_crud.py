import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import Optional
from datetime import date

# ==========================================================
# 1. CONFIGURACIÓN GENERAL
# ==========================================================

st.set_page_config(
    page_title="Gestión de Empleados",
    layout="wide"
)

# ==========================================================
# 2. CONEXIÓN A SUPABASE
# ==========================================================

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("❌ Faltan credenciales de Supabase")
        st.stop()
    return create_client(url, key)

supabase = get_supabase()

# ==========================================================
# 3. UTILIDAD: CATÁLOGOS DESDE SUPABASE
# ==========================================================

@st.cache_data(ttl=600)
def fetch_unique_column_values(table: str, column: str) -> list:
    try:
        res = supabase.table(table).select(column).execute()
        values = [
            row[column] for row in res.data
            if row.get(column) not in (None, "", " ")
        ]
        return sorted(set(values))
    except Exception as e:
        st.error(f"Error cargando {column}: {e}")
        return []

# ==========================================================
# 4. CRUD BÁSICO
# ==========================================================

def fetch_employees():
    res = supabase.table("empleados").select("*").order("EmployeeNumber").execute()
    return [{k.lower(): v for k, v in r.items()} for r in res.data]

def fetch_employee_by_id(emp_id: int) -> Optional[dict]:
    res = supabase.table("empleados").select("*").eq("EmployeeNumber", emp_id).single().execute()
    return {k.lower(): v for k, v in res.data.items()} if res.data else None

def add_employee(data: dict):
    supabase.table("empleados").insert(data).execute()
    st.success("✅ Empleado agregado")

def update_employee(emp_id: int, data: dict):
    supabase.table("empleados").update(data).eq("EmployeeNumber", emp_id).execute()
    st.success("✅ Empleado actualizado")

def delete_employee(emp_id: int):
    supabase.table("empleados").delete().eq("EmployeeNumber", emp_id).execute()
    st.success("🗑️ Empleado eliminado")

# ==========================================================
# 5. DATAFRAME PRINCIPAL
# ==========================================================

@st.cache_data(ttl=600)
def get_employees_df():
    data = fetch_employees()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)

# ==========================================================
# 6. UI PRINCIPAL
# ==========================================================

st.title("👥 Gestión de Empleados")
st.markdown("Administración completa conectada a Supabase")

df = get_employees_df()

# ==========================================================
# 7. FORMULARIO NUEVO EMPLEADO
# ==========================================================

st.subheader("➕ Nuevo Empleado")

dept_options = fetch_unique_column_values("consolidado", "Department")
jobrole_options = fetch_unique_column_values("consolidado", "JobRole")
tipocontrato_options = fetch_unique_column_values("consolidado", "Tipocontrato")

with st.form("add_employee_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)

    with col1:
        emp_id = st.number_input("EmployeeNumber", min_value=1)
        age = st.number_input("Age", min_value=18, max_value=100)
        gender = st.selectbox("Gender", ["Male", "Female"])

    with col2:
        department = st.selectbox("Department", dept_options)
        jobrole = st.selectbox("JobRole", jobrole_options)
        joblevel = st.number_input("JobLevel", min_value=1, max_value=5)

    with col3:
        tipocontrato = st.selectbox("Tipocontrato", tipocontrato_options)
        monthlyincome = st.number_input("MonthlyIncome", min_value=0)
        overtime = st.radio("OverTime", ["Yes", "No"])

    submitted = st.form_submit_button("💾 Guardar")

    if submitted:
        add_employee({
            "EmployeeNumber": emp_id,
            "Age": age,
            "Gender": gender,
            "Department": department,
            "JobRole": jobrole,
            "JobLevel": joblevel,
            "Tipocontrato": tipocontrato,
            "MonthlyIncome": monthlyincome,
            "OverTime": overtime
        })
        st.cache_data.clear()
        st.rerun()

# ==========================================================
# 8. TABLA DE EMPLEADOS
# ==========================================================

st.subheader("📋 Empleados Registrados")

if df.empty:
    st.warning("No hay empleados")
else:
    st.dataframe(df, use_container_width=True, hide_index=True)

# ==========================================================
# 9. EDITAR / ELIMINAR
# ==========================================================

st.subheader("✏️ Editar / ❌ Eliminar")

emp_ids = df["employeenumber"].tolist() if not df.empty else []

selected_id = st.selectbox(
    "Selecciona un empleado",
    [""] + emp_ids
)

if selected_id:
    emp = fetch_employee_by_id(selected_id)

    with st.form("edit_employee_form"):
        col1, col2 = st.columns(2)

        with col1:
            new_department = st.selectbox(
                "Department",
                dept_options,
                index=dept_options.index(emp["department"])
            )
            new_jobrole = st.selectbox(
                "JobRole",
                jobrole_options,
                index=jobrole_options.index(emp["jobrole"])
            )

        with col2:
            new_tipocontrato = st.selectbox(
                "Tipocontrato",
                tipocontrato_options,
                index=tipocontrato_options.index(emp["tipocontrato"])
            )
            new_monthlyincome = st.number_input(
                "MonthlyIncome",
                value=int(emp["monthlyincome"])
            )

        col_save, col_delete = st.columns(2)

        with col_save:
            if st.form_submit_button("💾 Guardar Cambios"):
                update_employee(
                    selected_id,
                    {
                        "Department": new_department,
                        "JobRole": new_jobrole,
                        "Tipocontrato": new_tipocontrato,
                        "MonthlyIncome": new_monthlyincome
                    }
                )
                st.cache_data.clear()
                st.rerun()

        with col_delete:
            if st.form_submit_button("🗑️ Eliminar"):
                delete_employee(selected_id)
                st.cache_data.clear()
                st.rerun()















