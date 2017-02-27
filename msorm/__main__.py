from .login import Credentials, Requester
from .models import Event, Filter, Member, Registration
from pprint import pprint
import asyncio

async def main(*_):
    creds = Credentials()
    with Requester(creds) as req:
        print('Example: show basic info for all members you have access to')
        pprint(await Event(req).get_fields())
        pprint(await Registration(req).get_fields())
        events = Event(req)
        pprint(await Event(req).get_entries('name', 'id', 'member_id'))
        regs = await Registration(req).get_entries('name', 'event_id', 'member_id')
        evnts = await events.get_entries_from_id('name', 'event_code', 'event_question_ids', ids=list(set(d['event_id'][0] for d in regs)))

        questions =

        pprint(evnts)



if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))