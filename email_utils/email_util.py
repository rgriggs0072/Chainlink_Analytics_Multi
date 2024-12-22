import streamlit as st
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText





def send_reset_link(email, token):
    mailjet_creds = st.secrets["mailjet"]
    sender_email = "randy@chainlinkanalytics.com"
    smtp_username = mailjet_creds["API_KEY"]
    smtp_password = mailjet_creds["SECRET_KEY"]
    smtp_server = "in-v3.mailjet.com"
    smtp_port = 587

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = email
    msg['Subject'] = "Password Reset Request"
    html = f"""
    <html>
      <body>
        <h3>You requested a password reset</h3>
        <p>Please use the following link to reset your password:</p>
        <p><a href="http://localhost:8501/?page=reset_password_page&token={token}">Reset Password</a></p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html, 'html'))

    try:
        #print(f"Attempting to send reset email to {email} via Mailjet...")  # Debugging log
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Initiating TLS connection
            print("TLS connection initiated")
            server.login(smtp_username, smtp_password)  # Logging into Mailjet
            print("Logged into Mailjet SMTP server")
            server.send_message(msg)  # Sending email
            print(f"Reset email sent to {email}")  # Log success
    except Exception as e:
        st.error(f"Failed to send reset email: {e}")
        print(f"Error: {e}")  # Log the error for debugging



def register_user(email, token, username):
    
        #Get mailjet credentials for sending email
        #print("I made it to the register user function")
        mailjet_creds = st.secrets["mailjet"]
        mailuser = mailjet_creds["API_KEY"]
        mail_pass =mailjet_creds["SECRET_KEY"] 
    
        sender_email = "randy@chainlinkanalytics.com"  # Your email registered with Mailjet
        smtp_username = mailuser  # Your Mailjet API Key
        smtp_password = mail_pass  # Your Mailjet Secret Key
        smtp_server = "in-v3.mailjet.com"
        smtp_port = 587  # For TLS

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = email
        msg['Subject'] = "Register User"
        html = f"""\
        <html>
          <body>
            <h3>Register User</h3>
            <p>Please use the following link to register new user passowrd Chainlink Analytics:</p>
            <p><a href="http://localhost:8501/Registration?token={token}">Register</a></p>

          </body>
        </html>
        """
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)

        #print("Email sent successfully.")