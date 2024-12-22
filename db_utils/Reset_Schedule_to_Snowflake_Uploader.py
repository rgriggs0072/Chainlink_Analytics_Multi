import ipaddress
import streamlit as st
import pandas as pd
import snowflake.connector
from snowflake.connector import ProgrammingError
import numpy as np
import getpass
import socket
from datetime import datetime
from db_utils.snowflake_connection import get_snowflake_connection, get_snowflake_toml, validate_toml_info, fetch_and_store_toml_info

def current_timestamp():
    return datetime.now()




# --------------------------------------------------------------------------------------------------------------------

def create_log_entry(user_id, activity_type, description, success, local_ip, selected_option):
    try:
        # Log the SQL activity
        insert_log_entry(user_id, activity_type, description, success, local_ip, selected_option)
    except Exception as log_error:
        st.exception(log_error)
        st.error(f"An error occurred while creating a log entry: {str(log_error)}")


# ====================================================================================================================
# The follwoing function is called to insert information into the log for latter trouble shooting
# ====================================================================================================================

def insert_log_entry(user_id, activity_type, description, success, ip_address, selected_option):
    try:
        cursor = conn.cursor()
        # Replace 'LOG' with the actual name of your log table
        insert_query = """
        INSERT INTO LOG (TIMESTAMP, USERID, ACTIVITYTYPE, DESCRIPTION, SUCCESS, IPADDRESS, USERAGENT)
        VALUES (CURRENT_TIMESTAMP(), %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (user_id, "SQL Activity", description, True, ip_address, selected_option))

        cursor.close()
    except Exception as e:
        # Handle any exceptions that might occur while logging
        print(f"Error occurred while inserting log entry: {str(e)}")


# ====================================================================================================================
# END function is called to insert information into the log for later trouble shooting
# ====================================================================================================================

# --------------------------------------------------------------------------------------------------------------------

# ====================================================================================================================
# Function to get the users IP address for later inserting into the log table for trouble shooting
# ====================================================================================================================
def get_local_ip():
    try:
        # Get the local host name
        host_name = socket.gethostname()

        # Get the IP address associated with the host name
        ip_address = socket.gethostbyname(host_name)

        return ip_address
    except Exception as e:
        print(f"An error occurred while getting the IP address: {e}")
        return None


# ====================================================================================================================
# END OF Function to get the users IP address for later inserting into the log table for trouble shooting
# ====================================================================================================================

# --------------------------------------------------------------------------------------------------------------------

# ====================================================================================================================
# Function to upload Reset Schedule Data into Snowflake for all stores and chains
# ====================================================================================================================



def upload_reset_data(df, selected_chain):
    # Retrieve TOML information
    toml_info = st.session_state.get('toml_info')
    if not toml_info:
        st.error("TOML information is not available. Please check the tenant ID and try again.")
        return

    # Create a connection to Snowflake
    conn_toml = get_snowflake_toml(toml_info)

    # Check for empty required columns
    if df['CHAIN_NAME'].isnull().any():
        st.warning("CHAIN_NAME field cannot be empty. Please provide a value and try again.")
        return
    elif df['STORE_NAME'].isnull().any():
        st.warning("STORE_NAME field cannot be empty. Please provide a value and try again.")
        return

    # Check if CHAIN_NAME matches the selected chain
    selected_chain = selected_chain.upper()
    chain_name_matches = df['CHAIN_NAME'].str.upper().eq(selected_chain)
    num_mismatches = len(chain_name_matches) - chain_name_matches.sum()

    if num_mismatches == 0:
        try:
            # Add LAST_UPLOAD_DATE with the current timestamp
            df['LAST_UPLOAD_DATE'] = pd.Timestamp.now()

            # Standardize date and time formats
            df['RESET_DATE'] = pd.to_datetime(df['RESET_DATE'], errors='coerce').dt.strftime('%Y-%m-%d')
            df['TIME'] = pd.to_datetime(df['TIME'], errors='coerce').dt.strftime('%H:%M:%S')

            # Replace missing values with None for compatibility
            df = df.replace({np.nan: None, '': None})

            # Ensure data types match Snowflake schema
            df = df.astype({
                'CHAIN_NAME': str,
                'STORE_NUMBER': 'Int64',
                'STORE_NAME': str,
                'PHONE_NUMBER': str,
                'CITY': str,
                'ADDRESS': str,
                'STATE': str,
                'COUNTY': str,
                'TEAM_LEAD': str,
                'RESET_DATE': str,
                'TIME': str,
                'STATUS': str,
                'NOTES': str,
                'LAST_UPLOAD_DATE': str
            })

            # Define the expected columns
            expected_columns = [
                'CHAIN_NAME', 'STORE_NUMBER', 'STORE_NAME', 'PHONE_NUMBER',
                'CITY', 'ADDRESS', 'STATE', 'COUNTY', 'TEAM_LEAD',
                'RESET_DATE', 'TIME', 'STATUS', 'NOTES', 'LAST_UPLOAD_DATE'
            ]
           
            # Generate placeholders for the insert
            placeholders = ', '.join(['%s'] * len(expected_columns))
            insert_query = f"""
            INSERT INTO RESET_SCHEDULE ({', '.join(expected_columns)})
            VALUES ({placeholders})
            """

            # Step 1: Remove existing data for the selected chain
            delete_query = f"""
            DELETE FROM RESET_SCHEDULE
            WHERE CHAIN_NAME = '{selected_chain}'
            """

            # Reset the index for safety
            df.reset_index(drop=True, inplace=True)

            # Execute the delete and insert queries
            with conn_toml.cursor() as cursor:
                st.info(f"Removing existing data for chain: {selected_chain}")
                cursor.execute(delete_query)  # Remove existing data
                
                st.info("Inserting new data...")
                cursor.executemany(insert_query, df.values.tolist())  # Insert new data
                
                conn_toml.commit()
                # cursor.execute("select current_database(), current_schema()")
                # database_info = cursor.fetchone()
                # st.write(f"connected to database: {database_info[0]}, schema: {database_info[1]}")

            st.success(f"Data for '{selected_chain}' has been successfully replaced in Snowflake.")

        except ProgrammingError as pe:
            st.error(f"An error occurred while writing to Snowflake: {str(pe)}")
        finally:
            # Ensure the connection is closed
            if conn_toml:
                conn_toml.close()
    else:
        st.warning(
            f"The selected chain ({selected_chain}) does not match {num_mismatches} name(s) in the CHAIN_NAME column. "
            "Please select the correct chain and try again."
             
        )


# =============================================================================================================================
# End Function to load data into Snowflake reset_schedule table for FoodMaxx
# ============================================================================================================================ 




