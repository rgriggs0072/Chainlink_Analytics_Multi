from ctypes.wintypes import SIZE
import streamlit as st
import snowflake.connector
import pandas as pd
from PIL import Image
import openpyxl
from io import BytesIO
import numpy as np
from datetime import datetime
from openpyxl.utils.dataframe import dataframe_to_rows

# Custom Import Modules
#from auth import user_login
#from menu import menu_with_redirect
#from util import apply_custom_style, add_logo, get_logo_url, get_logo_path, render_reset_data_update_sidebar, style_metric_cards
from db_utils.snowflake_utils import create_gap_report, get_snowflake_connection, execute_query_and_close_connection, get_snowflake_toml, validate_toml_info
from db_utils.snowflake_utils import upload_reset_data
from Formatting.ResetSH_formatter import format_RESET_schedule
from db_utils.Reset_Schedule_to_Snowflake_Uploader import upload_reset_data




# Redirect to Chainlink_Main.py if not logged in, otherwise show the navigation menu
# render_reset_data_update_sidebar()
# menu_with_redirect()

# Set Page Header   
st.header("CHAIN RESET MANAGEMENT")
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

# Add horizontal line
st.markdown("<hr>", unsafe_allow_html=True)

st.write("Download Template Here:")
# Add a download link for the Excel file
st.markdown("[Download Reset Schedule Template Here:](https://github.com/rgriggs0072/ChainLinkAnalytics/raw/master/import_templates/RESET_SCHEDULE_TEMPLATE.xlsx)")

# Create a container to hold the file uploader
file_container = st.container()

# Function to retrieve options from Snowflake table
def get_options():
    toml_info = st.session_state.get('toml_info')
    if not toml_info:
        st.error("TOML information is not available. Please check the tenant ID and try again.")
        return
    
    conn_toml = get_snowflake_toml(toml_info)
    cursor = conn_toml.cursor()
    try:
        result = execute_query_and_close_connection('SELECT option_name FROM options_table ORDER BY option_name', conn_toml)
        options = [row[0] for row in result]
        return options
    except snowflake.connector.errors.Error as e:
        st.error(f"Error executing query: {str(e)}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        return None

# Function to update options in Snowflake table
def update_options(options):
    toml_info = st.session_state.get('toml_info')
    if not toml_info:
        st.error("TOML information is not available. Please check the tenant ID and try again.")
        return
    
    conn_toml = get_snowflake_toml(toml_info)
    cursor = conn_toml.cursor()
    try:
        cursor.execute('DELETE FROM options_table')
        for option in options:
            cursor.execute("INSERT INTO options_table (option_name) VALUES (%s)", (option,))
        conn_toml.commit()
    except snowflake.connector.errors.Error as e:
        st.error(f"Error updating options: {str(e)}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
    finally:
        cursor.close()

# Call the function Get_Options to populate session state and dropdown
options = get_options()
# Initialize session state variables
if 'new_option' not in st.session_state:
    st.session_state.new_option = ""
if 'option_added' not in st.session_state:
    st.session_state.option_added = False

with file_container:
    st.subheader(":blue[Reset Schedule File Format Utility]")
    
    if not options:
        st.warning("No options available. Please add options to the list.")
    else:
        selected_option = st.selectbox(':red[Select the Chain Reset Schedule to format]', options + ['Add new option...'], key="existing_option")

    if selected_option == 'Add new option...':
        st.write("You selected: Add new option...")
        
        with st.form(key='add_option_form', clear_on_submit=True):
            new_option = st.text_input('Enter the new option', value=st.session_state.new_option)
            submit_button = st.form_submit_button('Add Option')
            
            if submit_button and new_option:
                options.append(new_option)
                update_options(options)
                st.success('Option added successfully!')
                st.session_state.option_added = True

        st.session_state.new_option = ""
        
    else:
        uploaded_file = st.file_uploader(":red[Upload reset schedule spreadsheet to be formatted]", type=["xlsx"])
        formatted_workbook = None  # Initialize the variable

        if st.button("Reformat Spreadsheet"):
            with st.spinner('Starting Format of Spreadsheet ...'):
                if uploaded_file is None:
                    st.warning("Please upload a spreadsheet first.")
                else:
                    # Load the workbook and get the first sheet
                    workbook = openpyxl.load_workbook(uploaded_file)
                    sheet = workbook.active  # Assuming validation is for the first sheet
                    
                    # Extract column A values and check against the selected option
                    column_a_values = [str(cell.value).strip() for cell in sheet['A'] if cell.value is not None]
                    if selected_option not in column_a_values:
                        st.error(f"The selected option '{selected_option}' does not match any value in column A of the uploaded sheet.")
                        st.info("Please ensure the selected option matches the data in column A and re-upload the file.")
                        st.stop()  # Stop further execution if validation fails

                    # Proceed with formatting if validation passes
                    formatted_workbook = format_RESET_schedule(workbook)  # Use the original workbook    
                    new_filename = f"formatted_{selected_option}_spreadsheet.xlsx"

                    if formatted_workbook is not None:
                        for sheet_name in formatted_workbook.sheetnames:
                            sheet = formatted_workbook[sheet_name]
                            if sheet.auto_filter:
                                sheet.auto_filter.ref = None
                       
                        stream = BytesIO()
                        formatted_workbook.save(stream)
                        stream.seek(0)
                
                        st.download_button(
                            label="Download formatted spreadsheet",
                            data=stream.read(),
                            file_name=new_filename,
                            mime='application/vnd.ms-excel'
                        )
                    else:
                        st.warning("No file has been prepared for download.")


with file_container:
    st.markdown("<hr>", unsafe_allow_html=True)
    st.subheader(":blue[Reset Schedule File to Upload to Snowflake Utility]")

    if "selected_option" not in st.session_state:
        st.session_state.selected_option = None
    
    if not options:
        st.warning("No options available. Please add options to the list.")
    else:
        selected_option = st.selectbox(':red[Select the Chain Reset Schedule to load to Snowflake]', options + ['Add new option...'], key="select_snowflake_option")

    if selected_option == 'Add new option...':
        st.write("You selected: Add new option...")
        
        with st.form(key='add_option_form', clear_on_submit=True):
            new_option = st.text_input('Enter the new option', value=st.session_state.new_option)
            submit_button = st.form_submit_button('Add Option')
            
            if submit_button and new_option:
                options.append(new_option)
                update_options(options)
                st.success('Option added successfully!')
                st.session_state.option_added = True

        st.session_state.new_option = ""
        
    else:
        st.session_state.selected_option = selected_option

    uploaded_files = st.file_uploader(":red[Browse or select formatted reset schedule excel sheet To Upload to Snowflake]", type=["xlsx"], accept_multiple_files=True)

    for uploaded_file in uploaded_files:
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        workbook_name = uploaded_file.name
        
        for sheet_name in sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            df = df.replace('NAN', np.nan)
  
    if uploaded_files:
        button_key = f"import_button_{workbook_name}_{sheet_name}"
        if st.button("Import into Snowflake", key=button_key):
            with st.spinner(f'Uploading {selected_option} data to Snowflake ...'):
                upload_reset_data(df, selected_option)  
    else:
        st.warning("Please upload a file before attempting to import into Snowflake.")
