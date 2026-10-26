"""SQL filters and public-only facets for the conference directory."""
from datetime import datetime
import re

from pytz import UTC, timezone
from sqlalchemy import and_, func
from sqlalchemy.orm import aliased
from werkzeug.exceptions import BadRequest

from indico.modules.events import Event
from indico.modules.events.models.settings import EventSetting
from indico.modules.rb.models.locations import Location
from indico.util.date_time import now_utc

from .conference_metadata import SUBJECT_DOMAINS


def filter_conferences(query, args):
    """Return a filtered query and optional facets from the unchanged public base query."""
    selected_time = args.get('time', '')
    subject = args.get('subject', '')
    city = args.get('city', '')
    if any(ord(char) < 32 or ord(char) == 127 for char in city):
        raise BadRequest('City must not contain control characters.')
    city = city.strip(' ')  # Match SQL btrim without changing other characters in a native venue name.
    if subject and subject not in SUBJECT_DOMAINS:
        raise BadRequest('Unknown conference subject.')
    month_start = month_end = None
    if selected_time and selected_time not in ('upcoming', 'ongoing', 'ended'):
        try:
            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}', selected_time):
                raise ValueError()
            year, month = map(int, selected_time.split('-'))
            if not 1 <= year <= 9998 or not 1 <= month <= 12:
                raise ValueError()
            shanghai = timezone('Asia/Shanghai')
            month_start = shanghai.localize(datetime(year, month, 1)).astimezone(UTC)
            month_end = shanghai.localize(datetime(year + (month == 12), month % 12 + 1, 1)).astimezone(UTC)
        except (ValueError, OverflowError):
            raise BadRequest('Invalid conference start month. Use YYYY-MM.') from None
    metadata = aliased(EventSetting)
    query = query.outerjoin(metadata, and_(metadata.event_id == Event.id,
                                          metadata.module == 'plugin_yujian_site',
                                          metadata.name == 'conference_metadata'))
    query = query.outerjoin(Location, Location.id == Event.own_venue_id)
    city_value = func.btrim(func.coalesce(func.nullif(func.btrim(metadata.value['city'].astext), ''),
                                         func.nullif(func.btrim(Event.own_venue_name), ''), Location.name))
    facets = None
    if args.get('filters') == '1':
        # Indico stores UTC timestamps without a SQL timezone; attach UTC before converting.
        month_value = func.to_char(func.timezone('Asia/Shanghai', func.timezone('UTC', Event.start_dt)), 'YYYY-MM')
        facets = {'months': sorted((value for value, in query.with_entities(month_value).distinct()), reverse=True),
                  'cities': sorted(value for value, in query.with_entities(city_value).distinct()
                                   if value and not any(ord(char) < 32 or ord(char) == 127 for char in value)),
                  'subjects': list(SUBJECT_DOMAINS)}
    now = now_utc()
    if selected_time == 'upcoming':
        query = query.filter(Event.start_dt > now)
    elif selected_time == 'ongoing':
        query = query.filter(Event.start_dt <= now, Event.end_dt > now)
    elif selected_time == 'ended':
        query = query.filter(Event.end_dt <= now)
    elif month_start:
        query = query.filter(Event.start_dt >= month_start, Event.start_dt < month_end)
    if subject:
        query = query.filter(metadata.value['subject_domains'].contains([subject]))
    if city:
        query = query.filter(city_value == city)
    return query, facets
