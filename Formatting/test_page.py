import streamlit as st

# Test session state
if 'test_state' not in st.session_state:
    st.session_state['test_state'] = "Initial Value"

st.write("Current session state value:", st.session_state['test_state'])

# Button to modify session state
if st.button("Change State"):
    st.session_state['test_state'] = "Updated Value"
    st.write("Session state updated!")
    st.write("what is the new session state? ",  st.session_state['test_state'])
