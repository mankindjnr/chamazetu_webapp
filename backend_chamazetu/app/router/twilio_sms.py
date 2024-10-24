import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_test_number = os.getenv("TWILIO_DEMO_NUMBER")

client = Client(account_sid, auth_token)

message = client.messages.create(
    from_=twilio_test_number, body="Hi there", to="+254720090889"
)

print(message.sid)
