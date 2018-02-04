import asyncio
from collections import defaultdict
from enum import IntEnum
from itertools import chain

from .login import Credentials, Requester
from .models import Event, Filter, Registration, Profile, Answer, Question
import logging

class States(IntEnum):
    open = 0  # Bekræftet
    moved = 1  # Flyttet til andet kursus
    cancel = 2  # Afmeldt
    manual = 3  # Afventer godkendelse
    waitinglist = 4
    annul = 5  # Annuleret
    draft = 6   # kladde - endnu ikke synlig i tilmeldingslisten


async def get_signup_data(main_event_code, requester: Requester, other_event_codes, questions_of_interest: dict,
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
    prev_course_filter += Filter("state") == "open"

    print('fetching answers, profiles and prev courses')
    answers, profiles, prev_course_registrations = await asyncio.gather(
        answer_req.get_entries(filters=answer_filt),
        profile_req.get_entries(filters=profile_filter),
        reg_req.get_entries('event_id', 'member_id', filters=prev_course_filter),
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

    getattr(States, 'annul')
    mid2reg = dict()
    for r in registrations:
        if not r['member_id']:
            continue

        mid = r['member_id'][0]
        state = getattr(States, r['state'])
        if mid in mid2reg:
            state = getattr(States, r['state'])
            existing_state = getattr(States, mid2reg[mid]['state'])
            if state > existing_state:
                continue
            if state == existing_state:
                id = r['id']
                existing_id = mid2reg[mid]['id']
                if id < existing_id:
                    continue

        mid2reg[mid] = r

    mid2prev_courses = defaultdict(list)
    for pc in prev_course_registrations:
        mid2prev_courses[pc['member_id'][0]].append(eid2event_code[pc['event_id'][0]])


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
                    )

        reg = mid2reg[mid]
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