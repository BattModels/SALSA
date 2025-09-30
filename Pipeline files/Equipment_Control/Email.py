import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(subject, body):
    # Set up the email
    sender_email="musev2shared@gmail.com"
    receiver_email=["cyhalek@umich.edu", 'lithium@umich.edu', 'tiz@umich.edu']
    password="vwrohjmkpfrihhvo"
    msg = MIMEMultipart()
    msg["From"] = f'Muse_v2 <{sender_email}>'
    msg["To"] =  ", ".join(receiver_email)
    msg["Subject"] = subject

    # Attach the email body
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()  # Secure the connection
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
    except Exception as e:
        print(f"Error: {e}")