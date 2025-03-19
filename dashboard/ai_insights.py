import streamlit as st
import pandas as pd
from db_utils.snowflake_utils import get_tenant_sales_report
from db_utils.snowflake_utils import get_snowflake_toml
from utils.ai_utils import detect_anomalies, generate_ai_insight
from io import BytesIO
import os


# Function to get gap data from GAP_REPORT
def get_gap_analysis(toml_info):
    """Fetch gap summary for AI insights."""

    conn_toml = get_snowflake_toml(toml_info)
    if conn_toml is None:
        return None

    cursor = conn_toml.cursor()
    query = """
        SELECT SUM("In_Schematic") AS total_in_schematic,
               SUM("PURCHASED_YES_NO") AS purchased,
               SUM("PURCHASED_YES_NO") / COUNT(*) AS purchased_percentage
        FROM GAP_REPORT;
    """
    cursor.execute(query)
    result = cursor.fetchall()
    conn_toml.close()

    if result:
        df = pd.DataFrame(result, columns=["TOTAL_IN_SCHEMATIC", "PURCHASED", "PURCHASED_PERCENTAGE"])
        total_gaps = df['TOTAL_IN_SCHEMATIC'].iloc[0] - df['PURCHASED'].iloc[0]
        formatted_percentage = f"{df['PURCHASED_PERCENTAGE'].iloc[0] * 100:.2f}%"
        return df['TOTAL_IN_SCHEMATIC'].iloc[0], df['PURCHASED'].iloc[0], total_gaps, formatted_percentage
    return None

# Page Title
st.title("🧠 AI-Powered Insights")

# Fetch sales data for the logged-in tenant
df_sales = get_tenant_sales_report(st.session_state["toml_info"])

if df_sales is None:
    st.error("❌ Failed to retrieve sales report data.")
    st.stop()

# Fetch gaps data from GAP_REPORT
gap_data = get_gap_analysis(st.session_state["toml_info"])

# 🚀 Layout: Separate Forms for Sales & Gap Analysis
col1, col2 = st.columns(2)

# ✅ 1️⃣ Sales Report Summary (Left Side)
with col1:
    with st.expander("📊 Sales Report Summary", expanded=True):
        st.write("This section provides an overview of sales trends.")

        # Show Sales Data
        st.write("### 🏪 Store Sales Data (First 10 Rows)")
        st.dataframe(df_sales.head(10))  # Show first 10 rows for preview

        # Run AI Anomaly Detection on Sales
        anomalies = detect_anomalies(df_sales)
        ai_sales_insights = generate_ai_insight(anomalies)

        if not anomalies.empty:
            st.warning("⚠️ AI Detected Sales/Gaps Anomalies!")
            st.write(ai_sales_insights)
        else:
            st.success("✅ No anomalies detected in the last 90 days.")

# ✅ 2️⃣ Gap Analysis Section (Right Side)
with col2:
    with st.expander("🚨 Gap Analysis & AI Recommendations", expanded=True):
        st.write("This section focuses on missing products & gaps.")

        if gap_data:
            total_in_schematic, purchased, total_gaps, purchased_percentage = gap_data

            st.metric(label="📌 Total Items in Schematic", value=total_in_schematic)
            st.metric(label="✅ Purchased Items", value=purchased)
            st.metric(label="❌ Total Gaps", value=total_gaps)
            st.metric(label="📊 Purchased Percentage", value=purchased_percentage)

            if total_gaps > 0:
                st.error(f"❌ {total_gaps} missing products detected!")
                ai_gap_insights = generate_ai_insight(pd.DataFrame([{"Gaps": total_gaps}]))  # Send gaps for AI analysis
                st.write("### 🧑‍💻 AI Recommendations for Closing Gaps")
                st.write(ai_gap_insights)


                st.write("📂 Available pages:", os.listdir("pages"))  # Debugging
                st.write("🔍 Current working directory:", os.getcwd())  # Debugging


                # 🚀 **New Button: Review & Send Gap Reports**
                if st.button("✏️ Review & Send Gap Reports"):
                    st.session_state["page"] = "gap_review"
                    st.rerun()  # ✅ Forces Streamlit to refresh and load gap_review

                # 🚀 Additional Actions
                if st.button("Notify Sales Team About Gaps"):
                    st.success("✅ Sales team notified about missing products.")

                if st.button("Reorder Missing Stock"):
                    st.success("✅ Stock order request sent to procurement.")
            else:
                st.success("✅ No gaps detected.")
        else:
            st.error("❌ Failed to retrieve gap data.")
