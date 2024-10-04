rotation_order = [
    {
        "recipient_id": 2,
        "user_name": "memlo lumlu",
        "share_value": 100,
        "share_name": "Alpha",
        "activity_id": 7,
        "expected_amount": 1300,
    },
    {
        "recipient_id": 6,
        "user_name": "varko yagna",
        "share_value": 100,
        "share_name": "Alpha",
        "activity_id": 7,
        "expected_amount": 1300,
    },
    {
        "recipient_id": 6,
        "user_name": "varko yagna",
        "share_value": 100,
        "share_name": "Beta",
        "activity_id": 7,
        "expected_amount": 1300,
    },
    {
        "recipient_id": 6,
        "user_name": "varko yagna",
        "share_value": 100,
        "share_name": "Gamma",
        "activity_id": 7,
        "expected_amount": 1300,
    },
    {
        "recipient_id": 6,
        "user_name": "varko yagna",
        "share_value": 100,
        "share_name": "Delta",
        "activity_id": 7,
        "expected_amount": 1300,
    },
    {
        "recipient_id": 4,
        "user_name": "zodru yostu",
        "share_value": 100,
        "share_name": "Alpha",
        "activity_id": 7,
        "expected_amount": 1300,
    },
    {
        "recipient_id": 3,
        "user_name": "nasta masta",
        "share_value": 100,
        "share_name": "Alpha",
        "activity_id": 7,
        "expected_amount": 1300,
    },
    {
        "recipient_id": 4702,
        "user_name": "mirka pelte",
        "share_value": 100,
        "share_name": "Alpha",
        "activity_id": 7,
        "expected_amount": 1300,
    },
    {
        "recipient_id": 4702,
        "user_name": "mirka pelte",
        "share_value": 100,
        "share_name": "Beta",
        "activity_id": 7,
        "expected_amount": 1300,
    },
    {
        "recipient_id": 9,
        "user_name": "sart sulmo",
        "share_value": 100,
        "share_name": "Alpha",
        "activity_id": 7,
        "expected_amount": 1300,
    },
    {
        "recipient_id": 9,
        "user_name": "sart sulmo",
        "share_value": 100,
        "share_name": "Beta",
        "activity_id": 7,
        "expected_amount": 1300,
    },
    {
        "recipient_id": 9,
        "user_name": "sart sulmo",
        "share_value": 100,
        "share_name": "Gamma",
        "activity_id": 7,
        "expected_amount": 1300,
    },
    {
        "recipient_id": 10,
        "user_name": "badri yefya",
        "share_value": 100,
        "share_name": "Alpha",
        "activity_id": 7,
        "expected_amount": 1300,
    },
]

import random
from collections import defaultdict

# Group records by recipient_id
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

# Print the final result
for record in shuffled_records:
    print(record)


{
    "recipient_id": 6,
    "user_name": "varko yagna",
    "share_value": 100,
    "share_name": "Alpha",
    "activity_id": 7,
    "expected_amount": 1300,
}
{
    "recipient_id": 9,
    "user_name": "sart sulmo",
    "share_value": 100,
    "share_name": "Alpha",
    "activity_id": 7,
    "expected_amount": 1300,
}
{
    "recipient_id": 4702,
    "user_name": "mirka pelte",
    "share_value": 100,
    "share_name": "Alpha",
    "activity_id": 7,
    "expected_amount": 1300,
}
{
    "recipient_id": 2,
    "user_name": "memlo lumlu",
    "share_value": 100,
    "share_name": "Alpha",
    "activity_id": 7,
    "expected_amount": 1300,
}
{
    "recipient_id": 4,
    "user_name": "zodru yostu",
    "share_value": 100,
    "share_name": "Alpha",
    "activity_id": 7,
    "expected_amount": 1300,
}
{
    "recipient_id": 3,
    "user_name": "nasta masta",
    "share_value": 100,
    "share_name": "Alpha",
    "activity_id": 7,
    "expected_amount": 1300,
}
{
    "recipient_id": 10,
    "user_name": "badri yefya",
    "share_value": 100,
    "share_name": "Alpha",
    "activity_id": 7,
    "expected_amount": 1300,
}
{
    "recipient_id": 6,
    "user_name": "varko yagna",
    "share_value": 100,
    "share_name": "Beta",
    "activity_id": 7,
    "expected_amount": 1300,
}
{
    "recipient_id": 9,
    "user_name": "sart sulmo",
    "share_value": 100,
    "share_name": "Beta",
    "activity_id": 7,
    "expected_amount": 1300,
}
{
    "recipient_id": 4702,
    "user_name": "mirka pelte",
    "share_value": 100,
    "share_name": "Beta",
    "activity_id": 7,
    "expected_amount": 1300,
}
{
    "recipient_id": 6,
    "user_name": "varko yagna",
    "share_value": 100,
    "share_name": "Gamma",
    "activity_id": 7,
    "expected_amount": 1300,
}
{
    "recipient_id": 9,
    "user_name": "sart sulmo",
    "share_value": 100,
    "share_name": "Gamma",
    "activity_id": 7,
    "expected_amount": 1300,
}
{
    "recipient_id": 6,
    "user_name": "varko yagna",
    "share_value": 100,
    "share_name": "Delta",
    "activity_id": 7,
    "expected_amount": 1300,
}


