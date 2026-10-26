"""Private summaries of native registration and abstract records."""
from sqlalchemy import or_

from indico.core.db import db
from indico.modules.events import Event
from indico.modules.events.abstracts.models.abstracts import Abstract, AbstractState
from indico.modules.events.abstracts.models.persons import AbstractPersonLink
from indico.modules.events.abstracts.util import (get_events_with_abstract_reviewer_convener,
                                                 get_track_reviewer_abstract_counts)
from indico.modules.events.models.persons import EventPerson
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration, RegistrationState
from indico.web.flask.util import url_for

from . import YujianSitePlugin


REGISTRATION_LABELS = {'complete': '报名成功', 'pending': '待审核', 'rejected': '已拒绝',
                       'withdrawn': '已撤回', 'unpaid': '待付款'}
ABSTRACT_LABELS = {'submitted': '已提交', 'withdrawn': '已撤回', 'accepted': '已录用',
                   'rejected': '未录用', 'merged': '已合并', 'duplicate': '重复稿件', 'invited': '受邀投稿'}


def event_visible(event, user, feature):
    return (not event.is_deleted and YujianSitePlugin.event_settings.get(event, 'managed')
            and event.has_feature(feature) and event.can_access(user)
            and (not YujianSitePlugin.instance.is_draft(event) or event.can_manage(user)))


def operations(event):
    registration_enabled = event.has_feature('registration')
    abstracts_enabled = event.has_feature('abstracts')
    registration = {'enabled': registration_enabled, 'total': 0, 'pending': 0, 'forms': [], 'links': {}}
    submission = {'enabled': abstracts_enabled, 'state': 'disabled', 'state_label': '尚未启用',
                  'total': 0, 'pending': 0, 'counts': {}, 'recent': [], 'links': {}}
    if registration_enabled:
        manage_url = url_for('event_registration.manage_regform_list', event_id=event.id)
        registration['links'] = {'manage_url': manage_url, 'create_url': manage_url}
        forms = RegistrationForm.query.filter_by(event_id=event.id, is_deleted=False).order_by(RegistrationForm.id)
        counts = {form_id: (count, pending) for form_id, count, pending in db.session.query(
            Registration.registration_form_id, db.func.count(Registration.id),
            db.func.count().filter(Registration.state == RegistrationState.pending)
        ).filter(Registration.event_id == event.id, ~Registration.is_deleted).group_by(
            Registration.registration_form_id)}
        for form in forms:
            count, pending = counts.get(form.id, (0, 0))
            state = 'open' if form.is_open else 'scheduled' if form.is_scheduled and not form.has_started else 'closed'
            dashboard = url_for('event_registration.manage_regform', form)
            registration['forms'].append({
                'id': form.id, 'title': form.title, 'state': state,
                'state_label': {'open': '开放中', 'scheduled': '即将开放', 'closed': '已关闭'}[state],
                'count': count, 'pending_count': pending, 'url': dashboard, 'settings_url': dashboard,
                'fields_url': url_for('event_registration.modify_regform', form),
                'list_url': url_for('event_registration.manage_reglist', form),
                'public_url': url_for('event_registration.display_regform', form)})
            registration['total'] += count
            registration['pending'] += pending
    if abstracts_enabled:
        state = 'open' if event.cfa.is_open else 'scheduled' if event.cfa.is_scheduled and not event.cfa.has_started else 'closed'
        dashboard = url_for('abstracts.management', event_id=event.id)
        query = Abstract.query.filter_by(event_id=event.id, is_deleted=False)
        counts = {state.name: count for state, count in query.with_entities(
            Abstract.state, db.func.count(Abstract.id)).group_by(Abstract.state)}
        submission.update(state=state, state_label={'open': '开放中', 'scheduled': '即将开放', 'closed': '尚未开放'}[state],
                          total=sum(counts.values()), pending=counts.get('submitted', 0), counts=counts,
                          links={'manage_url': dashboard,
                                 'list_url': url_for('abstracts.manage_abstract_list', event_id=event.id),
                                 'settings_url': dashboard, 'reviewing_url': dashboard,
                                 'review_settings_url': dashboard,
                                 'tracks_url': url_for('tracks.manage', event_id=event.id)})
        submission['recent'] = [{
            'id': abstract.id, 'number': abstract.friendly_id, 'title': abstract.title,
            'state': abstract.state.name, 'state_label': ABSTRACT_LABELS[abstract.state.name],
            'submitter': abstract.submitter.full_name, 'submitted': abstract.submitted_dt.isoformat(),
            'url': url_for('abstracts.display_abstract', abstract, management=True)
        } for abstract in query.options(db.joinedload(Abstract.submitter)).order_by(
            Abstract.submitted_dt.desc(), Abstract.id.desc()).limit(20)]
    return {'event': {'id': event.id, 'title': event.title, 'url': f'/event/{event.id}/',
                      'builder_url': f'/conference/{event.id}/', 'locked': event.is_locked,
                      'feature_url': url_for('event_features.index', event_id=event.id)},
            'features': {'registration': registration_enabled, 'abstracts': abstracts_enabled},
            'registration': registration, 'submission': submission}


