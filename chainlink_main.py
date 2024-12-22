from imaplib import _Authenticator
import streamlit as st

# # Set up the page
st.set_page_config(layout="wide", initial_sidebar_state="auto")

import bcrypt
from datetime import timedelta
import streamlit_authenticator as stauth
from db_utils.snowflake_utils import fetch_and_store_toml_info, fetch_user_credentials, validate_user_email
from PIL import Image
from dashboard.dashboard_main import display_dashboard
from streamlit_authenticator.utilities import (CredentialsError, ForgotError, Hasher, LoginError, RegisterError, ResetError, UpdateError)
from email_utils.email_util import send_reset_link
from utils.util import reset_password, generate_token
from auth.reset_password_page import reset_password_page




reduce_header_height_style = """
    <style>
        div.block-container {padding-top:1rem;}
    </style>
"""
st.markdown(reduce_header_height_style, unsafe_allow_html=True)


# Secret Key for JWT (stored securely in Streamlit secrets)
COOKIE_KEY = st.secrets["cookie_key"]["cookie_secret_key"]

# Utility function to add logo
def add_logo(logo_path, width, height):
    logo = Image.open(logo_path)
    modified_logo = logo.resize((width, height))
    return modified_logo

# Utility function to apply custom sidebar styles
def apply_custom_style():
    st.sidebar.markdown("--------")

# Step 1: Forgot Password Form
def forgot_password():
    st.title("Forgot Password")  # Title for the Forgot Password Page
    email = st.text_input("Enter your email", st.session_state.get('email', ''))
    
    # Add a button to trigger the form submission
    if st.button("Request Password Reset"):
        st.session_state['forgot_password_submitted'] = True  # Set session state to persist the form
        st.session_state['email'] = email  # Store email in session
        
        # Check if the user entered a valid email
        if email:
            # Validate the email exists in the database
            if validate_user_email(email):
                send_password_reset(email)  # Send reset link
            else:
                st.error("The email does not exist in our records.")
        else:
            st.warning("Please enter a valid email.")

# Step 2: Handle Password Reset Request
def send_password_reset(email):
    token = generate_token(email)
    st.write(f"Generated token: {token}")  # Debugging log

    if token:
        send_reset_link(email, token)  # Sends reset email with the token
        st.success("If the email exists, you will receive a password reset link.")
    else:
        st.warning("Invalid email.")

# Step 3: Update the Password Form
def reset_password_form():
    query_params = st.query_params
    reset_token = query_params.get("token", None)  # Get token from URL

    if reset_token is None:
        st.error("This page can only be accessed via the reset link.")
        return

    new_password = st.text_input("Enter your new password", type="password")
    confirm_password = st.text_input("Confirm your new password", type="password")
    
    if st.button("Reset Password"):
        if new_password and confirm_password:
            if new_password == confirm_password:
                success = reset_password(None, reset_token, new_password, confirm_password)
                if success:
                    st.success("Your password has been updated successfully.")
                    st.rerun()  # Redirect to login after success
                else:
                    st.error("Password reset failed. Invalid or expired token.")
            else:
                st.error("Passwords do not match.")
        else:
            st.warning("Please enter and confirm your new password.")

