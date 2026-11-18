from datetime import datetime, time, timedelta


def within_hours(start: datetime, end: datetime, open_t: time, close_t: time) -> bool:
    """start/end - местное наивное время. close < open означает работу через полночь
    (окно открытия дня D заканчивается в close дня D+1). Закрытие включительно.
    Переходы на летнее время не учитываются."""
    overnight = close_t < open_t
    for d in (0, -1):
        day = start.date() + timedelta(days=d)
        ws = datetime.combine(day, open_t)
        we = datetime.combine(day + timedelta(days=1 if overnight else 0), close_t)
        if ws <= start <= we and end <= we:
            return True
    return False
