from datetime import timedelta, datetime

def generate_occurrences(start_date, end_date, weekdays, holidays=[]):
    # Convert input strings to datetime objects
    start_date = datetime.strptime(start_date, "%d/%m/%Y")
    end_date = datetime.strptime(end_date, "%d/%m/%Y")

    # Validate input
    if start_date > end_date:
        raise ValueError("Start date must be before or equal to end date")

    # Initialize list to store occurrences
    occurrences = []

    # Generate occurrences
    current_date = start_date
    while current_date <= end_date:
        if current_date.strftime('%A') in weekdays and not any(
            datetime.strptime(holiday[0], "%d/%m/%Y") <= current_date <= datetime.strptime(holiday[1], "%d/%m/%Y") for holiday in holidays
        ):
            occurrences.append(current_date.strftime("%d/%m/%Y"))
        current_date += timedelta(days=1)

    return occurrences


if __name__ == '__main__':
    start_date = "01/11/2023"
    end_date = "30/11/2023"
    weekdays = ["Wednesday"]

    print(generate_occurrences(start_date, end_date, weekdays, [('08/11/2023', '21/11/2023')]))