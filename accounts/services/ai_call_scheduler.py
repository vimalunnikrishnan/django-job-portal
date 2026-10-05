from datetime import datetime, time, timedelta


AI_CALL_START_TIME = time(9, 0)
AI_CALL_END_TIME = time(18, 0)


def is_within_ai_call_window(current_time):
    return AI_CALL_START_TIME <= current_time <= AI_CALL_END_TIME


def get_next_ai_call_time(current_datetime):
    current_time = current_datetime.time()

    if is_within_ai_call_window(current_time):
        return current_datetime

    if current_time < AI_CALL_START_TIME:
        return current_datetime.replace(
            hour=AI_CALL_START_TIME.hour,
            minute=AI_CALL_START_TIME.minute,
            second=0,
            microsecond=0,
        )

    next_day = current_datetime + timedelta(days=1)

    return next_day.replace(
        hour=AI_CALL_START_TIME.hour,
        minute=AI_CALL_START_TIME.minute,
        second=0,
        microsecond=0,
    )