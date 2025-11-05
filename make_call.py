from twilio.rest import Client
from dotenv import load_dotenv
import os
load_dotenv()

# environment variables or paste directly for quick test
ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN")
FROM_NUMBER = os.environ.get("TWILIO_FROM") 
TO_NUMBER   = os.environ.get("MY_PHONE")     

client = Client(ACCOUNT_SID, AUTH_TOKEN)

call = client.calls.create(
    to=TO_NUMBER,
    from_=FROM_NUMBER,
    url="https://dissimilative-sally-allogenically.ngrok-free.dev/voice"
)

print("Call SID:", call.sid)
