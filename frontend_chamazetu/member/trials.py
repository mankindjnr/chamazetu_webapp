from datetime import datetime, timedelta

# Current date
current_date = datetime.strptime("17-February-2024", "%d-%B-%Y")

# Subtract a week
contrib_date = current_date - timedelta(days=7)

print("Contributed date (a week before):", contrib_date.strftime("%d-%m-%Y"))
