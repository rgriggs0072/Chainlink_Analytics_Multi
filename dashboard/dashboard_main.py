# dashboard.py
import streamlit as st

from db_utils.snowflake_utils import get_snowflake_toml, create_gap_report, get_snowflake_connection
import openpyxl
import pandas as pd
import altair as alt
from db_utils.snowflake_utils import fetch_chain_schematic_data, get_snowflake_toml, fetch_and_store_toml_info, execute_query_and_close_connection,fetch_supplier_schematic_summary_data
from db_utils.snowflake_utils import get_tenant_id,fetch_supplier_names
from io import BytesIO


from datetime import datetime


def display_dashboard(authenticator):

   # Sidebar - Input for gap report parameters
    st.sidebar.title("Gap Analysis Parameters")

    # Create a connection to Snowflake
    conn_toml = get_snowflake_toml(st.session_state.get('toml_info'))
    cursor = conn_toml.cursor()
    
   
    cursor.execute("SELECT current_database(), current_schema()")
    database_info = cursor.fetchone()
    st.write(f"Connected to database: {database_info[0]}, schema: {database_info[1]}")
   
    try:
        
        salesperson_options = pd.read_sql('SELECT DISTINCT "SALESPERSON" FROM "SALESPERSON"', conn_toml)['SALESPERSON'].tolist()
    except Exception as e:
        st.error(f"Error querying Salesperson table: {e}")


    store_options = pd.read_sql("SELECT DISTINCT CHAIN_NAME FROM CUSTOMERS", conn_toml)['CHAIN_NAME'].tolist()
    supplier_options = pd.read_sql("SELECT DISTINCT SUPPLIER FROM SUPPLIER_COUNTY", conn_toml)['SUPPLIER'].tolist()

    salesperson_options.sort()
    store_options.sort()
    supplier_options.sort()

    salesperson_options.insert(0, "All")
    store_options.insert(0, "All")
    supplier_options.insert(0, "All")

    with st.sidebar.form(key="Gap Report Report", clear_on_submit=True):
        salesperson = st.selectbox("Filter by Salesperson", salesperson_options)
        store = st.selectbox("Filter by Chain", store_options)
        supplier = st.selectbox("Filter by Supplier", supplier_options)
        submitted = st.form_submit_button("Generate Gap Report")

    df = None

    with st.sidebar:
        if submitted:
            with st.spinner('Generating report...'):
                temp_file_path = create_gap_report(conn_toml, salesperson=salesperson, store=store, supplier=supplier)
                with open(temp_file_path, 'rb') as f:
                    bytes_data = f.read()
                today = datetime.today().strftime('%Y-%m-%d')
                file_name = f"Gap_Report_{today}.xlsx"

                downloadcontainer = st.container()
                with downloadcontainer:
                    st.download_button(label="Download Gap Report", data=bytes_data, file_name=file_name, mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    st.write("File will be downloaded to your local download folder")

                container = st.container()
                with container:
                    st.spinner('Generating report...')


    # Retrieve toml_info from session state
    toml_info = st.session_state.get('toml_info', None)
    if not toml_info:
        st.error("TOML information is not available. Please check the tenant ID and try again.")
        return

   

     # Check for TOML info before rendering the dashboard
    toml_info = st.session_state.get('toml_info')
    if not toml_info:
        st.error("TOML information is not available. Please check the tenant ID and try again.")
        return

    tenant_name = toml_info.get('tenant_name', 'Unknown Tenant')
    #st.header(f"{tenant_name} Chain Dashboard")
    
        
    # Get the results from the display_execution_summary function
    result = display_execution_summary(toml_info)
    
    if result is None:
        st.error("Failed to retrieve execution summary.")
        return
    
    # Extract individual values from the result tuple
    total_in_schematic, total_purchased, total_gaps, formatted_percentage = result
    Revenue_missed = total_gaps * 40.19
    # Display dashboard header
    tenant_name = toml_info['tenant_name']
    st.header(f"{tenant_name} Chain Dashboard")

    # ====================================================================================================================================================
    # Execution Summary and Bar Chart in two columns (Row 1)
    # ====================================================================================================================================================
    with st.container():
        col1, col2 = st.columns(2)
        
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
                unsafe_allow_html=True
            )
        

        

        with col2:
            # Fetch chain schematic data and create a bar chart
            chain_schematic_data = fetch_chain_schematic_data(toml_info)
            bar_chart = alt.Chart(chain_schematic_data).mark_bar().encode(
                x='CHAIN_NAME',
                y='TOTAL_IN_SCHEMATIC',
                color=alt.Color('CHAIN_NAME', scale=alt.Scale(scheme='viridis')),
                tooltip=['CHAIN_NAME', 'TOTAL_IN_SCHEMATIC', 'PURCHASED', 'PURCHASED_PERCENTAGE']
            ).properties(
                width=800,
                height=400,
                background='#F8F2EB',
            ).configure_title(
                align='center',
                fontSize=16
            ).encode(
                text=alt.Text('CHAIN_NAME')
            )
            col2.altair_chart(bar_chart, use_container_width=False)

    # ====================================================================================================================================================
    # Salesperson Execution Summary (Row 2 Column 1) & Pivot Table for Gaps by Salesperson (Row 2 Column 2)
    # ====================================================================================================================================================
    with st.container():
        row2_col1, row2_col2 = st.columns([40, 70], gap="small")

        # Execute the SQL query to retrieve salesperson execution summary
        query = "SELECT SALESPERSON, TOTAL_DISTRIBUTION, TOTAL_GAPS, EXECUTION_PERCENTAGE FROM SALESPERSON_EXECUTION_SUMMARY ORDER BY TOTAL_GAPS DESC"
        conn_toml = get_snowflake_toml(toml_info)
        result = execute_query_and_close_connection(query, conn_toml)
        salesperson_df = pd.DataFrame(result, columns=['SALESPERSON', 'TOTAL_DISTRIBUTION', 'TOTAL_GAPS', 'EXECUTION_PERCENTAGE'])

        # Format the DataFrame
        salesperson_df['EXECUTION_PERCENTAGE'] = salesperson_df['EXECUTION_PERCENTAGE'].astype(float).round(2)
        limited_salesperson_df = salesperson_df.head(100)

        # Style and display table
        limited_salesperson_df_html = limited_salesperson_df.to_html(classes=["table", "table-striped"], escape=False, index=False)
        table_with_scroll = f"<div style='max-height: 365px; overflow-y: auto; background-color: #F8F2EB; text-align: center;'>{limited_salesperson_df_html}</div>"
        row2_col1.markdown(table_with_scroll, unsafe_allow_html=True)
        # Add download button
        excel_data = BytesIO()
        salesperson_df.to_excel(excel_data, index=False)
        row2_col1.download_button("Download Salesperson Summary", data=excel_data, file_name="salesperson_execution_summary.xlsx", key='download_button')

        # Create and display pivot table for gaps by date
        gap_query = "SELECT SALESPERSON, TOTAL_GAPS, EXECUTION_PERCENTAGE, LOG_DATE FROM SALESPERSON_EXECUTION_SUMMARY_TBL ORDER BY TOTAL_GAPS DESC"
        result = execute_query_and_close_connection(gap_query, conn_toml)
        gap_df = pd.DataFrame(result, columns=['SALESPERSON', 'TOTAL_GAPS', 'EXECUTION_PERCENTAGE', 'LOG_DATE'])

        # Pivot the DataFrame and create a pivot table
        gap_df_pivot = gap_df.pivot_table(index='SALESPERSON', columns='LOG_DATE', values='TOTAL_GAPS', margins=False)
        gap_df_pivot.columns = pd.to_datetime(gap_df_pivot.columns).strftime('%y/%m/%d')
        gap_table_with_scroll = f"<div style='max-height: 365px; overflow-y: auto; background-color: #F8F2EB;'>{gap_df_pivot.to_html(classes=['table', 'table-striped'], escape=False)}</div>"
        row2_col2.markdown(gap_table_with_scroll, unsafe_allow_html=True)

        # Add download button for gaps pivot table
        excel_data_pivot = BytesIO()
        gap_df_pivot.to_excel(excel_data_pivot, index=True)
        row2_col2.download_button("Download Gap History", data=excel_data_pivot, file_name="gap_history_report.xlsx", key='download_gap_button')

    # ====================================================================================================================================================
    # Supplier Selection and Product Scatter Chart (Row 3 Column 1)
    # ====================================================================================================================================================
    row3_col1 = st.columns([100], gap="small")[0]
    with row3_col1:
        st.markdown("<h1 style='text-align: center; font-size: 18px;'>Execution Summary by Product by Supplier</h1>",
                    unsafe_allow_html=True)

        # Sidebar multi-select for supplier selection
        #print("Fetching supplier names...") Debug Statement
        supplier_names = fetch_supplier_names()  # Fetch supplier names
        #print("Supplier names fetched: ", supplier_names)  # Debug the supplier names

        if supplier_names is None:
            st.error("Failed to fetch supplier names")
            return  # Exit if supplier names cannot be fetched

        selected_suppliers = st.sidebar.multiselect(
            "Select Suppliers",
            supplier_names,
            default=st.session_state.get('selected_suppliers', [])
        )

        # Store the selected suppliers in session state
        st.session_state['selected_suppliers'] = selected_suppliers
       # print("Did we get the supplier names here? ", st.session_state['selected_suppliers'])  # Debug statement

        # Display the data
        if st.session_state['selected_suppliers']:
           # print("Selected suppliers: ", st.session_state['selected_suppliers'])  # Debug selected suppliers
            df = fetch_supplier_schematic_summary_data(st.session_state['selected_suppliers'])
            #print("Fetched data: ", df)  # Debug the fetched data

            if df is not None and not df.empty:
                df["Purchased_Percentage"] = df["Purchased_Percentage"].astype(float)
                df["Purchased_Percentage_Display"] = df["Purchased_Percentage"] / 100

                scatter_chart = alt.Chart(df).mark_circle().encode(
                    x='Total_In_Schematic',
                    y=alt.Y('Purchased_Percentage:Q', title='Purchased Percentage'),
                    color='PRODUCT_NAME',
                    tooltip=[
                        'PRODUCT_NAME', 'UPC', 'Total_In_Schematic', 'Total_Purchased',
                        alt.Tooltip('Purchased_Percentage_Display:Q', format='.2%', title='Purchased Percentage')
                    ]
                ).interactive()

                st.altair_chart(scatter_chart, use_container_width=True)

                # Button to clear the selection after displaying the chart
                if st.button("Clear Selection"):
                   #print("Clearing selection...")  # Debug the button press
                    st.session_state['selected_suppliers'] = []  # Clear the list
                    st.rerun()  # Rerun the app to update the UI
            else:
                st.write("No data available to display the chart. Please ensure the suppliers are selected and data exists for them.")
        else:
            st.write("Please select one or more suppliers to view the chart.")

# =================================================================================================================================================
# END Creates scatter chart for product execution by supplier
# =================================================================================================================================================



#-------------- END Handles Setting Up DASHBOARD -----------------------------------------------------------------   



def display_execution_summary(toml_info):
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
        formatted_percentage = f"{df['PURCHASED_PERCENTAGE'].iloc[0] * 100:.2f}"
        return df['TOTAL_IN_SCHEMATIC'].iloc[0], df['PURCHASED'].iloc[0], total_gaps, formatted_percentage
    return None


