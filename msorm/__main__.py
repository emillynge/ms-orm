from collections import defaultdict
from itertools import chain
from typing import NamedTuple, List

import json_tricks
from aioxmlrpc.client import Fault

from msorm.scripts import get_signup_data
from .login import Credentials, Requester
from .models import Event, Filter, Member, Registration, Profile, ModelBase, ModelOverview, Membership, Answer, Question
from pprint import pprint
import asyncio
import pandas as pd

class EventResult(NamedTuple):
    id: str
    name: str
    registration_ids: List[str]
    event_question_ids: List[str]


event_codes = """13621
13622
13623
13624
13631
13632
13633
13634
13635
13641
13642
13643
13644
13645
13651
13652
13653
13654
13655
14605
14620
14621
14622
14623
14630
14631
14632
14633
14634
14635
14640
14641
14642
14643
14644
14645
14650
14651
14652
14653
14654
15501
15502
15503
15504
15511
15512
15513
15514
15515
15516
15521
15522
15523
15524
15525
15531
15532
15533
15534
15535
12630
12631
13610
13611
13612
13613
13614
14610
14611
14612
14613
14614
13660
13661
13662
14660
14661
14662
15541
15542
15561
15611
15612
15613
15614
16601
16602
16603
16604
16605
16501
16502
16503
16504
16505
16511
16512
16513
16514
16515
16516
16521
16522
16523
16524
16525
16531
16532
16533
16534
17601
17602
17603
17604
17605""".split('\n')

main_event_code = '17500'


async def try_request(requester: ModelBase, field, *args, **kwargs):
    try:
        await requester.get_entries(field, *args, **kwargs)
    except Fault:
        return None
    return field


async def find_permitted_fields(requester: ModelBase, fields, *args, **kwargs):
    fields = await asyncio.gather(*(try_request(requester, field, *args, **kwargs) for field in fields))
    return list(sorted(f for f in fields if f is not None))


QUESTIONS_OF_INTEREST = [
    "Vælg kurser",
    "Er du Søspejder?",
]
async def main(*_):
    creds = Credentials()
    async with Requester(creds) as req:
        signups = await get_signup_data(
            '17500',
            requester=req,
            other_event_codes=event_codes,
            questions_of_interest={"Vælg kurser": list(),
                                   "Er du Søspejder?": "Nej"},
            limit=None,
                              )
        with open("/tmp/signups.json", 'w') as fp:
            json_tricks.dump(signups, fp)
        return


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
