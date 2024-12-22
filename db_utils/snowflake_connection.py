import streamlit as st
import snowflake.connector
import logging
import pandas as pd
import os

def validate_toml_info(toml_info):
    required_keys = ["account", "snowflake_user", "password", "warehouse", "database", "schema"]
    missing_keys = [key for key in required_keys if key not in toml_info or not toml_info[key]]
    if missing_keys:
        logging.error(f"TOML configuration is incomplete or invalid. Missing: {missing_keys}")
        st.error(f"TOML configuration is incomplete or invalid. Check the configuration.")
        return False
    return True




def fetch_and_store_toml_info(tenant_id):
    try:
        conn = get_snowflake_connection()  # Fetch Snowflake connection
        cursor = conn.cursor()

        # Fetch TOML information based on the tenant_id
        query = """
        SELECT snowflake_user, password, account, warehouse, database, schema, logo_path, tenant_name
        FROM TOML
        WHERE TENANT_ID = %s
        """
        cursor.execute(query, (tenant_id,))
        toml_info = cursor.fetchone()
        cursor.close()
        conn.close()

        if toml_info:
            keys = ["snowflake_user", "password", "account", "warehouse", "database", "schema", "logo_path", "tenant_name"]
            toml_dict = dict(zip(keys, toml_info))
            print("Now what the hell toml info do you have big daddy? ", toml_info)
            
            # Store the TOML info in session state
            st.session_state['toml_info'] = toml_dict
            st.session_state['tenant_name'] = toml_dict['tenant_name']
            return True  # Indicate successful fetch and store
        else:
            logging.error(f"No TOML configuration found for tenant_id: {tenant_id}")
            return False  # Indicate failure in fetching TOML info
    except Exception as e:
        logging.error(f"Failed to fetch TOML info due to: {str(e)}")
        return False  # Handle the error appropriately



def get_snowflake_connection():
    
    try:
        # Load Snowflake credentials from the secrets.toml file
        snowflake_creds = st.secrets["chainlink"]

        # Create and return a Snowflake connection object
        conn = snowflake.connector.connect(
            account=snowflake_creds["account"],
            user=snowflake_creds["user"],
            password=snowflake_creds["password"],
            warehouse=snowflake_creds["warehouse"],
            database=snowflake_creds["database"],
            schema=snowflake_creds["schema"]
        )
        return conn
    except Exception as e:
        st.error("Failed to connect to Snowflake: " + str(e))
        return None
    

def get_snowflake_toml(toml_info):
    try:
        if not all(key in toml_info for key in ["account", "snowflake_user", "password", "warehouse", "database", "schema"]):
            logging.error("TOML configuration is incomplete or invalid.")
            st.error("TOML configuration is incomplete or invalid.")
            return None
        
        conn_toml = snowflake.connector.connect(
            account=toml_info['account'],
            user=toml_info['snowflake_user'],
            password=toml_info['password'],
            warehouse=toml_info['warehouse'],
            database=toml_info['database'],
            schema=toml_info['schema']
        )
        logging.info("Successfully connected to Snowflake.")
        return conn_toml
    except Exception as e:
        logging.error(f"Failed to connect to Snowflake with TOML info: {str(e)}")
        st.error(f"Failed to connect to Snowflake with TOML info: {str(e)}")
        return None


def get_tenant_id(username):
    conn = get_snowflake_connection()
    cursor = conn.cursor()

    query = """
    SELECT TENANT_ID FROM USERDATA WHERE UPPER(USERNAME) = %s
    """
    cursor.execute(query, (username.upper(),))
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    if result:
        return result[0]
    else:
        return None





# ============================================================================================================================================================
# 11/28/2023 Randy Griggs - Function will be called to handle the DB query and closing the the connection and return the results to the calling function
# ============================================================================================================================================================

def execute_query_and_close_connection(query, conn_toml):
    """
    Executes the given SQL query and closes the connection after completion.
    If the connection is closed prematurely, it tries to re-establish the connection.
    """
    cursor = None  # Initialize cursor to None to avoid unbound variable error
    try:
        # Ensure the connection is open
        if conn_toml.is_closed():
            # Try to re-establish the connection if it's closed
            conn_toml = get_snowflake_toml(st.session_state['toml_info'])
        
        # If the connection is still closed, raise an error
        if conn_toml is None or conn_toml.is_closed():
            st.error("Unable to establish a connection to Snowflake.")
            return None

        cursor = conn_toml.cursor()
        cursor.execute(query)
        result = cursor.fetchall()

        return result

    except Exception as e:
        st.error(f"Error executing query: {str(e)}")
        return None

    finally:
        # Close the cursor and connection after execution
        if cursor:
            cursor.close()
        if conn_toml and not conn_toml.is_closed():
            conn_toml.close()



# ============================================================================================================================================================
# END 11/28/2023 Randy Griggs - Function will be called to handle the DB query and closing the the connection
# ============================================================================================================================================================
    

# -------------------------------------------------------------------------------------------------------------------------------------------

# ===========================================================================================================================================
# Block for Function that will connect to DB and pull data to display the the bar chart from view - Execution Summary  - Data in row 1 column 2
# ===========================================================================================================================================

