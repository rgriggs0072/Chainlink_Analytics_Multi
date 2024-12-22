from imaplib import _Authenticator
import streamlit as st
import streamlit_authenticator as stauth
from db_utils.snowflake_utils import get_snowflake_connection, fetch_user_credentials, fetch_and_store_toml_info
from dashboard.dashboard_main import display_dashboard
from streamlit_authenticator.utilities import (CredentialsError, ForgotError, Hasher, LoginError, RegisterError, ResetError, UpdateError)


# Secret Key for JWT (stored securely in Streamlit secrets)
COOKIE_KEY = st.secrets["cookie_key"]["cookie_secret_key"]

# Initialize session state keys if not already initialized
if 'authentication' not in st.session_state:
   
    
    st.session_state['authentication'] = False

if 'roles' not in st.session_state:
    st.session_state['roles'] = []  # Initialize roles as an empty list if not set

# Main login function
def main():
    # Fetch user credentials from the database
    credentials = fetch_user_credentials()

    # Initialize the authenticator
    authenticator = stauth.Authenticate(
        credentials=credentials,
        cookie_name="chainlink_token",
        cookie_key=COOKIE_KEY,
        cookie_expiry_days=0.014,  # 20 minutes as a fraction of a day
    )
   
    
    # Create the login widget
    try:
        name, authentication_status, username = authenticator.login()
    except LoginError as e:
        st.error(e)

    # If authentication is successful
    if authentication_status:
        st.session_state['authentication'] = True
        st.session_state['username'] = username

    
        # Fetch user roles and tenant ID from the credentials
        tenant_id = credentials['usernames'][username].get('tenant_id')
        st.session_state['tenant_id'] = tenant_id
        st.session_state['email'] = credentials['usernames'][username].get('email')
        st.session_state['roles'] = credentials['usernames'][username].get('roles', [])

        # Fetch and store TOML info for the tenant
        if not fetch_and_store_toml_info(tenant_id):
            st.error("Failed to retrieve or validate TOML configuration.")
            return

        # Display the dashboard after successful login
        display_dashboard(authenticator)

    elif authentication_status == False:
        st.error('Username/password is incorrect')

    elif authentication_status is None:
        st.warning('Please enter your username and password')


         

   
     





if __name__ == "__main__":
    main()
