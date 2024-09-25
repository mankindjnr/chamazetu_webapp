result = {
    "Result": {
        "ResultType": 0,
        "ResultCode": 0,
        "ResultDesc": "The service request is processed successfully.",
        "OriginatorConversationID": "UWW_254113638169-23092024170839-2938",
        "ConversationID": "AG_20240923_205073ddd7a33320056f",
        "TransactionID": "SIN5LJDZ7Z",
        "ResultParameters": {
            "ResultParameter": [
                {"Key": "TransactionAmount", "Value": 100},
                {"Key": "TransactionReceipt", "Value": "SIN5LJDZ7Z"},
                {
                    "Key": "ReceiverPartyPublicName",
                    "Value": "0113638169 - Amos Njoroge Kairu",
                },
                {"Key": "TransactionCompletedDateTime", "Value": "23.09.2024 17:08:40"},
                {"Key": "B2CUtilityAccountAvailableFunds", "Value": 5225.0},
                {"Key": "B2CWorkingAccountAvailableFunds", "Value": 0.0},
                {"Key": "B2CRecipientIsRegisteredCustomer", "Value": "Y"},
                {"Key": "B2CChargesPaidAccountAvailableFunds", "Value": 0.0},
            ]
        },
        "ReferenceData": {
            "ReferenceItem": {
                "Key": "QueueTimeoutURL",
                "Value": "http://internalapi.safaricom.co.ke/mpesa/b2cresults/v1/submit",
            }
        },
    }
}

# extract all to this
# Example Output:
# {
#   'TransactionAmount': 100,
#   'TransactionReceipt': 'SIN1K4YXE1',
#   'ReceiverPartyPublicName': '254720090889 - AMOS NJOROGE KAIRU',
#   'TransactionCompletedDateTime': '23.09.2024 10:42:24',
#   'B2CUtilityAccountAvailableFunds': 5139.0,
#   'B2CWorkingAccountAvailableFunds': 0.0,
#   'B2CRecipientIsRegisteredCustomer': 'Y',
#   'B2CChargesPaidAccountAvailableFunds': 0.0

# }

conversation_id = result.get("Result", {}).get("OriginatorConversationID", "")
print(conversation_id)
transaction_id = result.get("Result", {}).get("TransactionID", "")
print(transaction_id)
result_type = result.get("Result", {}).get("ResultType", "")
print(result_type)
result_code = result.get("Result", {}).get("ResultCode", "")
print(result_code)
result_desc = result.get("Result", {}).get("ResultDesc", "")
print(result_desc)

print("\n")


def extract_result(result: dict) -> dict:
    result_parameters = (
        result.get("Result", {}).get("ResultParameters", {}).get("ResultParameter", [])
    )
    return {param["Key"]: param["Value"] for param in result_parameters}


print(extract_result(result))


# extract originator conversation id
# Example Output:
# UWW_254113638169-23092024170839-2938
def extract_originator_conversation_id(result: dict) -> str:
    return result.get("Result", {}).get("OriginatorConversationID", "")


print("\n", extract_originator_conversation_id(result))
