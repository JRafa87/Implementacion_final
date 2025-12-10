def render_manual_prediction_tab():
    """Renderiza la interfaz completa de simulación y predicción de empleados."""
    
    st.set_page_config(layout="wide", page_title="Predicción de Renuncia 📉")
    st.title("Sistema de Predicción de Riesgo de Renuncia 📉")

    model, scaler, mapping = load_model_artefacts()
    if model is None or scaler is None or mapping is None:
        return

    # Cargar Employee Numbers (Números de empleados)
    employee_map = fetch_employee_numbers()
    
    if employee_map:
        st.subheader("Selecciona un número de empleado:")
        employee_number = st.selectbox("Seleccionar Empleado", options=list(employee_map.keys()))
        if employee_number:
            st.write(f"Empleado seleccionado: {employee_map[employee_number]}")
            
            # Simulación con inputs de ejemplo o manuales
            user_inputs = {}
            for key, value in WHAT_IF_VARIABLES.items():
                # Usar un valor predeterminado según el tipo de variable
                default_value = DEFAULT_MODEL_INPUTS.get(key, 0)
                user_inputs[key] = st.number_input(label=f"Valor de {value}", value=default_value)
            
            if st.button("Predecir Riesgo"):
                predicted_class, prediction_proba = preprocess_and_predict(user_inputs, model, scaler, mapping)
                st.write(f"Resultado: {prediction_proba * 100:.2f}% probabilidad de renuncia." if predicted_class == 1 else "El riesgo de renuncia es bajo.")

