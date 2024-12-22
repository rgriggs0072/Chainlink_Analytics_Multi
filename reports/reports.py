import streamlit as st



import pandas as pd


# ------------- Custom Import Modules ---------------------------------------------------------------------------------------------------------------------------

# from Home import create_snowflake_connection  # Get connection object
# from dg_pivot_transformation import format_pivot_table
# from dg_non_pivot_format import format_non_pivot_table
# from Distro_Grid_Snowflake_Uploader import update_spinner, upload_distro_grid_to_snowflake

#from auth import  user_login  #login_form
#from menu import menu_with_redirect
#from util import apply_custom_style, add_logo, get_logo_url, get_logo_path, render_additional_reports_sidebar, style_metric_cards
from db_utils.snowflake_utils import create_gap_report, get_snowflake_connection, execute_query_and_close_connection, get_snowflake_toml, validate_toml_info  #, fetch_and_store_toml_in





#----------------------  Setup page, menu, sidebar, page header  ----------------------------------------------------------------



# Redirect to Chainlink_Main.py if not logged in, otherwise show the navigation menu
# render_additional_reports_sidebar()
# menu_with_redirect()


# Sets the page header

# Set Page Header
st.header("Misc Reports and Analytics")

# Set custom CSS for hr element
st.markdown("""
        <style>
            hr {
                margin-top: 0.5rem;
                margin-bottom: 0.5rem;
                height: 3px;
                background-color: #333;
                border: none;
            }
        </style>
    """, unsafe_allow_html=True)
# Dividing sections of the page starting with the header  There will be a line between all elements
# Add horizontal line
st.markdown("<hr>", unsafe_allow_html=True)

#----------------------END  Setup page, menu, sidebar, page header  ----------------------------------------------------------------

#------------------------------------------------------------------------------------------------------------------------------------------

#======================================================================================================================================

# Load Product Data function to the product table within snowflake
#======================================================================================================================================
# Load Product Data function to the product table within Snowflake
def fetch_product_analysis_data():
    # Retrieve toml_info from session
    toml_info = st.session_state.get('toml_info')
    #st.write(toml_info)
    if not toml_info:
        st.error("TOML information is not available. Please check the tenant ID and try again.")
        return
    
    conn_toml = get_snowflake_toml(toml_info)

    # Create a cursor object
    cursor = conn_toml.cursor()

    # Execute the SQL query against the PRODUCT_ANALYSIS view and fetch the results into a DataFrame
    sql_query = """
    SELECT
        STORE_NAME,
        PRODUCT_NAME,
        SALESPERSON,
        UPC,
        _COUNT AS ProductCount
    FROM
        PRODUCT_ANALYSIS;  
    """
    cursor = conn_toml.cursor()
    cursor.execute(sql_query)
    results = cursor.fetchall()
    df = pd.DataFrame(results, columns=["Store", "Product", "Salesperson", "UPC", "ProductCount"])
    df['Salesperson'].fillna('Unknown', inplace=True)

    #st.write(df)

    # Close the cursor and connection
    cursor.close()
    conn_toml.close()

    return df





#===================================================================================================================================

# Button to call the product analysis data function above
#====================================================================================================================================

# Button to fetch and display the product analysis data
if st.button("Fetch Product Analysis Pivot Data"): 
    with st.spinner('Getting Product Analysis Data From Snowflake ...'):
    # Fetch the data
     df = fetch_product_analysis_data()

#====================================================================================================================================
#Create the excel pivot table and provide download button    
     # Pivot table creation
     pivot_table = pd.pivot_table(df, values="ProductCount", index=["UPC", "Product","Salesperson" ], columns="Store", fill_value=0)

     # Add total by salesperson
    pivot_table["Total"] = pivot_table.sum(axis=1)



    # Save the pivot table as an Excel file
    excel_file_path = "product_analysis_pivot.xlsx"
    pivot_table.to_excel(excel_file_path)

# Download button for the Excel file
    st.download_button(
        label="Download Product Analysis Report",
        data=open(excel_file_path, "rb").read(),
        file_name=excel_file_path,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )



#====================================================================================================================================

# Function to pull Schematic Summary Data from snowflake

#===================================================================================================================================

def fetch_schematic_summary_data():
     # Retrieve toml_info from session
    toml_info = st.session_state.get('toml_info')
    #st.write(toml_info)
    if not toml_info:
        st.error("TOML information is not available. Please check the tenant ID and try again.")
        return
    
    conn_toml = get_snowflake_toml(toml_info)

    # Create a cursor object
    cursor = conn_toml.cursor()

    # Execute the SQL query against the schematic_summary view and fetch the results into a DataFrame
    sql_query = """
    SELECT 
    "dg_upc" AS UPC,
    SUPPLIER,
    PRODUCT_NAME,
    SUM("In_Schematic") AS Total_In_Schematic,
    SUM(PURCHASED_YES_NO) AS Total_Purchased,
    (SUM(PURCHASED_YES_NO) / SUM("In_Schematic")) * 100 AS Purchased_Percentage
     
FROM
    GAP_REPORT_TMP2
    where "sc_STATUS" = 'Yes'
    group by supplier, "dg_upc", product_name
    order by supplier;
    """
    cursor = conn_toml.cursor()
    cursor.execute(sql_query)
    results = cursor.fetchall()
    df = pd.DataFrame(results, columns=["UPC", "SUPPLIER", "PRODUCT_NAME", "Total_In_Schematic", "Total_Purchased", "PURCHASED_PERCENTAGE"])
    #st.write(df)
    # Ensure 'PURCHASED_PERCENTAGE' is treated as a numeric (float) type
    df['PURCHASED_PERCENTAGE'] = df['PURCHASED_PERCENTAGE'].astype(float)
    # Remove rows with NaN values in 'PURCHASED_PERCENTAGE'
    df['Total_Purchased'].fillna(0, inplace=True)
    df['PURCHASED_PERCENTAGE'].fillna(0, inplace=True)
    # Perform rounding and formatting
    df['PURCHASED_PERCENTAGE'] = (df['PURCHASED_PERCENTAGE']).apply(lambda x: f"{x:.2f}%")

    #st.write(df)

    # Close the cursor and connection
    cursor.close()
    conn_toml.close()

    return df

#==================================================================================================================================
# Button to call the Scehmatic Summary data function above and create the excel file and a button to download the file
#====================================================================================================================================

# Button to fetch and display the product analysis data
if st.button("Fetch Schematic Summary Data"): 
    with st.spinner('Getting Schematic Summary Data From Snowflake ...'):
    # Fetch Schematic Summary Data
     df = fetch_schematic_summary_data()

# Download button for the Excel file
    excel_file_path = "SCHEMATIC_SUMMARY_DATA.xlsx"
    df.to_excel(excel_file_path, index=False)

    st.download_button(
        label="Download Schematic Summary Data",
        data=open(excel_file_path, "rb").read(),
        file_name=excel_file_path,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    