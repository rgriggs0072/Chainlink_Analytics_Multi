import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from PIL import Image
from openpyxl import Workbook
import snowflake.connector
from openpyxl.utils.dataframe import dataframe_to_rows
import openpyxl
import datetime
from utils.util import format_non_pivot_table, format_pivot_table, validate_chain_name
from db_utils.snowflake_utils import (create_gap_report, get_snowflake_connection, execute_query_and_close_connection,
                                      get_snowflake_toml, validate_toml_info, upload_distro_grid_to_snowflake)
from db_utils.distro_grid_snowflake_uploader import update_spinner, upload_distro_grid_to_snowflake

# Set Page Header
st.header("CHAIN RESET MANAGEMENT")

# Custom CSS for hr element
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

# Add a horizontal line and links to download templates
st.markdown("<hr>", unsafe_allow_html=True)
st.write("Download Template Here:")
st.markdown("[Download Pivot Table Template](https://github.com/rgriggs0072/ChainLinkAnalytics/raw/master/import_templates/Pivot_Table_Distro_Grid_Template.xlsx)")
st.markdown("[Download Distro Grid Template](https://github.com/rgriggs0072/ChainLinkAnalytics/raw/master/import_templates/Distribution_Grid_Template.xlsx)")

# Retrieve chain options from Snowflake

# Function to get chain options from Snowflake for dropdown
def get_options():
    toml_info = st.session_state.get('toml_info')
    if not toml_info:
        st.error("TOML information is not available. Please check the tenant ID and try again.")
        return []
    
    conn_toml = get_snowflake_toml(toml_info)
    cursor = conn_toml.cursor()
    cursor.execute('SELECT option_name FROM options_table ORDER BY option_name')
    
    return [row[0] for row in cursor]

# ====================================================================================================================
# THE FUNCTION TO UPDATE THE CHAIN OPTIONS IN SNOWFLAKE FOR THE DROPDOWN
# ====================================================================================================================
# Function to update options in Snowflake table
def update_options(options):
    # Retrieve toml_info from session
    toml_info = st.session_state.get('toml_info')
   
    if not toml_info:
        st.error("TOML information is not available. Please check the tenant ID and try again.")
        return
    
    conn_toml = get_snowflake_toml(toml_info)

    # Create a cursor object
    cursor = conn_toml.cursor()
    cursor.execute('DELETE FROM options_table')
    for option in options:
        cursor.execute("INSERT INTO options_table (option_name) VALUES (%s)", (option,))
    conn_toml.commit()


# ====================================================================================================================
# END THE FUNCTION TO UPDATE THE CHAIN OPTIONS IN SNOWFLAKE FOR THE DROPDOWN
# ====================================================================================================================


options = get_options()

# Initialize session state variables for options
if 'new_option' not in st.session_state:
    st.session_state.new_option = ""
if 'option_added' not in st.session_state:
    st.session_state.option_added = False

# Dropdown for selecting the chain name, used for both formatting and uploading
if not options:
    st.warning("No options available. Please add options to the list.")
else:
    selected_option = st.selectbox(':red[Select the Chain Distro Grid]', options + ['Add new option...'], key="chain_option")

    # Handle the case where a new chain needs to be added
    if selected_option == 'Add new option...':
        with st.form(key='add_option_form', clear_on_submit=True):
            new_option = st.text_input('Enter the new option', value=st.session_state.new_option)
            submit_button = st.form_submit_button('Add Option')

            if submit_button and new_option:
                options.append(new_option)
                update_options(options)
                st.success('Option added successfully!')
                st.session_state.option_added = True
                st.session_state.new_option = ""  # Clear the text input field

    # Save selected option to session state for use throughout the page
    st.session_state.selected_option = selected_option

# File container to hold the file uploader for formatting the Distribution Grid
file_container = st.container()

with file_container:
    st.subheader(":blue[Distro Grid Formatting Utility]")

# Uploading and Validating Spreadsheet
upload_file_to_format = st.file_uploader(":red[Browse or drag here the Distribution Grid to Format]", type=["xlsx"])

if upload_file_to_format:
    # Validate the chain name in the uploaded spreadsheet
    validate_chain_name(upload_file_to_format, st.session_state.selected_option)

    # Proceed to reformat if validation passes
    workbook = openpyxl.load_workbook(upload_file_to_format)
    user_selection = st.selectbox("Select Yes if a Pivot Table or Select No if not a Pivot Table:",
                                  ["Choose One", "Yes", "No"])

    if user_selection == "Choose One":
        st.info("Please select whether the spreadsheet is a Pivot Table or not.")
    elif user_selection in ["Yes", "No"]:
        if st.button("Reformat DG Spreadsheet"):
            formatted_workbook = None  # Initialize the variable
            stream = BytesIO()  # Define the stream variable

            if user_selection == "Yes":
                formatted_workbook = format_pivot_table(workbook, st.session_state.selected_option)
                st.success("Pivot table formatted successfully.")
            elif user_selection == "No":
                formatted_workbook = format_non_pivot_table(workbook, stream, st.session_state.selected_option)

                # If no warnings are detected, set acknowledged_warnings to True
                if not st.session_state.get('warnings_present', False):
                    st.session_state['acknowledged_warnings'] = True

            # Create a new filename and save the formatted workbook
            new_filename = "formatted_spreadsheet.xlsx"
            if formatted_workbook is not None and (st.session_state['acknowledged_warnings'] or not st.session_state.get('warnings_present', False)):
                formatted_workbook.save(stream)
                stream.seek(0)
                st.download_button(
                    label="Download formatted spreadsheet",
                    data=stream,
                    file_name=new_filename,
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )

# ===========================================================================================================
# create code uploader in preparation to write to snowflake
# ==========================================================================================================

# Create a container to hold the file uploader
snowflake_file_container = st.container()

# Add a title to the container
with snowflake_file_container:
    st.markdown("<hr>", unsafe_allow_html=True)
    st.subheader(":blue[Write Distribution Grid to Snowflake Utility]")


    # create file uploader
    uploaded_files = st.file_uploader("Browse or select formatted Distribution Grid excel sheets", type=["xlsx"],
                                      accept_multiple_files=True)

# Process each uploaded file
for uploaded_file in uploaded_files:
    # Read Excel file into pandas ExcelFile object
    excel_file = pd.ExcelFile(uploaded_file)

    ## Get sheet names from ExcelFile object
    sheet_names = excel_file.sheet_names

    # Display DataFrame for each sheet in Streamlit
    for sheet_name in sheet_names:
        df = pd.read_excel(excel_file, sheet_name=sheet_name)

    # #===========================================================================================================
    # End of code to create code uploader in preparation to write to snowflake
    # ==========================================================================================================
     # Create a connection to Snowflake
    conn_toml = get_snowflake_toml(st.session_state.get('toml_info'))
    cursor = conn_toml.cursor()
    
   
    cursor.execute("SELECT current_database(), current_schema()")
    database_info = cursor.fetchone()
    st.write(f"Connected to database: {database_info[0]}, schema: {database_info[1]}")
   
    # Write DataFrame to Snowflake on button click
    button_key = f"import_button_{uploaded_file.name}_{sheet_name}"
    if st.button("Import Distro Grid into Snowflake", key=button_key):
        with st.spinner('Uploading data to Snowflake ...'):
            # Write DataFrame to Snowflake based on the selected store
            

            upload_distro_grid_to_snowflake(df, selected_option, update_spinner)