[
    {
        "recipient_id": 6,
        "user_name": "varko yagna",
        "share_value": 100,
        "share_name": "Alpha",
        "activity_id": 7,
        "expected_amount": 1300,
        "receiving_date": datetime.datetime(2024, 10, 2, 0, 0),
        "order_in_rotation": 1,
    },
    {
        "recipient_id": 9,
        "user_name": "sart sulmo",
        "share_value": 100,
        "share_name": "Alpha",
        "activity_id": 7,
        "expected_amount": 1300,
        "receiving_date": datetime.datetime(2024, 10, 3, 0, 0),
        "order_in_rotation": 2,
    },
    {
        "recipient_id": 4702,
        "user_name": "mirka pelte",
        "share_value": 100,
        "share_name": "Alpha",
        "activity_id": 7,
        "expected_amount": 1300,
        "receiving_date": datetime.datetime(2024, 10, 4, 0, 0),
        "order_in_rotation": 3,
    },
    {
        "recipient_id": 2,
        "user_name": "memlo lumlu",
        "share_value": 100,
        "share_name": "Alpha",
        "activity_id": 7,
        "expected_amount": 1300,
        "receiving_date": datetime.datetime(2024, 10, 5, 0, 0),
        "order_in_rotation": 4,
    },
    {
        "recipient_id": 4,
        "user_name": "zodru yostu",
        "share_value": 100,
        "share_name": "Alpha",
        "activity_id": 7,
        "expected_amount": 1300,
        "receiving_date": datetime.datetime(2024, 10, 6, 0, 0),
        "order_in_rotation": 5,
    },
    {
        "recipient_id": 3,
        "user_name": "nasta masta",
        "share_value": 100,
        "share_name": "Alpha",
        "activity_id": 7,
        "expected_amount": 1300,
        "receiving_date": datetime.datetime(2024, 10, 7, 0, 0),
        "order_in_rotation": 6,
    },
    {
        "recipient_id": 10,
        "user_name": "badri yefya",
        "share_value": 100,
        "share_name": "Alpha",
        "activity_id": 7,
        "expected_amount": 1300,
        "receiving_date": datetime.datetime(2024, 10, 8, 0, 0),
        "order_in_rotation": 7,
    },
    {
        "recipient_id": 6,
        "user_name": "varko yagna",
        "share_value": 100,
        "share_name": "Beta",
        "activity_id": 7,
        "expected_amount": 1300,
        "receiving_date": datetime.datetime(2024, 10, 9, 0, 0),
        "order_in_rotation": 8,
    },
    {
        "recipient_id": 9,
        "user_name": "sart sulmo",
        "share_value": 100,
        "share_name": "Beta",
        "activity_id": 7,
        "expected_amount": 1300,
        "receiving_date": datetime.datetime(2024, 10, 10, 0, 0),
        "order_in_rotation": 9,
    },
    {
        "recipient_id": 4702,
        "user_name": "mirka pelte",
        "share_value": 100,
        "share_name": "Beta",
        "activity_id": 7,
        "expected_amount": 1300,
        "receiving_date": datetime.datetime(2024, 10, 11, 0, 0),
        "order_in_rotation": 10,
    },
    {
        "recipient_id": 6,
        "user_name": "varko yagna",
        "share_value": 100,
        "share_name": "Gamma",
        "activity_id": 7,
        "expected_amount": 1300,
        "receiving_date": datetime.datetime(2024, 10, 12, 0, 0),
        "order_in_rotation": 11,
    },
    {
        "recipient_id": 9,
        "user_name": "sart sulmo",
        "share_value": 100,
        "share_name": "Gamma",
        "activity_id": 7,
        "expected_amount": 1300,
        "receiving_date": datetime.datetime(2024, 10, 13, 0, 0),
        "order_in_rotation": 12,
    },
    {
        "recipient_id": 6,
        "user_name": "varko yagna",
        "share_value": 100,
        "share_name": "Delta",
        "activity_id": 7,
        "expected_amount": 1300,
        "receiving_date": datetime.datetime(2024, 10, 14, 0, 0),
        "order_in_rotation": 13,
    },
]


