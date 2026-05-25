import zoneinfo
from django.utils import timezone
from django.conf import settings as django_settings

def make_aware(value, tz=None):
    """
    Returns a timezone-aware datetime.

    Aware inputs are returned unchanged; naive inputs get the chosen
    timezone (defaulting to settings.TIME_ZONE) attached without
    converting wall-clock time. If a DST transition makes the time
    ambiguous, daylight saving is assumed in effect.
    """
    if timezone.is_aware(value):
        return value

    if tz is None:
        tz_code = django_settings.TIME_ZONE
        tz = zoneinfo.ZoneInfo(tz_code)

    return value.replace(tzinfo=tz)
