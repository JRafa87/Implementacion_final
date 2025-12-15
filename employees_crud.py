with st.form("add_employee_form", clear_on_submit=True):

    st.subheader("Datos Generales")

    col1, col2 = st.columns(2)

    with col1:
        new_employee_number = st.number_input(
            "EmployeeNumber (ID)",
            value=next_id,
            disabled=True
        )

        new_age = st.number_input("Age", 18, 100, 30)
        new_gender = st.selectbox("Gender", ["Male", "Female"])
        new_maritalstatus = st.selectbox("MaritalStatus", ["Single", "Married", "Divorced"])
        new_department = st.selectbox("Department", ["HR", "Tech", "Finance", "Marketing"])
        new_jobrole = st.selectbox("JobRole", ["Manager", "Developer", "Analyst", "Support"])
        new_joblevel = st.number_input("JobLevel", 1, 5, 1)

    with col2:
        new_monthlyincome = st.number_input("MonthlyIncome", min_value=0.0)
        new_percenthike = st.number_input("PercentSalaryHike", 0, 100, 10)
        new_businesstravel = st.selectbox(
            "BusinessTravel",
            ["Rarely", "Frequently", "Non-Travel"]
        )
        new_overtime = st.radio("OverTime", ["Yes", "No"])
        new_performance = st.number_input("PerformanceRating", 1, 5, 3)
        new_distance = st.number_input("DistanceFromHome", 0, 100, 5)

    st.subheader("Historial Laboral")

    col3, col4 = st.columns(2)

    with col3:
        new_education = st.number_input("Education", 1, 5, 3)
        new_educationfield = st.text_input("EducationField")
        new_numcompanies = st.number_input("NumCompaniesWorked", 0)
        new_totalyears = st.number_input("TotalWorkingYears", 0)
        new_yearsatcompany = st.number_input("YearsAtCompany", 0)

    with col4:
        new_yearsincurrentrole = st.number_input("YearsInCurrentRole", 0)
        new_yearssincelastpromotion = st.number_input("YearsSinceLastPromotion", 0)
        new_yearswithmanager = st.number_input("YearsWithCurrManager", 0)
        new_training = st.number_input("TrainingTimesLastYear", 0)
        new_tipocontrato = st.selectbox("Tipo de Contrato", ["Indefinido", "Temporal"])

    st.subheader("Asistencia y Fechas")

    col5, col6 = st.columns(2)

    with col5:
        new_tardanzas = st.number_input("NumeroTardanzas", 0)
        new_faltas = st.number_input("NumeroFaltas", 0)

    with col6:
        new_fechaingreso = st.text_input("FechaIngreso (dd/mm/yyyy)")
        new_fechasalida = st.text_input("FechaSalida (dd/mm/yyyy)", value="")

    col_save, col_cancel = st.columns(2)

    with col_save:
        if st.form_submit_button("💾 Guardar Nuevo Empleado"):
            employee_data = {
                "employeenumber": int(new_employee_number),
                "age": new_age,
                "gender": new_gender,
                "maritalstatus": new_maritalstatus,
                "department": new_department,
                "jobrole": new_jobrole,
                "joblevel": new_joblevel,
                "monthlyincome": new_monthlyincome,
                "percentsalaryhike": new_percenthike,
                "businesstravel": new_businesstravel,
                "overtime": new_overtime,
                "performancerating": new_performance,
                "distancefromhome": new_distance,
                "education": new_education,
                "educationfield": new_educationfield,
                "numcompaniesworked": new_numcompanies,
                "totalworkingyears": new_totalyears,
                "yearsatcompany": new_yearsatcompany,
                "yearsincurrentrole": new_yearsincurrentrole,
                "yearssincelastpromotion": new_yearssincelastpromotion,
                "yearswithcurrmanager": new_yearswithmanager,
                "trainingtimeslastyear": new_training,
                "tipocontrato": new_tipocontrato,
                "numerotardanzas": new_tardanzas,
                "numerofaltas": new_faltas,
                "fechaingreso": new_fechaingreso,
                "fechasalida": new_fechasalida or None
            }

            add_employee(employee_data)
            st.session_state["show_add_form"] = False
            clear_cache_and_rerun()

    with col_cancel:
        if st.form_submit_button("❌ Cancelar"):
            st.session_state["show_add_form"] = False
            st.rerun()












