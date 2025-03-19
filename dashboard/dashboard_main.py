# dashboard.py
import streamlit as st

from db_utils.snowflake_utils import (
    get_snowflake_toml,
    create_gap_report,
    fetch_chain_schematic_data,
    execute_query_and_close_connection,
    fetch_supplier_schematic_summary_data,
    fetch_supplier_names,  # Updated to use as originally intended
    check_and_process_data,
)
import pandas as pd
import altair as alt
from io import BytesIO
from datetime import datetime





def fetch_distinct_values(engine, table, column):
    query = f'SELECT DISTINCT "{column}" FROM "{table}"'
    try:
        df = pd.read_sql_query(query, engine)
        return df[column].tolist()
    except Exception as e:
        st.error(f"Error querying {table} table: {e}")
        return []


def display_dashboard(authenticator):
    # Create a SQLAlchemy engine for Snowflake
    engine = get_snowflake_toml(st.session_state.get("toml_info"))

    # Fetch distinct options
    salesperson_options = fetch_distinct_values(engine, "SALESPERSON", "SALESPERSON")
    store_options = fetch_distinct_values(engine, "CUSTOMERS", "CHAIN_NAME")
    supplier_options = fetch_distinct_values(engine, "SUPPLIER_COUNTY", "SUPPLIER")

    # Sort and add "All" option
    for options in [salesperson_options, store_options, supplier_options]:
        options.sort()
        options.insert(0, "All")

    # Sidebar form for filtering
    with st.sidebar.form(key="Gap Report Report", clear_on_submit=True):
        salesperson = st.selectbox("Filter by Salesperson", salesperson_options)
        store = st.selectbox("Filter by Chain", store_options)
        supplier = st.selectbox("Filter by Supplier", supplier_options)
        submitted = st.form_submit_button("Generate Gap Report")

    if submitted:
        with st.spinner("Generating report..."):
            temp_file_path = create_gap_report(
                engine, salesperson=salesperson, store=store, supplier=supplier
            )
            with open(temp_file_path, "rb") as f:
                bytes_data = f.read()
            today = datetime.today().strftime("%Y-%m-%d")
            st.sidebar.download_button(
                label="Download Gap Report",
                data=bytes_data,
                file_name=f"Gap_Report_{today}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    # Retrieve toml_info from session state
    toml_info = st.session_state.get("toml_info")
    if not toml_info:
        st.error("TOML information is not available. Please check the tenant ID and try again.")
        return

    # Display Execution Summary
    result = display_execution_summary(toml_info)
    if result is None:
        st.error("Failed to retrieve execution summary.")
        return

    # Extract values from the result
    total_in_schematic, total_purchased, total_gaps, formatted_percentage = result
    Revenue_missed = total_gaps * 40.19

    # Header
    tenant_name = toml_info["tenant_name"]
    st.header(f"{tenant_name} Chain Dashboard")

    # Execution Summary and Bar Chart
    with st.container():
        col1, col2 = st.columns(2)

        # Execution Summary
        with col1:
            st.markdown(
                f"""
                <div class="card text-secondary p-3 mb-2" style="max-width: 45rem; background-color: #F8F2EB; border: 2px solid #dee2e6; text-align: center; height: 400px;">
                    <div class="card-body" style="overflow-y: auto;">
                        <h5 class="card-title">Execution Summary</h5>
                        <p class="card-text">Total In Schematic: {total_in_schematic}</p>
                        <p class="card-text">Total Purchased: {total_purchased}</p>
                        <p class="card-text">Total Gaps: {total_gaps}</p>
                        <p class="card-text">Overall Purchased Percentage: {formatted_percentage}%</p>
                        <p>Overall Missed Revenue: ${Revenue_missed: .2f}</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Bar Chart
        with col2:
            chain_schematic_data = fetch_chain_schematic_data(toml_info)
            bar_chart = (
                alt.Chart(chain_schematic_data)
                .mark_bar()
                .encode(
                    x="CHAIN_NAME",
                    y="TOTAL_IN_SCHEMATIC",
                    color=alt.Color("CHAIN_NAME", scale=alt.Scale(scheme="viridis")),
                    tooltip=[
                        "CHAIN_NAME",
                        "TOTAL_IN_SCHEMATIC",
                        "PURCHASED",
                        "PURCHASED_PERCENTAGE",
                    ],
                )
                .properties(width=800, height=400, background="#F8F2EB")
            )
            col2.altair_chart(bar_chart, use_container_width=False)

    # Salesperson Execution Summary and Pivot Table
    with st.container():
        row2_col1, row2_col2 = st.columns([40, 70], gap="small")

        # Salesperson Execution Summary
        query = """
            SELECT SALESPERSON, TOTAL_DISTRIBUTION, TOTAL_GAPS, EXECUTION_PERCENTAGE 
            FROM SALESPERSON_EXECUTION_SUMMARY 
            ORDER BY TOTAL_GAPS DESC
        """
        salesperson_df = pd.read_sql_query(query, engine)
        salesperson_df["EXECUTION_PERCENTAGE"] = salesperson_df["EXECUTION_PERCENTAGE"].astype(float).round(2)
        limited_salesperson_df = salesperson_df.head(100)

        # Display table in Column 1
        row2_col1.markdown(
            f"""
            <div style='max-height: 365px; overflow-y: auto; background-color: #F8F2EB; text-align: center;'>
                {limited_salesperson_df.to_html(classes=["table", "table-striped"], escape=False, index=False)}
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Download button for Salesperson Summary
        excel_data = BytesIO()
        limited_salesperson_df.to_excel(excel_data, index=False)
        row2_col1.download_button(
            "Download Salesperson Summary",
            data=excel_data,
            file_name="salesperson_execution_summary.xlsx",
        )

        # Gap Pivot Table
        gap_query = """
            SELECT SALESPERSON, TOTAL_GAPS, EXECUTION_PERCENTAGE, LOG_DATE 
            FROM SALESPERSON_EXECUTION_SUMMARY_TBL 
            ORDER BY TOTAL_GAPS DESC
        """
        gap_df = pd.read_sql_query(gap_query, engine)
        gap_df_pivot = gap_df.pivot_table(index="SALESPERSON", columns="LOG_DATE", values="TOTAL_GAPS", margins=False)
        gap_df_pivot.columns = pd.to_datetime(gap_df_pivot.columns).strftime("%y/%m/%d")

        # Display Pivot Table in Column 2
        row2_col2.markdown(
            f"""
            <div style='max-height: 365px; overflow-y: auto; background-color: #F8F2EB;'>
                {gap_df_pivot.to_html(classes=["table", "table-striped"], escape=False)}
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Download button for Gap History
        excel_data_pivot = BytesIO()
        gap_df_pivot.to_excel(excel_data_pivot, index=True)
        row2_col2.download_button(
            "Download Gap History",
            data=excel_data_pivot,
            file_name="gap_history_report.xlsx",
        )

    # Supplier Selection and Scatter Chart
    row3_col1 = st.columns([100], gap="small")[0]
    with row3_col1:
        st.markdown(
            "<h1 style='text-align: center; font-size: 18px;'>Execution Summary by Product by Supplier</h1>",
            unsafe_allow_html=True,
        )

        supplier_names = fetch_supplier_names()  # No arguments passed as per original function
        if not supplier_names:
            st.error("Failed to fetch supplier names")
            return

        selected_suppliers = st.sidebar.multiselect(
            "Select Suppliers",
            supplier_names,
            default=st.session_state.get("selected_suppliers", []),
        )
        st.session_state["selected_suppliers"] = selected_suppliers

        if selected_suppliers:
            df = fetch_supplier_schematic_summary_data(selected_suppliers)
            if df is not None and not df.empty:
                df["Purchased_Percentage_Display"] = df["Purchased_Percentage"] / 100
                scatter_chart = (
                    alt.Chart(df)
                    .mark_circle()
                    .encode(
                        x="Total_In_Schematic",
                        y=alt.Y("Purchased_Percentage_Display:Q", title="Purchased Percentage"),
                        color="PRODUCT_NAME",
                        tooltip=[
                            "PRODUCT_NAME",
                            "UPC",
                            "Total_In_Schematic",
                            "Total_Purchased",
                            alt.Tooltip(
                                "Purchased_Percentage_Display:Q", format=".2%", title="Purchased Percentage"
                            ),
                        ],
                    )
                    .interactive()
                )
                st.altair_chart(scatter_chart, use_container_width=True)
            else:
                st.write("No data available for the selected suppliers.")
        else:
            st.write("Please select suppliers to view the chart.")




# =================================================================================================================================================
# END Creates scatter chart for product execution by supplier
# =================================================================================================================================================



#-------------- END Handles Setting Up DASHBOARD -----------------------------------------------------------------   



def display_execution_summary(toml_info):
    conn_toml = get_snowflake_toml(toml_info)
    if conn_toml is None:
        return 0, 0, 0, "0.00"

    cursor = conn_toml.cursor()
    query = """
        SELECT 
        SUM("In_Schematic") AS TOTAL_IN_SCHEMATIC,
        SUM("PURCHASED_YES_NO") AS PURCHASED,
        (SUM("PURCHASED_YES_NO") / NULLIF(COUNT(*),0)) AS PURCHASED_PERCENTAGE
    FROM GAP_REPORT;
    """

    try:
        cursor.execute(query)
        result = cursor.fetchone()

        cursor.close()
        conn_toml.close()

        if result and any(result):
            total_in_schematic = result[0] or 0
            purchased = result[1] or 0
            purchased_percentage = result[2] or 0
            formatted_percentage = f"{purchased_percentage * 100:.2f}"

            total_gaps = total_in_schematic - purchased

            return total_in_schematic, purchased, total_gaps, formatted_percentage
        else:
            return 0, 0, 0, "0.00"
    except Exception as e:
        #logging.error(f"Failed execution summary query: {e}")
        st.error(f"Query Error: {str(e)}")
        return 0, 0, 0, "0.00"


    cursor.close()
    conn_toml.close()



