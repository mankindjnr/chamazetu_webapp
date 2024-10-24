data = {'Result': {'ResultType': 0, 'ResultCode': 0, 'ResultDesc': 'The service request is processed successfully.', 'OriginatorConversationID': '4fe9-4cd8-ab70-95b3e86ac48931144451', 'ConversationID': 'AG_20241021_20705853e484ff6a5c9a', 'TransactionID': 'SJL0000000', 'ResultParameters': {'ResultParameter': [{'Key': 'DebitPartyName', 'Value': '0113638169 - Amos Njoroge Kairu'}, {'Key': 'CreditPartyName', 'Value': '4138859 - BLACKALPHA NJOROGE VENTURES                  '}, {'Key': 'OriginatorConversationID', 'Value': 'ecab-4c60-99d3-11c7168133a080291247'}, {'Key': 'InitiatedTime', 'Value': 20241021164723}, {'Key': 'CreditPartyCharges'}, {'Key': 'DebitAccountType', 'Value': 'MMF Account For Customer'}, {'Key': 'TransactionReason'}, {'Key': 'ReasonType', 'Value': 'Pay Bill Online'}, {'Key': 'TransactionStatus', 'Value': 'Completed'}, {'Key': 'FinalisedTime', 'Value': 20241021164723}, {'Key': 'Amount', 'Value': 15.0}, {'Key': 'ConversationID', 'Value': 'AG_20241021_2050623fc5a70dcdf719'}, {'Key': 'ReceiptNo', 'Value': 'SJL8VE7ONE'}]}, 'ReferenceData': {'ReferenceItem': {'Key': 'Occasion', 'Value': '2/UWD_WBR2003-21102024164716-2460'}}}}

# exrract phone number
phone_number = data['Result']['ResultParameters']['ResultParameter'][0]['Value'].split(' ')[0]
print(phone_number)

# extract amount
amount = data['Result']['ResultParameters']['ResultParameter'][-3]['Value']
print(int(amount))

# extract transaction result code
result_code = data['Result']['ResultCode']
print(result_code)

# extract result type
result_type = data['Result']['ResultType']
print(result_type)

# extract receipt number
receipt_number = data['Result']['ResultParameters']['ResultParameter'][-1]['Value']
print(receipt_number)

# extract the occasion
occasion = data['Result']['ReferenceData']['ReferenceItem']['Value']
user_id, unprocessed_code = data['Result']['ReferenceData']['ReferenceItem']['Value'].split('/')
print(occasion)
print( user_id)
print(unprocessed_code)