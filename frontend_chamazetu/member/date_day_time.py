from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# we get the last sunday date
def get_sunday_date():
    nairobi_tz = ZoneInfo("Africa/Nairobi")
    today = datetime.now(nairobi_tz)
    print(today)
    # calculating the number of days to subtract to get the first day of the week
    days_to_subtract = (today.weekday() + 1) % 7
    # subtracting the days to get the first day of the week
    sunday_date = today - timedelta(days=days_to_subtract)
    return sunday_date


# convert a date to day name
def extract_date_time(date):
    nairobi_tz = ZoneInfo("Africa/Nairobi")
    date_time = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%f")
    date_time = date_time.replace(tzinfo=nairobi_tz)

    date_time = date_time.astimezone(nairobi_tz)

    date = date_time.date()
    time = date_time.strftime("%H:%M:%S")
    day = date_time.strftime("%A")
    return {"date": date, "time": time, "day": day}