def fetch_chain_schematic_data(toml_info):
    try:
        conn_toml = get_snowflake_toml(toml_info)
        if conn_toml is None:
            st.error("Failed to establish a connection.")
            return pd.DataFrame()  # Return an empty DataFrame if connection fails

        query = "SELECT CHAIN_NAME, SUM(\"In_Schematic\") AS total_in_schematic, SUM(\"PURCHASED_YES_NO\") AS purchased, SUM(\"PURCHASED_YES_NO\") / COUNT(*) AS purchased_percentage FROM gap_report GROUP BY CHAIN_NAME;"
        result = execute_query_and_close_connection(query, conn_toml)

        if not result:
            st.error("No data fetched.")
            return pd.DataFrame()  # Return an empty DataFrame if no data

        df = pd.DataFrame(result, columns=["CHAIN_NAME", "TOTAL_IN_SCHEMATIC", "PURCHASED", "PURCHASED_PERCENTAGE"])
        df['PURCHASED_PERCENTAGE'] = (df['PURCHASED_PERCENTAGE'].astype(float) * 100).round(2).astype(str) + '%'
        return df
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        return pd.DataFrame()  # Return an empty DataFrame in case of error
    finally:
        if conn_toml:
            conn_toml.close()  # Ensure connection is always closed


# ===========================================================================================================================================
# END Block for Function that will connect to DB and pull data to display the the bar chart from view - Execution Summary  - Data in column 3




def fetch_supplier_names():
    
    
    
    # Retrieve toml_info from session state
    toml_info = st.session_state.get('toml_info')
    if not toml_info:
        st.error("TOML information is not available. Please check the tenant ID and try again.")
        return

    query = "SELECT DISTINCT supplier FROM supplier_county order by supplier"  # Adjust the query as needed
    # Create a connection to Snowflake
    conn_toml = get_snowflake_toml(toml_info)
    
    # Create a cursor object
    cursor = conn_toml.cursor()

    cursor.execute(query)
    result = cursor.fetchall()
    
    # Safely iterate over the result
    supplier_names = [row[0] for row in result]
    return supplier_names

#===================================================================================================
# Function to create the gap report from data pulled from snowflake and button to download gap report
#=====================================================================================================




def create_gap_report(conn, salesperson, store, supplier):
    """
    Retrieves data from a Snowflake view and creates a button to download the data as a CSV report.
    """
   
    # Retrieve toml_info from session state
    toml_info = st.session_state.get('toml_info')
    if not toml_info:
        st.error("TOML information is not available. Please check the tenant ID and try again.")
        return
 
        # Create a connection to Snowflake
        conn_toml = snowflake_connection.get_snowflake_toml(toml_info)

        # Create a cursor object
        cursor = conn_toml.cursor()
    
        # Execute the stored procedure without filters
        #cursor = conn.cursor()
        cursor.execute("CALL PROCESS_GAP_REPORT()")
        cursor.close()

    # Execute SQL query and retrieve data from the Gap_Report view with filters
    if salesperson != "All":
        query = f"SELECT * FROM Gap_Report WHERE SALESPERSON = '{salesperson}'"
        if store != "All":
            query += f" AND STORE_NAME = '{store}'"
            if supplier != "All":
                query += f" AND SUPPLIER = '{supplier}'"
    elif store != "All":
        query = f"SELECT * FROM Gap_Report WHERE STORE_NAME = '{store}'"
        if supplier != "All":
            query += f" AND SUPPLIER = '{supplier}'"
    else:
        if supplier != "All":
            query = f"SELECT * FROM Gap_Report WHERE SUPPLIER = '{supplier}'"
        else:
            query = "SELECT * FROM Gap_Report"
    df = pd.read_sql(query, conn)

    # Get the user's download folder
    download_folder = os.path.expanduser(r"~\Downloads")

    # Write the updated dataframe to a temporary file
    temp_file_name = 'temp.xlsx'

    # Create the full path to the temporary file
    #temp_file_path = os.path.join(download_folder, temp_file_name)
    temp_file_path = "temp.xlsx"
    #df.to_excel(temp_file_path, index=False)
    #st.write(df)

    df.to_excel(temp_file_path, index=False)  # Save the DataFrame to a temporary file


    # # Create the full path to the temporary file
    # temp_file_name = 'temp.xlsx'
    # temp_file_path = os.path.join(download_folder, temp_file_name)

    return temp_file_path  # Return the file path



def fetch_supplier_schematic_summary_data(selected_suppliers):
    toml_info = st.session_state.get('toml_info')
    supplier_conditions = ", ".join([f"'{supplier}'" for supplier in selected_suppliers])

    query = f"""
    SELECT 
    PRODUCT_NAME,
    "dg_upc" AS UPC,
    SUM("In_Schematic") AS Total_In_Schematic,
    SUM(PURCHASED_YES_NO) AS Total_Purchased,
    (SUM(PURCHASED_YES_NO) / SUM("In_Schematic")) * 100 AS Purchased_Percentage
    FROM
        GAP_REPORT_TMP2
    WHERE
        "sc_STATUS" = 'Yes' AND SUPPLIER IN ({supplier_conditions})
    GROUP BY
        SUPPLIER, PRODUCT_NAME, "dg_upc"
    ORDER BY Purchased_Percentage ASC;
    """

    # Create a connection using get_snowflake_toml which should return a connection object
    conn_toml = get_snowflake_toml(toml_info)

    if conn_toml:
        # Execute the query and get the result using the independent function
        result = execute_query_and_close_connection(query, conn_toml)

        if result:
            df = pd.DataFrame(result, columns=["PRODUCT_NAME", "UPC", "Total_In_Schematic", "Total_Purchased", "Purchased_Percentage"])
            return df
        else:
            st.error("No data was returned from the query.")
            return pd.DataFrame()
    else:
        st.error("Failed to establish a connection.")
        return pd.DataFrame()