"""Xabarnoma jadvali (yakuniy qaror):

- daily3 (standart): 08:00, 13:00, 19:00 (fermer vaqt zonasi)
- 2h / 4h / 8h / 10h: 08:00 dan boshlab har N soat, faqat 07:00–21:00 oralig'ida
- weekly: dushanba 08:00 · monthly: oyning 1-kuni 08:00
Tezkor ogohlantirishlar bu jadvalga bog'liq emas.
"""
from datetime import datetime, time, timedelta

SCHEDULES = ("daily3", "2h", "4h", "8h", "10h", "weekly", "monthly")
WINDOW_START, WINDOW_END = 7, 21
START_HOUR = 8


def _day_slots(schedule: str, day) -> list[datetime]:
    if schedule == "daily3":
        hours = [8, 13, 19]
    elif schedule.endswith("h") and schedule[:-1].isdigit():
        step = int(schedule[:-1])
        hours = [h for h in range(START_HOUR, 24, step) if WINDOW_START <= h <= WINDOW_END]
    else:
        return []
    return [datetime.combine(day, time(h)) for h in hours]


def last_slot(schedule: str, now_local: datetime) -> datetime:
    """now_local (tz-aware) dan oldingi eng so'nggi rejali vaqt."""
    tz = now_local.tzinfo
    naive = now_local.replace(tzinfo=None)
    schedule = schedule if schedule in SCHEDULES else "daily3"
    if schedule == "weekly":
        monday = (naive - timedelta(days=naive.weekday())).replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
        slot = monday if monday <= naive else monday - timedelta(days=7)
        return slot.replace(tzinfo=tz)
    if schedule == "monthly":
        first = naive.replace(day=1, hour=START_HOUR, minute=0, second=0, microsecond=0)
        if first > naive:
            prev = (first - timedelta(days=1)).replace(day=1)
            first = prev
        return first.replace(tzinfo=tz)
    for back in range(0, 3):
        day = (naive - timedelta(days=back)).date()
        slots = [s for s in _day_slots(schedule, day) if s <= naive]
        if slots:
            return max(slots).replace(tzinfo=tz)
    return naive.replace(tzinfo=tz)


def is_due(schedule: str, now_local: datetime, last_report_local: datetime | None) -> bool:
    slot = last_slot(schedule, now_local)
    if last_report_local is None:
        # yangi dala: faqat yaqinda (60 daqiqa ichida) kelgan slotda yuboramiz — tunda "eski" slot uchun xabar ketmasin
        return now_local - slot <= timedelta(minutes=60)
    return last_report_local < slot
