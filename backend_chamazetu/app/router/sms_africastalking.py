# # import africastalking
# import os
# from dotenv import load_dotenv

# load_dotenv()

# # TODO: Initialize Africa's Talking
# USERNAME = os.getenv("AFRICASTALKING_USERNAME")
# API_KEY = os.getenv("AFRICASTALKING_API_KEY")
# africastalking.initialize(username=USERNAME, api_key=API_KEY)

# sms = africastalking.SMS


# class send_sms:
#     def __init__(self):
#         self.sms = africastalking.SMS

#     def sending(self):
#         # Set the numbers in international format
#         recipients = ["+254720090889"]
#         # Set your message
#         message = "chamaZetu, today is the deadline for your contribution. Kindly make your payment before the end of the day."
#         # Set your shortCode or senderId
#         sender = "zetuchama"
#         try:
#             response = self.sms.send(message, recipients, sender)
#             print(response)
#             return response
#         except Exception as e:
#             print(f"Houston, we have a problem: {e}")
#             return {"message": f"Failed to send message due to: {e}"}
