from datetime import datetime
from pytz import timezone, utc

# Given UTC times
utc_times = ['2024-03-10 08:14:19.885084', '2024-03-10 09:58:51.138586']

# Specify the desired time zone
desired_tz = timezone('Africa/Nairobi')  # East Africa Time

# Convert the UTC times to the desired time zone
for utc_time_str in utc_times:
    utc_time = datetime.strptime(utc_time_str, '%Y-%m-%d %H:%M:%S.%f')
    utc_time = utc_time.replace(tzinfo=utc)
    local_time = utc_time.astimezone(desired_tz)
    print(local_time)
