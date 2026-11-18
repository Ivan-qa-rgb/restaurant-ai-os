from datetime import datetime, timedelta


def normalize_date(value):
    if not value:
        return ""

    value = value.strip().lower()

    if value in ("сегодня", "today"):
        return datetime.now().strftime("%Y-%m-%d")

    if value in ("завтра", "tomorrow"):
        return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return value
