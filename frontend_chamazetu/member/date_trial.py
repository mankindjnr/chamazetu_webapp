from datetime import datetime, timedelta


def get_sunday_date():
    today = datetime.now()
    print("today: ", today)
    # calculating the number of days to subtract to get the first day of the week
    days_to_subtract = (today.weekday() + 1) % 7
    # subtracting the days to get the first day of the week
    sunday_date = today - timedelta(days=days_to_subtract)
    return sunday_date


# sunday_date = get_sunday_date()
# print("sunday_date: ", sunday_date.strftime("%Y-%m-%d"))
