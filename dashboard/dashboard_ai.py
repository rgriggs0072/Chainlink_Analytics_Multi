# ------------ Dashboard_ai.py -----------------------------

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from prophet import Prophet
import openai
from db_utils.snowflake_connection import get_snowflake_toml
from io import BytesIO

# ✅ Retrieve API Key from secrets
OPENAI_API_KEY = st.secrets["openai"]["api_key"]

# 📌 Fetch Data from Snowflake (Dynamically Determine Last 2 Years)
def fetch_sales_data(conn, supplier_ids, category, on_off, chain_ind):
    """Fetch sales data from Snowflake and ensure continuous time series."""
    supplier_filter = f"SUPPLIER_ID IN ({', '.join(map(str, supplier_ids))})"
    
    query = f"""
        SELECT YEAR, MONTH, SUPPLIER_ID, {category}, ON_OFF_PREMISE, CHAIN_INDEPENDENT 
        FROM ANALYTICS_MASTER
        WHERE {supplier_filter}
        AND ON_OFF_PREMISE = '{on_off}'
        AND CHAIN_INDEPENDENT = '{chain_ind}'
        ORDER BY YEAR, MONTH;
    """
    df = pd.read_sql(query, conn)

    df["DATE"] = pd.to_datetime(df["YEAR"].astype(str) + "-" + df["MONTH"].astype(str) + "-01")
    df = df[["DATE", "SUPPLIER_ID", category, "ON_OFF_PREMISE", "CHAIN_INDEPENDENT"]].rename(columns={"DATE": "ds", category: "y"})  

    return df

# 📌 Fetch Supplier Names
def fetch_supplier_names(conn):
    query = "SELECT SUPPLIER_ID, SUPPLIER_NAME FROM SUPPLIER_MASTER ORDER BY SUPPLIER_NAME ASC;"
    df = pd.read_sql(query, conn)
    return dict(zip(df["SUPPLIER_ID"], df["SUPPLIER_NAME"]))

# 📌 AI Forecast Analysis
def analyze_forecast(forecast_df):
    """AI-generated insights for sales predictions, including quarterly trends."""
    
    forecast_summary = forecast_df[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].round(2).to_string()

    # Aggregate data by quarters
    forecast_df['QUARTER'] = forecast_df['ds'].dt.quarter
    quarterly_summary = forecast_df.groupby('QUARTER')[['yhat', 'yhat_lower', 'yhat_upper']].sum().round(2).to_string()

    # ✅ Initialize OpenAI Client
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a data scientist and expert in sales forecasting and trend analysis."},
                {"role": "user", "content": f"Analyze this sales forecast and provide key insights:\n\n{forecast_summary}"},
                {"role": "user", "content": f"Additionally, break down the trends by quarter and provide insights on the quarterly trends:\n\n{quarterly_summary}"}
            ]
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"⚠️ AI Analysis Failed: {e}"






# 📌 Determine Last 2 Years Dynamically
def get_training_years(df):
    """Dynamically determine the last two available years for training."""
    available_years = sorted(df["ds"].dt.year.unique(), reverse=True)
    if len(available_years) < 2:
        st.error("Not enough historical data for prediction.")
        st.stop()
    return available_years[:2], available_years[0] + 1  # Returns (last two years, prediction year)

# 📌 Forecast Sales Using Prophet (Excluding Real 2025 Data)
def forecast_sales(df, selected_quarters):
    """Train Prophet model on last two years & compare against real 2025 sales."""
    
    # Dynamically determine training years & prediction year
    training_years, prediction_year = get_training_years(df)

    # Train model using ONLY 2023 and 2024 data
    df = pd.concat([df, df[df["ds"].dt.year == 2024]])  # Double weight of 2024
    train_df = df[df["ds"].dt.year.isin([2023, 2024])]

    train_df = df[df["ds"].dt.year.isin([2023, 2024])]
    
    model = Prophet(
        yearly_seasonality=2,  # We will add it manually
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.02,  # Prevent overfitting trends
        seasonality_prior_scale=5.0  # Reduce seasonal impact
    )
    # Add Custom Yearly Seasonality
    model.add_seasonality(name='yearly', period=12, fourier_order=8)


    model.fit(train_df)

    # Generate predictions for all 12 months of 2025
    future = model.make_future_dataframe(periods=13, freq='M')
    future = future[future["ds"].dt.year == 2025]  # Filter only for 2025
    forecast = model.predict(future)


    # Filter to selected quarters
    future["QUARTER"] = future["ds"].dt.quarter
    future = future[future["QUARTER"].isin(selected_quarters)]

    forecast = model.predict(future)
    return forecast, training_years, prediction_year


