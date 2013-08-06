import datetime
from django.utils import timezone

tz = timezone.get_default_timezone()

def get_midnight():
    
    naive_midnight = datetime.datetime.combine(datetime.datetime.today(), datetime.time())
    aware_midnight = tz.localize(naive_midnight)

    return aware_midnight

            
