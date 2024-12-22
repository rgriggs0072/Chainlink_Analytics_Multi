
# admin/admin_page.py
import streamlit as st
import time
import re
from db_utils.snowflake_utils import get_snowflake_connection
from utils.util import generate_token, create_user
from email_utils.email_util import register_user



def fetch_roles():
    # This function will only fetch roles if they are not already present in the session state.
    if 'available_roles' not in st.session_state:
        conn = get_snowflake_connection()  # Adjust this function based on your actual database connection utility
        cursor = conn.cursor()
        cursor.execute("SELECT role_name FROM GET_USER_ROLES;")  # Assuming 'role_name' is the column with role names
        roles = cursor.fetchall()
        cursor.close()
        conn.close()
        st.session_state['available_roles'] = [role[0] for role in roles]  # Cache the roles in session state
    return st.session_state['available_roles']  # Return the cached roles

def register_new_user_form():
    st.write("Rendering new user registration form...")  # Debug statement
    user_created_successfully = False  # Initialize the variable

    with st.form("register_user"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        fname = st.text_input("First Name")
        lname = st.text_input("Last Name")
        initial_status = st.selectbox("Initial Status", ["Pending", "Active"])

        # Fetch roles and add them to a selectbox
        roles = fetch_roles()  # This call will now only access the database if roles are not cached in session state
        if roles:
            selected_role = st.selectbox("Role", roles)
        else:
            st.error("Could not fetch roles. Please try again later.")
            selected_role = None

        submit_button = st.form_submit_button("Register")

        if submit_button and selected_role:
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                st.error("Please enter a valid email address.")
            else:
                try:
                    user_created_successfully = create_user(username, email, fname, lname, selected_role, initial_status)
                except Exception as e:
                    st.error(f"An error occurred while creating the user: {e}")

    if user_created_successfully:
        try:
            token = generate_token(email)  # Generate a unique token for the user
            register_user(email, token, username)  # Send an email with the registration link using the generated token
            st.success("Registration initiated successfully. Please have the user check their email to complete the registration.")
        except Exception as e:
            st.error(f"An error occurred while sending the registration email: {e}")



def admin_dashboard():
    #st.write(f"User roles: {st.session_state.get('roles', [])}") 
    st.title("Admin Dashboard")
    #st.write("Am I the big dog? ")

    if is_user_admin():
        #st.write("Welcome! You have access to the admin dashboard.")
        with st.expander("Register New User"):
            register_new_user_form()
    else:
        st.error("You must be an admin to access this page.")


def is_user_admin():
    user_roles =st.session_state.get('roles', [])
   # st.write(f"User roles: {user_roles}")  # Debugging log to check roles in session state
    # Convert all roles to lowercase and check if 'admin' is present
    return 'admin' in [role.lower() for role in user_roles]



# Ensure this code is only executed when the page is accessed directly
admin_dashboard()
 