def participation(user):
    from .payments import pay_url
    registrations = []
    # Native account ownership gives token-free detail and ticket URLs. Email-only records
    # are linked to accounts by Indico's own registration/account association lifecycle.
    registration_query = Registration.query.filter_by(user_id=user.id, is_deleted=False).options(
        db.joinedload(Registration.event), db.joinedload(Registration.registration_form))
    for registration in registration_query.order_by(Registration.id.desc()):
        event, form = registration.event, registration.registration_form
        if form.is_deleted or not event_visible(event, user, 'registration'):
            continue
        ticket = (registration.state == RegistrationState.complete and form.tickets_enabled
                  and (form.ticket_on_event_page or form.ticket_on_summary_page
                       or event.can_manage(user, 'registration')))
        if ticket:
            template = form.get_ticket_template()
            ticket = not (template.is_ticket and registration.is_ticket_blocked)
        registrations.append({
            'id': registration.id, 'event_id': event.id, 'event_title': event.title,
            'event_url': f'/event/{event.id}/', 'start': event.start_dt.isoformat(), 'end': event.end_dt.isoformat(),
            'location': event.venue_name, 'form_title': form.title, 'state': registration.state.name,
            'state_label': REGISTRATION_LABELS[registration.state.name],
            'url': url_for('event_registration.display_regform', form),
            'can_modify': bool(not event.is_locked and registration.can_be_modified),
            'payment_url': pay_url(registration),
            'ticket_url': url_for('event_registration.ticket_download', form) if ticket else None})

    owner_link = Abstract.person_links.any(AbstractPersonLink.person.has(EventPerson.user_id == user.id))
    abstract_query = Abstract.query.filter(~Abstract.is_deleted, or_(Abstract.submitter_id == user.id, owner_link))
    abstract_query = abstract_query.options(db.joinedload(Abstract.event), db.selectinload(
        Abstract.person_links).joinedload(AbstractPersonLink.person).joinedload(EventPerson.user))
    submissions = [{
        'id': abstract.id, 'event_id': abstract.event_id, 'event_title': abstract.event.title,
        'title': abstract.title, 'number': abstract.friendly_id, 'state': abstract.state.name,
        'state_label': ABSTRACT_LABELS[abstract.state.name],
        'url': url_for('abstracts.display_abstract', abstract, management=False),
        'can_edit': bool(not abstract.event.is_locked and abstract.can_edit(user))
    } for abstract in abstract_query.order_by(Abstract.id.desc())
        if event_visible(abstract.event, user, 'abstracts') and abstract.user_owns(user) and abstract.can_access(user)]

    reviews = []
    candidates = get_events_with_abstract_reviewer_convener(user)
    for event in Event.query.filter(Event.id.in_(candidates)).order_by(Event.id.desc()):
        if 'abstract_reviewer' not in candidates[event.id] or not event_visible(event, user, 'abstracts'):
            continue
        tracks = []
        for track, counts in get_track_reviewer_abstract_counts(event, user).items():
            if not track.can_review_abstracts(user):
                continue
            count = counts['unreviewed']
            if count:
                tracks.append({'id': track.id, 'title': track.title, 'count': count,
                               'url': url_for('abstracts.display_reviewable_track_abstracts', track)})
        if tracks:
            reviews.append({'event_id': event.id, 'event_title': event.title, 'tracks': tracks,
                            'url': url_for('abstracts.display_reviewable_tracks', event_id=event.id)})
    # shortcut: loads the user's own records; add server pagination when personal histories become large.
    return {'registrations': registrations, 'submissions': submissions, 'reviews': reviews}
