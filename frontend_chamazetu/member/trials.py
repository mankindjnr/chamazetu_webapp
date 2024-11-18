[2024-11-10 15:54:19,369: INFO/MainProcess] Task app.celery.process_callback[ac30e4c0-a26f-48d5-a5e9-984b71b259f6] received
celery_backend_worker-2  | [2024-11-10 15:54:19,370: WARNING/MainProcess] ======c2b callback=====
celery_backend_worker-2  | [2024-11-10 15:54:19,374: WARNING/MainProcess] ======c2b callback commiting=====
celery_backend_worker-2  | [2024-11-10 15:54:19,382: INFO/MainProcess] Task app.celery.process_callback[ac30e4c0-a26f-48d5-a5e9-984b71b259f6] succeeded in 0.012108460068702698s: None
celery_backend_worker-2  | [2024-11-11 08:40:50,894: INFO/MainProcess] Task app.celery.process_b2c_result[500026c7-bbde-4c0e-86c2-979ec4d5c3ce] received
celery_backend_worker-2  | [2024-11-11 08:40:50,895: INFO/MainProcess] Result: {'Result': {'ResultType': 0, 'ResultCode': 0, 'ResultDesc': 'The service request is processed successfully.', 'OriginatorConversationID': 'UWW_254792544472-11112024084049265478-6199', 'ConversationID': 'AG_20241111_20106496ff42ae53aea5', 'TransactionID': 'SKB9DNCQWX', 'ResultParameters': {'ResultParameter': [{'Key': 'TransactionAmount', 'Value': 1000}, {'Key': 'TransactionReceipt', 'Value': 'SKB9DNCQWX'}, {'Key': 'ReceiverPartyPublicName', 'Value': '254792544472 - VALERIA WANJIKU THINWA'}, {'Key': 'TransactionCompletedDateTime', 'Value': '11.11.2024 08:40:50'}, {'Key': 'B2CUtilityAccountAvailableFunds', 'Value': 7553.0}, {'Key': 'B2CWorkingAccountAvailableFunds', 'Value': 0.0}, {'Key': 'B2CRecipientIsRegisteredCustomer', 'Value': 'Y'}, {'Key': 'B2CChargesPaidAccountAvailableFunds', 'Value': 0.0}]}, 'ReferenceData': {'ReferenceItem': {'Key': 'QueueTimeoutURL', 'Value': 'http://internalapi.safaricom.co.ke/mpesa/b2cresults/v1/submit'}}}}
celery_backend_worker-2  | [2024-11-11 08:40:50,901: WARNING/MainProcess] ===chamazetu's withdrawal fees:
celery_backend_worker-2  | [2024-11-11 08:40:50,901: WARNING/MainProcess]  
celery_backend_worker-2  | [2024-11-11 08:40:50,901: WARNING/MainProcess] 129.75
celery_backend_worker-2  | [2024-11-11 08:40:50,908: INFO/MainProcess] Task app.celery.process_b2c_result[500026c7-bbde-4c0e-86c2-979ec4d5c3ce] succeeded in 0.013730427017435431s: None
celery_backend_worker-2  | [2024-11-12 12:45:15,458: INFO/MainProcess] Task app.celery.process_b2c_result[c86e591e-80a5-44a7-9e84-3028be657497] received
celery_backend_worker-2  | [2024-11-12 12:45:15,458: INFO/MainProcess] Result: {'Result': {'ResultType': 0, 'ResultCode': 0, 'ResultDesc': 'The service request is processed successfully.', 'OriginatorConversationID': 'UWW_254797256965-12112024124514231720-7815', 'ConversationID': 'AG_20241112_20706fc94276fe711ec9', 'TransactionID': 'SKC6IOG06C', 'ResultParameters': {'ResultParameter': [{'Key': 'TransactionAmount', 'Value': 1970}, {'Key': 'TransactionReceipt', 'Value': 'SKC6IOG06C'}, {'Key': 'ReceiverPartyPublicName', 'Value': '0797256965 - Virginia mugure kairu'}, {'Key': 'TransactionCompletedDateTime', 'Value': '12.11.2024 12:45:15'}, {'Key': 'B2CUtilityAccountAvailableFunds', 'Value': 5574.0}, {'Key': 'B2CWorkingAccountAvailableFunds', 'Value': 0.0}, {'Key': 'B2CRecipientIsRegisteredCustomer', 'Value': 'Y'}, {'Key': 'B2CChargesPaidAccountAvailableFunds', 'Value': 0.0}]}, 'ReferenceData': {'ReferenceItem': {'Key': 'QueueTimeoutURL', 'Value': 'http://internalapi.safaricom.co.ke/mpesa/b2cresults/v1/submit'}}}}
celery_backend_worker-2  | [2024-11-12 12:45:15,465: WARNING/MainProcess] ===chamazetu's withdrawal fees:
celery_backend_worker-2  | [2024-11-12 12:45:15,465: WARNING/MainProcess]  
celery_backend_worker-2  | [2024-11-12 12:45:15,465: WARNING/MainProcess] 145.5
celery_backend_worker-2  | [2024-11-12 12:45:15,471: INFO/MainProcess] Task app.celery.process_b2c_result[c86e591e-80a5-44a7-9e84-3028be657497] succeeded in 0.012780392076820135s: None
celery_backend_worker-2  | [2024-11-13 18:59:14,260: INFO/MainProcess] Task app.celery.process_callback[23c57b33-e6a7-4b89-a35b-3398ae2e341b] received
celery_backend_worker-2  | [2024-11-13 18:59:14,261: WARNING/MainProcess] ======c2b callback=====
celery_backend_worker-2  | [2024-11-13 18:59:14,261: ERROR/MainProcess] Failed to update transaction
celery_backend_worker-2  | : unconverted data remains: 2
celery_backend_worker-2  | [2024-11-13 18:59:14,263: ERROR/MainProcess] Task app.celery.process_callback[23c57b33-e6a7-4b89-a35b-3398ae2e341b] raised unexpected: HTTPException()
celery_backend_worker-2  | Traceback (most recent call last):
celery_backend_worker-2  |   File "/usr/local/lib/python3.10/site-packages/celery/app/trace.py", line 451, in trace_task
celery_backend_worker-2  |     R = retval = fun(*args, **kwargs)
celery_backend_worker-2  |   File "/usr/local/lib/python3.10/site-packages/celery/app/trace.py", line 734, in __protected_call__
celery_backend_worker-2  |     return self.run(*args, **kwargs)
celery_backend_worker-2  |   File "/app/backend/app/celery.py", line 145, in process_callback
celery_backend_worker-2  |     raise HTTPException(status_code=500, detail="Failed to update transaction")
celery_backend_worker-2  | fastapi.exceptions.HTTPException
