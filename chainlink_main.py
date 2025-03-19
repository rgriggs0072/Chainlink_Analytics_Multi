# ----------- chainlink_main.py ---------------------
import streamlit as st
# Page Configuration
st.set_page_config(
    page_title="Chainlink Analytics",
    layout="wide", initial_sidebar_state="collapsed")

import bcrypt
from datetime import timedelta
import streamlit_authenticator as stauth
from db_utils.snowflake_utils import fetch_and_store_toml_info, fetch_user_credentials, validate_user_email
from PIL import Image
from dashboard.dashboard_main import display_dashboard
from email_utils.email_util import send_reset_link
from utils.util import reset_password, generate_token
from auth.reset_password_page import reset_password_page
#from dashboard.dashboard_ai import main as ai_dashboard  # Import AI Dashboard



reduce_white_space_style = """
    <style>
        div.block-container {
            padding-top: 0.5rem;  /* Adjust the padding to reduce white space */
        }
        h1 {
            margin-top: 0rem;  /* Adjust the margin for headings */
        }
        .stMarkdown {
            margin-top: -1rem; /* Adjust the margin for markdown text */
        }
    </style>
"""
st.markdown(reduce_white_space_style, unsafe_allow_html=True)

# Secret Key for JWT
COOKIE_KEY = st.secrets["cookie_key"]["cookie_secret_key"]

# Utility function to add logo
def add_logo(logo_path, width, height):
    logo = Image.open(logo_path)
    return logo.resize((width, height))

# Utility function to apply custom sidebar styles
def apply_custom_style():
    st.sidebar.markdown("--------")







# Forgot Password Form
def forgot_password():
    st.title("Forgot Password")
    email = st.text_input("Enter your email", st.session_state.get('email', ''))

    if st.button("Request Password Reset"):
        st.session_state['forgot_password_submitted'] = True
        st.session_state['email'] = email

        if email:
            if validate_user_email(email):
                send_password_reset(email)
            else:
                st.error("The email does not exist in our records.")
        else:
            st.warning("Please enter a valid email.")

# Send Password Reset Link
def send_password_reset(email):
    token = generate_token(email)

    if token:
        send_reset_link(email, token)
        st.success("If the email exists, you will receive a password reset link.")
    else:
        st.warning("Invalid email.")

# Reset Password Form
def reset_password_form():
    query_params = st.query_params
    reset_token = query_params.get("token", None)

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
                    st.rerun()
                else:
                    st.error("Password reset failed. Invalid or expired token.")
            else:
                st.error("Passwords do not match.")
        else:
            st.warning("Please enter and confirm your new password.")

# Render Authenticated Menu
def render_authenticated_menu(authenticator):
    # Add the logout button to the sidebar
    logout_clicked = authenticator.logout("Logout", "sidebar", key="logout_key")
    if logout_clicked:
        st.write("Logout button clicked")  # Debugging statement
        print("Logout button clicked")  # Console log for debugging
        st.session_state.clear()  # Clear session state on logout
        st.sidebar.empty()  # Clear the sidebar immediately
        st.session_state["logged_out"] = True  # Mark as logged out
        st.rerun()  # Trigger a rerun to reload the app and show only the login page

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
            st.Page("dataloader/load_Misc_distro_grid_data.py", title="Load Misc Distro Grid Data"),
            st.Page("dataloader/Historical_Data_Uploader.py", title="Historical Data Uploader")
        ]

    if "user" in roles or "admin" in roles:
        page_dict["Reports"] = [
            st.Page("reports/reports.py", title="Reports")
        ]
    # ✅ Add AI Insights under Reports or create a new section
    if "user" in roles or "admin" in roles:
        page_dict["AI Insights"] = [
            st.Page("dashboard/dashboard_ai.py", title="🧠 AI Dashboard"),
            st.Page("dashboard/ai_insights.py", title="🧠 AI Insights"),
            st.Page("pages/gap_review.py", title="✏️ Review & Send Gap Reports")
           
        ]

    # Set up navigation and run the selected page
    if page_dict:
        account_pages = [st.Page(lambda: st.write("Logging Out..."), title="Logout")]
        pg = st.navigation({"Home": account_pages, **page_dict})
        pg.run()

# Sequential Execution (No main function)
query_params = st.query_params
reset_token = query_params.get('token', None)

if reset_token:
    reset_password_page()
    st.stop()

if st.session_state.get('forgot_password_submitted', False):
    forgot_password()
    st.stop()

# Check for logout state
if st.session_state.get("logged_out", False):
    st.session_state.clear()  # Fully clear the session state
    st.sidebar.empty()  # Clear any remaining sidebar content
    st.warning("You have been logged out.")
    st.stop()

credentials = fetch_user_credentials()

authenticator = stauth.Authenticate(
    credentials=credentials,
    cookie_name="chainlink_token",
    cookie_key=COOKIE_KEY,
    cookie_expiry_days=0.014
)

try:
    name, authentication_status, username = authenticator.login()
    print(f"Login attempt: {authentication_status}")  # Debugging statement
    print(f"user name = ", username)
except stauth.LoginError as e:
    st.error(e)
    st.stop()

if authentication_status:
    print("User authenticated")  # Console log for debugging
    st.session_state['authentication_status'] = True
    st.session_state['username'] = username
    st.session_state['roles'] = credentials['usernames'][username].get('roles', [])
    st.session_state['tenant_id'] = credentials['usernames'][username].get('tenant_id')

    if not fetch_and_store_toml_info(st.session_state['tenant_id']):
        st.error("Failed to retrieve TOML configuration.")
        st.stop()

    render_authenticated_menu(authenticator)

elif authentication_status is False:
    st.error('Username/password is incorrect')
    if st.button("Forgot Password?"):
        st.session_state['forgot_password_submitted'] = True
        st.rerun()

elif authentication_status is None:
    st.warning('Please enter your username and password')
    if st.button("Forgot Password?"):
        st.session_state['forgot_password_submitted'] = True
        st.rerun()