[
    {
        "chama_id": 5,
        "activity_id": 7,
        "contributor_id": 6,
        "share_name": "Alpha",
        "expected_amount": 1300,
        "contributed_amount": 0,
        "fine": 0,
        "cycle_number": 1,
        "recipient_id": 6,
        "rotation_date": datetime.datetime(2024, 10, 2, 0, 0),
    },
    {
        "chama_id": 5,
        "activity_id": 7,
        "contributor_id": 9,
        "share_name": "Alpha",
        "expected_amount": 1300,
        "contributed_amount": 0,
        "fine": 0,
        "cycle_number": 1,
        "recipient_id": 6,
        "rotation_date": datetime.datetime(2024, 10, 2, 0, 0),
    },
    {
        "chama_id": 5,
        "activity_id": 7,
        "contributor_id": 4702,
        "share_name": "Alpha",
        "expected_amount": 1300,
        "contributed_amount": 0,
        "fine": 0,
        "cycle_number": 1,
        "recipient_id": 6,
        "rotation_date": datetime.datetime(2024, 10, 2, 0, 0),
    },
    {
        "chama_id": 5,
        "activity_id": 7,
        "contributor_id": 2,
        "share_name": "Alpha",
        "expected_amount": 1300,
        "contributed_amount": 0,
        "fine": 0,
        "cycle_number": 1,
        "recipient_id": 6,
        "rotation_date": datetime.datetime(2024, 10, 2, 0, 0),
    },
    {
        "chama_id": 5,
        "activity_id": 7,
        "contributor_id": 4,
        "share_name": "Alpha",
        "expected_amount": 1300,
        "contributed_amount": 0,
        "fine": 0,
        "cycle_number": 1,
        "recipient_id": 6,
        "rotation_date": datetime.datetime(2024, 10, 2, 0, 0),
    },
    {
        "chama_id": 5,
        "activity_id": 7,
        "contributor_id": 3,
        "share_name": "Alpha",
        "expected_amount": 1300,
        "contributed_amount": 0,
        "fine": 0,
        "cycle_number": 1,
        "recipient_id": 6,
        "rotation_date": datetime.datetime(2024, 10, 2, 0, 0),
    },
    {
        "chama_id": 5,
        "activity_id": 7,
        "contributor_id": 10,
        "share_name": "Alpha",
        "expected_amount": 1300,
        "contributed_amount": 0,
        "fine": 0,
        "cycle_number": 1,
        "recipient_id": 6,
        "rotation_date": datetime.datetime(2024, 10, 2, 0, 0),
    },
    {
        "chama_id": 5,
        "activity_id": 7,
        "contributor_id": 6,
        "share_name": "Beta",
        "expected_amount": 1300,
        "contributed_amount": 0,
        "fine": 0,
        "cycle_number": 1,
        "recipient_id": 6,
        "rotation_date": datetime.datetime(2024, 10, 2, 0, 0),
    },
    {
        "chama_id": 5,
        "activity_id": 7,
        "contributor_id": 9,
        "share_name": "Beta",
        "expected_amount": 1300,
        "contributed_amount": 0,
        "fine": 0,
        "cycle_number": 1,
        "recipient_id": 6,
        "rotation_date": datetime.datetime(2024, 10, 2, 0, 0),
    },
    {
        "chama_id": 5,
        "activity_id": 7,
        "contributor_id": 4702,
        "share_name": "Beta",
        "expected_amount": 1300,
        "contributed_amount": 0,
        "fine": 0,
        "cycle_number": 1,
        "recipient_id": 6,
        "rotation_date": datetime.datetime(2024, 10, 2, 0, 0),
    },
    {
        "chama_id": 5,
        "activity_id": 7,
        "contributor_id": 6,
        "share_name": "Gamma",
        "expected_amount": 1300,
        "contributed_amount": 0,
        "fine": 0,
        "cycle_number": 1,
        "recipient_id": 6,
        "rotation_date": datetime.datetime(2024, 10, 2, 0, 0),
    },
    {
        "chama_id": 5,
        "activity_id": 7,
        "contributor_id": 9,
        "share_name": "Gamma",
        "expected_amount": 1300,
        "contributed_amount": 0,
        "fine": 0,
        "cycle_number": 1,
        "recipient_id": 6,
        "rotation_date": datetime.datetime(2024, 10, 2, 0, 0),
    },
    {
        "chama_id": 5,
        "activity_id": 7,
        "contributor_id": 6,
        "share_name": "Delta",
        "expected_amount": 1300,
        "contributed_amount": 0,
        "fine": 0,
        "cycle_number": 1,
        "recipient_id": 6,
        "rotation_date": datetime.datetime(2024, 10, 2, 0, 0),
    },
]
