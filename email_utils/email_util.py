import streamlit as st
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders




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




def send_gap_report(logged_in_user, logged_in_email, salesperson_email, salesperson_name, report_file):
    """Sends the gap report as an email attachment from the logged-in user to the salesperson."""
    
    # Get Mailjet credentials
    mailjet_creds = st.secrets["mailjet"]
    smtp_username = mailjet_creds["API_KEY"]
    smtp_password = mailjet_creds["SECRET_KEY"]
    smtp_server = "in-v3.mailjet.com"
    smtp_port = 587

    # Set sender dynamically
    sender_email = logged_in_email  # Now the email comes from the logged-in user

    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = salesperson_email
    msg['Subject'] = f"🚨 Gap Report - {salesperson_name}"

    # Email Body
    html = f"""
    <html>
      <body>
        <h3>Gap Report for {salesperson_name}</h3>
        <p>Attached is your latest gap report showing missing products in stores.</p>
        <p>Please review and take necessary action.</p>
        <p>Sent by: <b>{logged_in_user} ({logged_in_email})</b></p>
        <p>Best Regards,<br>Chainlink Analytics Team</p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html, 'html'))

    # Attach Excel File
    part = MIMEBase("application", "octet-stream")
    part.set_payload(report_file.read())  # Read the file into the attachment
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f"attachment; filename=gap_report_{salesperson_name}.xlsx",
    )
    msg.attach(part)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        return f"✅ Gap report successfully sent to {salesperson_name} from {logged_in_user}!"
    except Exception as e:
        return f"❌ Failed to send gap report: {str(e)}"
