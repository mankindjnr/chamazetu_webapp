from passlib.context import CryptContext
import random
from collections import defaultdict

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str):
    return pwd_context.verify(password, hashed_password)


def shuffle_list(rotation_order):
    grouped_records = defaultdict(list)
    for record in rotation_order:
        grouped_records[record["recipient_id"]].append(record)

    # Sort the groups by the number of records they have (to start with the largest group)
    sorted_groups = sorted(grouped_records.values(), key=len, reverse=True)

    # Initialize the result list
    shuffled_records = []

    # Distribute the records in a round-robin fashion
    while any(sorted_groups):  # While there are still records to distribute
        for group in sorted_groups:
            if group:
                shuffled_records.append(group.pop(0))

        # Sort the remaining groups again to keep larger groups at the front
        sorted_groups = sorted(
            [group for group in sorted_groups if group], key=len, reverse=True
        )

    # Check the result for consecutive recipient_id occurrences
    def has_consecutive_recipients(records):
        for i in range(1, len(records)):
            if records[i]["recipient_id"] == records[i - 1]["recipient_id"]:
                return True
        return False

    # If consecutive records have the same recipient_id, reshuffle
    attempts = 0
    while has_consecutive_recipients(shuffled_records):
        random.shuffle(shuffled_records)
        attempts += 1
        if attempts > 1000:  # Safety limit for reshuffling
            break

    return shuffled_records
