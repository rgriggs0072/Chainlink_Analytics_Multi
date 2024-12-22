import streamlit as st
from utils.util import reset_password

def reset_password_page():
    # Get query parameters from the URL using st.query_params
    query_params = st.query_params
    
    # Debugging log to check query parameters
    st.write(f"Query Params: {query_params}")  # Debugging log for query parameters
    
    # Get the reset token from the query params
   # reset_token = query_params.get("token", [None])[0]  # Extract the first item from the list associated with 'token'
    reset_token = query_params.get("token", None)
    
    # Debugging log to verify correct token extraction
    st.write(f"Extracted Reset Token: {reset_token}")  # Debugging log
    
    if not reset_token:
        st.error("This page can only be accessed via the reset link.")
        return
    
    st.title("Reset Your Password")

    with st.form("reset_password_form"):
        username = st.text_input("User Name", placeholder="Enter your user name")
        new_password = st.text_input("New Password", type="password", placeholder="Enter a new password")
        confirm_password = st.text_input("Confirm New Password", type="password", placeholder="Confirm your new password")
        
        submit_button = st.form_submit_button("Reset Password")

        if submit_button:
            if username:
                if new_password == confirm_password:
                    success = reset_password(username, reset_token, new_password, confirm_password)
                    if success:
                        st.success("Your password has been reset successfully. Please log in with your new password.")
                    else:
                        st.error("Failed to reset the password. Please ensure your reset token is valid and try again.")
                else:
                    st.error("Passwords do not match. Please try again.")
            else:
                st.error("Please enter your username.")



if __name__ == "__main__":
    reset_password_page()

