# Agent Intent Confusion Matrix (178 examples)

Rows represent the **true human labels**, columns represent the **predicted intents**.

| True \ Predicted | ACCOUNT_ACCESS_OR_SECURITY | DELIVERY_EXPERIENCE_OR_CARRIER_COMPLAINT | DELIVERY_LATE_OR_NOT_ARRIVED | DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED | DEVICE_OR_DIGITAL_SERVICE_ISSUE | GENERAL_SERVICE_COMPLAINT | ITEM_DAMAGED_WRONG_OR_COUNTERFEIT | OTHER_NON_ACTIONABLE | PRIME_MEMBERSHIP_OR_SUBSCRIPTION | REFUND_STATUS_OR_AMOUNT | RETURN_OR_REPLACEMENT_REQUEST | UNEXPECTED_CHARGE_OR_BILLING_ERROR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **ACCOUNT_ACCESS_OR_SECURITY** | 9 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **DELIVERY_EXPERIENCE_OR_CARRIER_COMPLAINT** | 0 | 7 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| **DELIVERY_LATE_OR_NOT_ARRIVED** | 2 | 1 | 26 | 1 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 1 |
| **DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED** | 0 | 1 | 7 | 6 | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 1 |
| **DEVICE_OR_DIGITAL_SERVICE_ISSUE** | 0 | 0 | 1 | 0 | 11 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| **GENERAL_SERVICE_COMPLAINT** | 0 | 2 | 2 | 1 | 1 | 5 | 1 | 0 | 0 | 0 | 0 | 0 |
| **ITEM_DAMAGED_WRONG_OR_COUNTERFEIT** | 0 | 1 | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 2 | 2 | 0 |
| **OTHER_NON_ACTIONABLE** | 1 | 1 | 8 | 1 | 3 | 1 | 1 | 12 | 0 | 1 | 1 | 0 |
| **PRIME_MEMBERSHIP_OR_SUBSCRIPTION** | 0 | 0 | 4 | 0 | 2 | 1 | 0 | 0 | 3 | 1 | 0 | 1 |
| **REFUND_STATUS_OR_AMOUNT** | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 1 | 0 |
| **RETURN_OR_REPLACEMENT_REQUEST** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 6 | 0 |
| **UNEXPECTED_CHARGE_OR_BILLING_ERROR** | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 2 | 0 | 1 | 0 | 10 |
