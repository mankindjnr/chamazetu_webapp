import random
from datetime import datetime


def generate_transaction_code(transaction_type, origin, destination, member_id):
    # Get current month abbreviation in uppercase
    month_prefix = datetime.now().strftime("%b").upper()

    # Determine transaction prefix based on transaction type
    if transaction_type.lower() == "deposit":
        prefix = f"{month_prefix}DEPO"
    elif transaction_type.lower() == "withdrawal":
        prefix = f"{month_prefix}DRAW"
    else:
        raise ValueError("Invalid transaction type. Use 'deposit' or 'withdrawal'.")

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # Generate random element
    random_element = "".join(
        random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=5)
    )

    # Construct transaction code
    transaction_code = (
        f"{prefix}{timestamp}_{random_element}_{origin}_{destination}{member_id}"
    )

    return transaction_code
