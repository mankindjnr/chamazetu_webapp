from datetime import datetime, timedelta
import calendar


# ====== custom interval for interval 'custom'=======
def calculate_custom_interval(
    set_contribution_date: datetime, contribution_day: int
) -> datetime:
    return set_contribution_date + timedelta(days=contribution_day)


# ======monthly interval for interval 'first', 'second', 'third', 'fourth', 'last'=======
def get_nth_weekday(year, month, n, weekday):
    month_calenday = calendar.monthcalendar(year, month)
    weekday_occurences = [
        week[weekday] for week in month_calenday if week[weekday] != 0
    ]

    # handle 'last' by picking the last occurence
    if n == "last":
        return weekday_occurences[-1]

    # for 'first' 'second' 'third' 'fourth' occurence
    n_dict = {"first": 0, "second": 1, "third": 2, "fourth": 3}
    return weekday_occurences[n_dict[n]]


def calculate_monthly_interval(
    set_contribution_date: datetime, interval: str, contribution_day: str
) -> datetime:
    weekday_map = {
        "monday": calendar.MONDAY,
        "tuesday": calendar.TUESDAY,
        "wednesday": calendar.WEDNESDAY,
        "thursday": calendar.THURSDAY,
        "friday": calendar.FRIDAY,
        "saturday": calendar.SATURDAY,
        "sunday": calendar.SUNDAY,
    }
    next_month = (set_contribution_date.month % 12) + 1
    year = (
        set_contribution_date.year
        if next_month != 1
        else set_contribution_date.year + 1
    )
    weekday = weekday_map[contribution_day.lower()]

    # get the nth weekday weekday of the next month
    day = get_nth_weekday(year, next_month, interval, weekday)
    return datetime(year, next_month, day)


# ========daily frequency interval=======
def calculate_daily_interval(set_contribution_date: datetime) -> datetime:
    return set_contribution_date + timedelta(days=1)


# ========weekly frequency interval=======
def calculate_weekly_interval(set_contribution_date: datetime) -> datetime:
    return set_contribution_date + timedelta(weeks=1)


# ====== monthly interval for interval monthly=======
def calculate_monthly_same_day_interval(
    set_contribution_date: datetime, contribution_day: int
) -> datetime:
    next_month = (set_contribution_date.month % 12) + 1
    year = (
        set_contribution_date.year
        if next_month != 1
        else set_contribution_date.year + 1
    )
    day = contribution_day

    # handle months without that day i.e 31st in february
    last_day_of_next_month = calendar.monthrange(year, next_month)[1]
    day = min(day, last_day_of_next_month)

    return datetime(year, next_month, day)