# 📌 Plot Monthly Trends Line Chart (Now Includes Real Jan & Feb Data)
def plot_monthly_trends(df, forecast, category, supplier_name, training_years, prediction_year):
    """Plots actuals for last two years, real Jan & Feb data, and predictions for the current year."""
    fig, ax = plt.subplots(figsize=(12, 6))

    # Ensure correct month ordering
    month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    df["YEAR"] = df["ds"].dt.year
    df["MONTH"] = df["ds"].dt.strftime('%b')
    df["MONTH_NUM"] = df["ds"].dt.month

    df = df.sort_values(by=["MONTH_NUM"])  # Sort by numeric month

    # Plot last two years dynamically
    colors = ["black", "gray"]
    for i, year in enumerate(training_years):
        yearly_data = df[df["YEAR"] == year].groupby("MONTH")["y"].sum()
        yearly_data = yearly_data.reindex(month_order)  # Force month order
        ax.plot(yearly_data.index, yearly_data, linestyle="-", color=colors[i], label=f"Actual {year}")

    # Forecasted data
    forecast["YEAR"] = forecast["ds"].dt.year
    forecast["MONTH"] = forecast["ds"].dt.strftime('%b')
    forecast["MONTH_NUM"] = forecast["ds"].dt.month
    forecast = forecast.sort_values(by=["MONTH_NUM"])  # Sort forecast correctly

    forecast_current_year = forecast[forecast["YEAR"] == prediction_year].groupby("MONTH")["yhat"].sum()
    forecast_current_year = forecast_current_year.reindex(month_order)  # Force month order

    ax.plot(forecast_current_year.index, forecast_current_year, linestyle="dashed", color="blue", label=f"Predicted {prediction_year}")

    # Add Real Sales Data for Jan & Feb
    if "real_sales" in st.session_state:
        real_sales_df = pd.DataFrame(st.session_state["real_sales"])
        if not real_sales_df.empty:
            real_sales_df["ds"] = pd.to_datetime(real_sales_df["ds"])
            real_sales_df["MONTH"] = real_sales_df["ds"].dt.strftime('%b')
            real_sales_df["MONTH_NUM"] = real_sales_df["ds"].dt.month
            real_sales_df = real_sales_df[real_sales_df["ds"].dt.year == prediction_year].groupby("MONTH")["y"].sum()
            real_sales_df = real_sales_df.reindex(["Jan", "Feb"])

            ax.plot(real_sales_df.index, real_sales_df, linestyle="-", color="red", label=f"Real {prediction_year} (Jan & Feb)")

    # 📌 Ensure x-axis always displays Jan → Dec
    ax.set_xticks(range(12))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])


    ax.set_title(f"📊 {category} Monthly Trends for {supplier_name}")
    ax.set_xlabel("Month")
    ax.set_ylabel(category)
    ax.legend()
    
    st.pyplot(fig)


# ✅ Streamlit UI (Now Dynamic for Any Year)
st.title("🧠 AI Predictive Dashboard")
st.write("Analyze and forecast sales trends dynamically.")

toml_info = st.session_state.get('toml_info')
if not toml_info:
    st.error("Missing database connection information.")
    st.stop()


conn = get_snowflake_toml(toml_info)
if conn is None:
    st.error("Unable to connect to Snowflake.")
    st.stop()

# Fetch Supplier Names
supplier_names = fetch_supplier_names(conn)

# UI Filters
supplier_ids = st.multiselect("Select Supplier(s)", options=list(supplier_names.keys()), format_func=lambda x: supplier_names.get(x, x))
category = st.selectbox("Select Metric", ["DOLLAR_VOLUME", "BUYER_COUNT", "PLACEMENT_COUNT"])
on_off = st.selectbox("Select On/Off Premise", ["On Premise", "Off Premise"])
chain_ind = st.selectbox("Select Chain/Independent", ["Chain", "Independent"])

# Quarter Selection Slider
selected_quarters = st.slider("Select Quarters", 1, 4, (1, 4))

# Ensure session state for storing entries
if "real_sales_entries" not in st.session_state:
    st.session_state["real_sales_entries"] = []

# User input form
st.subheader("📌 Enter Real Sales Data for Current Year")

col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])

with col1:
    chain_type = st.selectbox("Chain/Independent", ["Chain", "Independent"], key="chain_select")

with col2:
    premise_type = st.selectbox("On/Off Premise", ["On Premise", "Off Premise"], key="premise_select")

with col3:
    month = st.selectbox("Select Month", 
                         ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                         key="month_select")

with col4:
    sales_value = st.number_input("Sales Amount", min_value=0.0, step=100.0, key="sales_input")

with col5:
    if st.button("Add Entry"):
        # Convert month name to numeric format
        month_num = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                     "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}[month]
        
        # Save entry in session state
        st.session_state["real_sales_entries"].append({
            "ds": f"{pd.Timestamp.now().year}-{month_num:02d}-01",  # Use dynamic current year
            "CHAIN_INDEPENDENT": chain_type,
            "ON_OFF_PREMISE": premise_type,
            "y": sales_value
        })
        st.rerun()  # Update the UI with new data

# Display stored entries
if st.session_state["real_sales_entries"]:
    st.subheader("✅ Entered Sales Data")
    df_entries = pd.DataFrame(st.session_state["real_sales_entries"])
    st.dataframe(df_entries.style.format({"y": "${:,.2f}"}))

# Final submission
if st.button("Submit Sales Data"):
    st.session_state["real_sales"] = st.session_state["real_sales_entries"]
    st.success("Sales data submitted successfully!")
    st.session_state["real_sales_entries"] = []  # Clear session after submission

# ✅ Generate Forecast
if st.button("Generate Forecast") or st.session_state.get("forecast_generated"):
    st.session_state["forecast_generated"] = True  

    with st.spinner("Generating AI Forecast..."):
        df = fetch_sales_data(conn, supplier_ids, category, on_off, chain_ind)
        forecast, training_years, prediction_year = forecast_sales(df, list(range(selected_quarters[0], selected_quarters[1] + 1)))

        supplier_name = ", ".join([supplier_names.get(sid, str(sid)) for sid in supplier_ids])
        plot_monthly_trends(df, forecast, category, supplier_name, training_years, prediction_year)


       # ✅ Show AI-Generated Insights
        st.subheader("🔍 AI-Generated Insights")
        with st.spinner("Analyzing forecast with AI..."):
            ai_insights = analyze_forecast(forecast)
        st.write(ai_insights)


conn.close()
