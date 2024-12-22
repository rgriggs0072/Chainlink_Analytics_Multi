from dashboard.dashboard_main import display_dashboard
import streamlit as st
from PIL import Image

def apply_custom_style():
    st.sidebar.markdown("--------")

def get_logo_url():
    return "https://www.chainlinkanalytics.com/"

def get_logo_path():
    return "./images/ChainlinkAnalytics/Chainlink_Analytics_icon_text_logo__web_blues.png"

# Add_logo function
def add_logo(logo_path, width, height):
    logo = Image.open(logo_path)
    modified_logo = logo.resize((width, height))
    return modified_logo

# Define the authenticated menu with navigation using st.Page and st.navigation
def authenticated_menu(authenticator):
   
   # print("am I authenticated and do I have the TOML in formation? ", st.session_state['toml_info'])
    # Check if TOML info is available
    if 'toml_info' not in st.session_state:
        return  # Exit if no TOML info is available

    # Display the success message at the top of the sidebar
    username = st.session_state.get('username', 'User')
    st.sidebar.success(f"Welcome, {username}!")

    # Display the user information, tenant, and logo
    toml_info = st.session_state['toml_info']
    tenant_name = toml_info.get('tenant_name', 'No Tenant Name')
    user_email = st.session_state.get('email', 'No Email')

    # Display tenant name in the sidebar
    st.sidebar.header(tenant_name)

    # Display logo if available
    logo_path = toml_info.get('logo_path')
    if logo_path:
        my_logo = add_logo(logo_path=logo_path, width=200, height=100)
        st.sidebar.image(my_logo)

    # Apply custom styling
    apply_custom_style()

    # Define pages for navigation based on user roles
    roles = [role.lower() for role in st.session_state['roles']]  # Normalize roles to lowercase
    pages = []

    if "user" in roles:
        pages = {"Dashboards": [
            st.Page("dashboard/dashboard_main.py", title="Dashboard"),  # Correct file path
            st.Page("dashboard/dashboard_test.py", title="Dashboard_Test"),  # Correct file path
            # Add other user pages here
        ]
    }
    if "admin" in roles:
        pages ={"Dashboards": [
            st.Page("dashboard/dashboard_main.py", title="Dashboard"),  # Correct file path
            st.Page("dashboard/dashboard_test.py", title="Dashboard_Test"),  # Correct file path
            # Add other admin pages here
        ]
        }
    # Set up navigation and run the selected page
    if pages:  # Ensure there are valid pages to pass
        pg = st.navigation(pages)
        pg.run()

    # Add logout button at the end of the menu
    #authenticator.logout("Logout", "sidebar")

