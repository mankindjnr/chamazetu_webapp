from datetime import datetime, timedelta
import calendar

def count_contribution_days(activity_title, frequency, interval, contribution_day, first_contribution_date, restart, restart_date, next_contribution_date):
    # Parse dates
    first_contribution_date = datetime.strptime(first_contribution_date, '%Y-%m-%d %H:%M:%S')
    if restart:
        start_date = datetime.strptime(restart_date, '%Y-%m-%d %H:%M:%S')
    else:
        start_date = first_contribution_date
    
    next_contribution_date = datetime.strptime(next_contribution_date, '%Y-%m-%d %H:%M:%S')
    days_passed = 0

    # Calculate based on frequency
    if frequency == 'daily':
        days_passed = (next_contribution_date - start_date).days
    
    elif frequency == 'weekly':
        # Use weekday numbers to calculate intervals
        target_weekday = getattr(calendar, contribution_day.upper())
        current_date = start_date
        while current_date < next_contribution_date:
            if current_date.weekday() == target_weekday:
                days_passed += 1
            current_date += timedelta(days=1)
    
    elif frequency == 'monthly':
        # Custom monthly calculation for specific day-of-month contributions
        current_date = start_date
        while current_date < next_contribution_date:
            if current_date.day == int(contribution_day):
                days_passed += 1
            current_date += timedelta(days=calendar.monthrange(current_date.year, current_date.month)[1])
    
    elif frequency == 'interval' and interval == 'custom':
        # For custom intervals, assume `contribution_day` represents the interval in days
        days_passed = ((next_contribution_date - start_date).days // int(contribution_day))

    return days_passed

# Example usage
activity = {
    'activity_title': 'activity one',
    'frequency': 'weekly',
    'interval': 'weekly',
    'contribution_day': 'tuesday',
    'first_contribution_date': '2024-08-27 00:00:00',
    'restart': False,
    'restart_date': None,
    'next_contribution_date': '2024-11-27 00:00:00'  # Example next contribution date
}

days_count = count_contribution_days(**activity)
print(f"Number of contribution days passed for '{activity['activity_title']}': {days_count}")
