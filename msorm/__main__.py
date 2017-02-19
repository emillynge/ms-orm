from .login import Credentials, Requester
from .models import Event, Filter, Member
from pprint import pprint
import asyncio

async def main(*_):
    creds = Credentials()
    with Requester(creds) as req:
        print('Example: show basic info for all members you have access to')
        pprint(await Member(req).get_entries('name', 'member_number', filters=Filter('name') > ''))


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))