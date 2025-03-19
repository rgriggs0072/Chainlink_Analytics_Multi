import pandas as pd
from prophet import Prophet
import streamlit as st


import openai


# ✅ Load API key from Streamlit secrets
openai.api_key = st.secrets["openai"]["api_key"]


def detect_anomalies(df):
    """Detects sales anomalies using Facebook Prophet."""
    
    if df.empty:
        return pd.DataFrame()  # Return empty DataFrame if no data

    # Aggregate data at the STORE + PRODUCT level
    df_grouped = df.groupby(["LAST_UPLOAD_DATE", "PRODUCT_NAME"]).agg({"PURCHASED_YES_NO": "sum"}).reset_index()
    df_grouped = df_grouped.rename(columns={"LAST_UPLOAD_DATE": "ds", "PURCHASED_YES_NO": "y"})  # Prophet format

    # ✅ Check for missing values and fill them
    if df_grouped.isnull().values.any():
        print("⚠️ Missing values detected. Filling NaNs...")
        df_grouped = df_grouped.fillna(0)  # Replace NaN with 0

    # ✅ Ensure the 'ds' column is datetime type
    df_grouped["ds"] = pd.to_datetime(df_grouped["ds"], errors='coerce')

    # ✅ Remove any remaining NaN values
    df_grouped = df_grouped.dropna()

    # ✅ Ensure there are no negative or infinite values
    df_grouped = df_grouped[df_grouped["y"] >= 0]

    # ✅ Verify data before fitting
    if df_grouped.empty:
        print("⚠️ No valid data points available for Prophet.")
        return pd.DataFrame()  # Return empty DataFrame

    # ✅ Fit the Prophet model
    model = Prophet()
    try:
        model.fit(df_grouped)
    except Exception as e:
        print(f"❌ Prophet fitting failed: {e}")
        return pd.DataFrame()  # Return empty DataFrame if Prophet fails

    # Generate future predictions
    future = model.make_future_dataframe(periods=30)  # Predict next 30 days
    forecast = model.predict(future)

    # Detect anomalies (deviations from forecast)
    df_grouped["forecast"] = forecast["yhat"].values[:len(df_grouped)]
    df_grouped["anomaly"] = abs(df_grouped["y"] - df_grouped["forecast"]) > 1.0 * df_grouped["forecast"].std()

    return df_grouped[df_grouped["anomaly"] == True]  # Return only anomalies




def generate_ai_insight(anomalies):
    """Generate AI insights based on detected anomalies."""
    
    if anomalies.empty:
        return "No significant anomalies detected in the last 90 days."

    prompt = f"""
    The following sales anomalies were detected:

    {anomalies.to_string(index=False)}

    Provide an explanation for these anomalies and suggest actions to improve sales and reduce gaps.
    """

    # ✅ Ensure OpenAI API key is set
    client = openai.OpenAI(api_key=openai.api_key)

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are an expert retail sales analyst."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content




def analyze_forecast(file):
    """Uses OpenAI to analyze forecast data and generate insights."""
    df = pd.read_csv(file)

    # Summarize key trends using OpenAI
    summary_prompt = f"""
    Analyze the following sales forecast data and provide key insights:
    {df.head(20).to_string(index=False)}
    """

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert in business analytics."},
            {"role": "user", "content": summary_prompt}
        ]
    )

    return response["choices"][0]["message"]["content"]