import streamlit as st
import pandas as pd
import re
from db_utils.snowflake_connection import get_snowflake_toml



# Utility to fetch or create supplier


def update_analytics_master(conn):
    cursor = conn.cursor()

    # First, clear existing analytics_master (optional but recommended)
    cursor.execute("TRUNCATE TABLE analytics_master")

    merge_query = """
        INSERT INTO analytics_master (SUPPLIER_ID, YEAR, MONTH, ON_OFF_PREMISE, CHAIN_INDEPENDENT, DOLLAR_VOLUME, BUYER_COUNT, PLACEMENT_COUNT)
        SELECT 
            COALESCE(d.SUPPLIER_ID, b.SUPPLIER_ID, p.SUPPLIER_ID) as SUPPLIER_ID,
            COALESCE(d.YEAR, b.YEAR, p.YEAR) as YEAR,
            COALESCE(d.MONTH, b.MONTH, p.MONTH) as MONTH,
            COALESCE(d.ON_OFF_PREMISE, b.ON_OFF_PREMISE, p.ON_OFF_PREMISE) as ON_OFF_PREMISE,
            COALESCE(d.CHAIN_INDEPENDENT, b.CHAIN_INDEPENDENT, p.CHAIN_INDEPENDENT) as CHAIN_INDEPENDENT,
            d.DOLLAR_VOLUME,
            b.BUYER_COUNT,
            p.PLACEMENT_COUNT
        FROM DOLLAR_VOLUME d
        FULL OUTER JOIN BUYER_COUNT b 
          ON d.SUPPLIER_ID = b.SUPPLIER_ID 
         AND d.YEAR = b.YEAR 
         AND d.MONTH = b.MONTH 
         AND d.ON_OFF_PREMISE = b.ON_OFF_PREMISE 
         AND d.CHAIN_INDEPENDENT = b.CHAIN_INDEPENDENT
        FULL OUTER JOIN PLACEMENT_COUNT p 
          ON COALESCE(d.SUPPLIER_ID, b.SUPPLIER_ID) = p.SUPPLIER_ID 
         AND COALESCE(d.YEAR, b.YEAR) = p.YEAR 
         AND COALESCE(d.MONTH, b.MONTH) = p.MONTH 
         AND COALESCE(d.ON_OFF_PREMISE, b.ON_OFF_PREMISE) = p.ON_OFF_PREMISE 
         AND COALESCE(d.CHAIN_INDEPENDENT, b.CHAIN_INDEPENDENT) = p.CHAIN_INDEPENDENT;
    """

    try:
        cursor.execute(merge_query)
        conn.commit()
        st.success("Analytics master table updated successfully!")
    except Exception as e:
        conn.rollback()
        logging.error(f"Failed to update analytics master: {str(e)}")
        st.error(f"Failed to update analytics master: {str(e)}")
    finally:
        cursor.close()


def get_or_create_supplier(conn, supplier_name):
    cursor = conn.cursor()
    cursor.execute("SELECT SUPPLIER_ID FROM SUPPLIER_MASTER WHERE SUPPLIER_NAME = %s", (supplier_name,))
    result = cursor.fetchone()
    if result:
        return result[0]

    cursor.execute("INSERT INTO SUPPLIER_MASTER (SUPPLIER_NAME) VALUES (%s)", (supplier_name,))
    cursor.execute("SELECT SUPPLIER_ID FROM SUPPLIER_MASTER WHERE SUPPLIER_NAME = %s", (supplier_name,))
    new_id = cursor.fetchone()[0]
    conn.commit()
    return new_id


# Main function to parse and load Excel data
import streamlit as st

def load_data(file, table_type, conn):
    df = pd.read_excel(file)
    df = df.where(pd.notnull(df), None)

    cursor = conn.cursor()
    month_cols = [col for col in df.columns if re.match(r'.*\d{4} \d{2}$', col)]

    insert_rows = []
    total_rows = len(df) * len(month_cols)
    progress_bar = st.progress(0)
    current_row = 0

    with st.spinner('Uploading data to Snowflake...'):
        for idx, row in df.iterrows():
            supplier_name = row['Supplier']
            supplier_id = get_or_create_supplier(conn, supplier_name)
            on_off_premise = row['On-Off Premise']
            chain_independent = row['Chain / Independent']

            for col in month_cols:
                value = row[col]
                match = re.search(r'(\d{4}) (\d{2})$', col)
                year, month = int(match.group(1)), int(match.group(2))

                if None in [supplier_id, year, month, on_off_premise, chain_independent, value]:
                    current_row += 1
                    progress_bar.progress(current_row / total_rows)
                    continue

                insert_rows.append((supplier_id, year, month, on_off_premise, chain_independent, value))
                current_row += 1
                progress_bar.progress(current_row / total_rows)

        if table_type == 'DOLLAR_VOLUME':
            query = """
                INSERT INTO DOLLAR_VOLUME (SUPPLIER_ID, YEAR, MONTH, ON_OFF_PREMISE, CHAIN_INDEPENDENT, DOLLAR_VOLUME)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
        elif table_type == 'BUYER_COUNT':
            query = """
                INSERT INTO BUYER_COUNT (SUPPLIER_ID, YEAR, MONTH, ON_OFF_PREMISE, CHAIN_INDEPENDENT, BUYER_COUNT)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
        elif table_type == 'PLACEMENT_COUNT':
            query = """
                INSERT INTO PLACEMENT_COUNT (SUPPLIER_ID, YEAR, MONTH, ON_OFF_PREMISE, CHAIN_INDEPENDENT, PLACEMENT_COUNT)
                VALUES (%s, %s, %s, %s, %s, %s)
            """

        cursor.executemany(query, insert_rows)
        conn.commit()

        # Call update function after successful commit
        update_analytics_master(conn)

    progress_bar.empty()
   # st.success("Data uploaded successfully!")






# Streamlit page integration
st.title("Historical Data Uploader")

toml_info = st.session_state.get('toml_info')
if not toml_info:
    st.error("Please log in first.")
else:
    file_type = st.selectbox("Select file type", ["DOLLAR_VOLUME", "BUYER_COUNT", "PLACEMENT_COUNT"])
    uploaded_file = st.file_uploader("Upload Excel file", type=['xlsx'])

    if st.button("Load Data"):
        if uploaded_file is not None:
            conn = get_snowflake_toml(toml_info)
            if conn:
                try:
                    load_data(uploaded_file, file_type, conn)
                    st.success(f"Successfully loaded data into {file_type} table!")
                except Exception as e:
                    st.error(f"Failed to load data: {str(e)}")
                finally:
                    conn.close()
            else:
                st.error("Failed to connect to Snowflake.")
        else:
            st.error("Please upload a file.")
