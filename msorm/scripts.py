import asyncio
from collections import defaultdict
from enum import Enum
from itertools import chain
from operator import itemgetter

from .login import Credentials, Requester
from .models import Event, Filter, Registration, Profile, Answer, Question
import logging

class State(Enum):
    CONFIRMED = "open"      # Bekræftet
    MOVED = "moved"         # Flyttet til andet kursus
    CANCELLED = "cancel"    # Afmeldt
    AWAITING = "manual"     # Afventer godkendelse
    WAITLIST = "waitinglist"# På venteliste
    REJECTED = "annul"      # Annuleret
    DRAFTED = "draft"       # kladde - endnu ikke synlig i tilmeldingslisten
    DIDNOTFINISH = "notdone"# Ikke gennemført (der menes sikker at kurset ikke blev gennemført)
    DIDNOTATTEND = "noshow" # Ikke mødt op  (der menes sikker at man ikke var der til kursusstart)

async def get_signup_data(main_event_code,
                          requester: Requester,
                          other_event_codes,
                          questions_of_interest: dict,
                          limit=None):
    logging.debug('Example: show basic info for all members you have access to')
    event_req = Event(requester)
    reg_req = Registration(requester)
    profile_req = Profile(requester)
    answer_req = Answer(requester)
    question_req = Question(requester)

    logging.debug('info loaded, fetching main event')

    main_event = (await event_req.get_entries('registration_ids',
                                              'name',
                                              'event_question_ids',
                                              'event_moveto_ids',
                                              filters=Filter('event_code') == main_event_code))[0]

    logging.debug('fetching events, questions and registrations')
    other_events, questions, registrations = await asyncio.gather(
        event_req.get_entries('registration_ids',
                              'event_code',
                              filters=Filter('event_code').In(*other_event_codes)),
        question_req.get_entries('event_question_option_ids', 'name',
                                 ids=main_event["event_question_ids"]),
        reg_req.get_entries('member_id',
                            'state',
                            ids=main_event["registration_ids"][:limit]),
    )

    relevant_questions = [q for q in questions if q['name'] in questions_of_interest.keys()]

    answer_filt = Filter('event_question_id').In(*(q['id'] for q in relevant_questions))
    answer_filt += Filter('event_id') == main_event["id"]

    profile_filter = Filter('active') == True
    profile_filter += Filter('member_id').In(*(reg['member_id'][0] for reg in registrations if reg['member_id']))

    prev_course_filter = Filter('event_id').In(*(e['id'] for e in other_events))
    prev_course_filter += Filter('member_id').In(*(reg['member_id'][0] for reg in registrations if reg['member_id']))
    prev_course_filter += Filter("state").In(State.CONFIRMED.value, State.WAITLIST.value, State.CANCELLED.value,
                                             State.DIDNOTFINISH.value, State.REJECTED.value, State.DIDNOTATTEND.value)

    print('fetching answers, profiles and prev courses')
    answers, profiles, prev_course_registrations = await asyncio.gather(
        answer_req.get_entries(filters=answer_filt),
        profile_req.get_entries(filters=profile_filter),
        reg_req.get_entries('event_id', 'member_id', 'state', filters=prev_course_filter),
    )


    rid2answers = defaultdict(lambda :defaultdict(list))
    for answer in answers:
        rid = answer['event_registration_id'][0]

        subject = answer['event_question_id'][1]
        if answer['event_question_option_id'] is not False:
            response = answer['event_question_option_id'][1]
            rid2answers[rid][subject].append(response)
        else:
            rid2answers[rid][subject] = answer['response']

    eid2event_code = dict((e['id'], e['event_code']) for e in other_events)

    mid2reg = dict()
    registrations.sort(key=itemgetter('id'), reverse=True)
    for r in registrations:
        if not r['member_id']:
            continue

        mid = r['member_id'][0]
        if mid in mid2reg:
            continue

        mid2reg[mid] = r

    assignable_courses = set(main_event['event_moveto_ids'])

    prev_course_registrations.sort(key=itemgetter('id'), reverse=True)
    seen = set()
    mid2prev_courses = defaultdict(list)
    mid2prev_waitlists = defaultdict(list)
    mid2assigned_courses = defaultdict(list)
    mid2assigned_state = defaultdict(lambda: None)
    for pc in prev_course_registrations:
        event_id = pc['event_id'][0]
        member_id = pc['member_id'][0]
        hash_pair = (member_id, event_id)
        if hash_pair in seen:
            continue

        seen.add(hash_pair)
        state = State(pc['state'])

        if event_id in assignable_courses:
            d = mid2assigned_courses
            if member_id in mid2assigned_state:
                continue

            mid2assigned_state[member_id] = state
            if state not in (State.CONFIRMED, State.DIDNOTFINISH):
                continue

        elif state == State.WAITLIST:
            d = mid2prev_waitlists
        elif state in (State.CONFIRMED, State.DIDNOTFINISH):
            d = mid2prev_courses
        else:
            continue

        d[member_id].append(eid2event_code[event_id])


    signups = dict()
    for profile in profiles:
        mid = profile['member_id'][0]
        gruppe = profile['primary_membership_organization_id']
        if gruppe is False:
            gruppe = None
        else:
            gruppe = gruppe[1]

        division = profile['organization_structure_parent_id']
        if division is False:
            division = None
        else:
            division = division[1]

        data = dict(gender=profile['gender'], birthdate=profile['birthdate'],
                    gruppe=gruppe,
                    division=division,
                    member_number=profile['member_number'],
                    name=profile['member_id'][1],
                    prev_courses=mid2prev_courses[mid],
                    prev_waitlists=mid2prev_waitlists[mid],
                    assigned_courses=mid2assigned_courses[mid]
                    )

        reg = mid2reg[mid]
        state = reg['state']
        if state == State.MOVED.value and mid2assigned_state[mid]:
            state = f'{state}_{mid2assigned_state[mid].value}'

        data.update(state=reg['state'])
        answer = rid2answers[reg['id']]

        for question_name, default_value in questions_of_interest.items():
            if question_name not in answer:
                response = default_value
            else:
                response = answer[question_name]

            if isinstance(default_value, list):
                value = response
            elif isinstance(response, list):
                value = response[0]
            else:
                value = response

            data[question_name] = value


        signups[data['member_number']] = data

    return signups, dict(Event=main_event['id'])