# Main function to handle authentication and page rendering
def main():
    # Check if the user is visiting with a password reset token in the URL
    query_params = st.query_params
    reset_token = query_params.get('token', None)  # Extract token if it exists
    
    # If there's a reset token, show the reset password page
    if reset_token:
        reset_password_page()  # Render the reset password page
        return  # Stop further execution (skip the login flow)

    # Check if the user has requested password reset
    if st.session_state.get('forgot_password_submitted', False):
        forgot_password()  # Render forgot password form
        return

    # Fetch credentials from Snowflake
    credentials = fetch_user_credentials()

    # Initialize the authenticator
    authenticator = stauth.Authenticate(
        credentials=credentials,
        cookie_name="chainlink_token",
        cookie_key=COOKIE_KEY,
        cookie_expiry_days=0.014  # 20 minutes as a fraction of a day
    )

    # Otherwise, show the login form
    try:
        name, authentication_status, username = authenticator.login()
    except stauth.LoginError as e:
        st.error(e)

    if authentication_status:
        st.session_state['authentication_status'] = True
        st.session_state['username'] = username
        st.session_state['roles'] = credentials['usernames'][username].get('roles', [])
        st.session_state['tenant_id'] = credentials['usernames'][username].get('tenant_id')

        # Fetch and store TOML info for the tenant
        if not fetch_and_store_toml_info(st.session_state['tenant_id']):
            st.error("Failed to retrieve or validate TOML configuration.")
            return

        # Render authenticated menu and navigation
        render_authenticated_menu(authenticator)

    elif authentication_status == False:
        st.error('Username/password is incorrect')
        if st.button("Forgot Password?"):
            st.session_state['forgot_password_submitted'] = True
            st.rerun()  # Redirect to Forgot Password Page

    elif authentication_status is None:
        st.warning('Please enter your username and password')
        if st.button("Forgot Password?"):
            st.session_state['forgot_password_submitted'] = True
            st.rerun()  # Redirect to Forgot Password Page


# Function to render authenticated menu and dynamic navigation
def render_authenticated_menu(authenticator):
    # Check if TOML info is available
    if 'toml_info' not in st.session_state:
        st.error("No TOML info available.")
        return

    # Display welcome message and tenant info in the sidebar
    username = st.session_state.get('username', 'User')
    toml_info = st.session_state['toml_info']
    tenant_name = toml_info.get('tenant_name', 'No Tenant Name')
    logo_path = toml_info.get('logo_path')

    st.sidebar.success(f"Welcome, {username}!")
    st.sidebar.header(tenant_name)

    if logo_path:
        my_logo = add_logo(logo_path=logo_path, width=200, height=100)
        st.sidebar.image(my_logo)

    # Apply custom styling
    apply_custom_style()

    # Dynamically create pages based on user roles
    roles = [role.lower() for role in st.session_state['roles']]
    page_dict = {}

    if "user" in roles or "admin" in roles:
        page_dict["Home"] = [
            st.Page(lambda: display_dashboard(authenticator), title="Dashboard")
        ]

    if "admin" in roles:
        page_dict["Admin Dashboard"] = [
            st.Page("admin/admin_page.py", title="Administration")
        ]

    if "user" in roles or "admin" in roles:
        page_dict["Load Data"] = [
            st.Page("dataloader/load_company_data.py", title="Load Company Data"),
            st.Page("dataloader/reset_data_update.py", title="Load Reset Schedules"),
            st.Page("dataloader/distro_grid_processing.py", title="Load Distro Grid Data"),
            st.Page("dataloader/load_Misc_distro_grid_data.py", title="Load Misc Distro Grid Data")
        ]

    if "user" in roles or "admin" in roles:
        page_dict["Reports"] = [
            st.Page("reports/reports.py", title="Reports")
        ]

    # Set up navigation and run the selected page
    if page_dict:
        account_pages = [st.Page(lambda: st.write("Logging Out..."), title="Logout", icon=":material/logout:")]
        pg = st.navigation({"Home": account_pages, **page_dict})
        pg.run()

    # Use the logout button with a callback to clear the session
    #authenticator.logout("Logout", "sidebar", key="logout_key", callback=logout_callback)
    authenticator.logout("Logout", "sidebar", key="logout_key")
   
     


def logout_callback(*args, **kwargs):
    # Clear session state, including sidebar
    st.session_state.clear()
    # Set page configuration again to reset sidebar state
    st.set_page_config(layout="wide", initial_sidebar_state="auto")
    # Explicitly clear sidebar
    st.sidebar.empty()
    # Remove the cookie
    st.set_cookie("chainlink_token", "", expires=timedelta(days=-1))
    # Rerun to return to the login page
    st.rerun()

       
       

if __name__ == "__main__":
    main()
