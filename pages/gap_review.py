import streamlit as st
import pandas as pd
from db_utils.snowflake_utils import get_snowflake_toml
from email_utils.email_util import send_gap_report

# 🚀 Fetch Salesperson Gaps from Snowflake
def get_salesperson_gaps(toml_info, selected_salesperson="All"):
    conn_toml = get_snowflake_toml(toml_info)
    if conn_toml is None:
        return None

    cursor = conn_toml.cursor()
    
    # ✅ Query only gaps for a specific salesperson or all salespeople
    if selected_salesperson == "All":
        query = "SELECT * FROM GAP_REPORT"
    else:
        query = f"SELECT * FROM GAP_REPORT WHERE SALESPERSON = '{selected_salesperson}'"

    cursor.execute(query)
    result = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]  # Get column names
    conn_toml.close()

    # ✅ Convert results to a DataFrame
    if result:
        df = pd.DataFrame(result, columns=columns)
        return df
    return None

# 🚀 Fetch Unique Salespeople for Selection
df_salespeople = get_salesperson_gaps(st.session_state["toml_info"])  # ✅ Only needed for dropdown

# ✅ Check if data exists before proceeding
if df_salespeople is None or df_salespeople.empty:
    st.success("✅ No gaps found.")
    st.stop()

# 🚀 Salesperson Selection Dropdown
salespeople = ["All"] + list(df_salespeople["SALESPERSON"].unique())  # ✅ Only used for dropdown
selected_salesperson = st.selectbox("📌 Select Salesperson to Review", salespeople)

# 🚀 Fetch Gaps for Selected Salesperson
df_filtered = get_salesperson_gaps(st.session_state["toml_info"], selected_salesperson)

if df_filtered is None or df_filtered.empty:
    st.success(f"✅ No gaps found for {selected_salesperson}.")
    st.stop()

# 🚀 Brewer Filter (Optional)
brewers = ["All"] + sorted(df_filtered["SUPPLIER"].unique())
selected_brewer = st.selectbox("🍺 Filter by Brewer", brewers)

if selected_brewer != "All":
    df_filtered = df_filtered[df_filtered["SUPPLIER"] == selected_brewer]  # ✅ Show only selected Brewer

# ✅ Initialize session state to store edited DataFrame
if "edited_df" not in st.session_state:
    st.session_state["edited_df"] = df_filtered.copy()


# ✅ Add a delete column for row selection & move it to the first column
# 🚀 Ensure "DELETE" column is only added once & always appears first
if "DELETE" in st.session_state["edited_df"].columns:
    st.session_state["edited_df"].drop(columns=["DELETE"], inplace=True)

st.session_state["edited_df"].insert(0, "DELETE", False)  # ✅ Always insert "DELETE" as first column

st.write(f"### ✏️ Edit Gap Report for {selected_salesperson}")

# 🚀 Editable DataFrame (Users can check boxes to delete rows)
edited_df = st.data_editor(st.session_state["edited_df"], key="gap_editor")

# 🚀 Handle Row Deletion
if st.button("🗑 Remove Selected Rows"):
    # ✅ Keep only rows where DELETE is False
    st.session_state["edited_df"] = edited_df[edited_df["DELETE"] == False].drop(columns=["DELETE"])
    st.success(f"✅ Rows successfully removed.")
    st.rerun()  # ✅ Refresh to apply changes



# 🚀 Download Updated Report
st.download_button(
    label="📥 Download Excel",
    data=st.session_state["edited_df"].to_csv(index=False).encode('utf-8'),
    file_name=f"gap_report_{selected_salesperson}.csv",
    mime="text/csv"
)

# 🚀 Send Email with the Edited Report
if st.button(f"📧 Send Gap Report to {selected_salesperson}"):
    salesperson_email = st.session_state["edited_df"]["SALESPERSON_EMAIL"].iloc[0]  # Get salesperson's email
    email_result = send_gap_report(salesperson_email, selected_salesperson, st.session_state["edited_df"])
    st.success(email_result)
