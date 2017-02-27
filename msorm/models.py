from collections import UserDict, namedtuple

from .login import Requester
import builtins
import re
import functools
from itertools

class need_properties:
    def __init__(self, *property_names):
        self.props = property_names

    def __call__(_self, method):

        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            if not all(hasattr(self, prop) and getattr(self, prop) is not None for prop in _self.props):
                raise ValueError(f'One or more propersites is missing or unset: {props}')
            return method(self, *args, **kwargs)
        return wrapper

need_ids = need_properties('ids')


class Filter(list):
    typecasts = re.compile('([a-z]+)\((.+)\)')

    def __init__(self, field):
        self.field = field
        self.closed = False

        super().__init__()

    def __append_filter(self, operator, value, closes=True):
        if self.closed:
            raise ValueError('Cannot finalize filter. already finalized')
        self.append([self.field, operator, value])

        if closes:
            self.closed = True
        return self

    def In(self, *other):
        return self.__append_filter('in', other)

    def __contains__(self, item):
        return self.__append_filter('in', item)

    def __le__(self, other):
        return self.__append_filter('<=', other)

    def __lt__(self, other):
        return self.__append_filter('<', other)

    def __ge__(self, other):
        return self.__append_filter('>=', other)

    def __gt__(self, other):
        return self.__append_filter('>', other)

    def __eq__(self, other):
        return self.__append_filter('=', other)

    def __add__(self, other):
        if isinstance(other, str):
            other = Filter(other)
        other.extend(self)
        return other

    @classmethod
    def make_filters(cls, filters, **kwfilters):

        _filters = list(filters)
        for field, filt in kwfilters.items():
            if isinstance(filt, str):
                for f in filt.split('&&'):
                    if not f:
                        continue
                    op, val = f.strip(' ').split(' ')
                    tc = cls.typecasts.findall(val)
                    if tc:
                        print(tc)
                        _tc = lambda _val: getattr(builtins, tc[0][0])(_val)
                        val = tc[0][-1]

                    if ',' in val:
                        val = val.split(',')
                        if tc:
                            val = [_tc(v) for v in val]
                    elif tc:
                        val = _tc(val)

                    print(val)
                    _filters.append([field, op, val])
        return _filters


class ModelBase(UserDict):
    model_name = None
    def __init__(self, requester: Requester, model_name=None, entries: dict=None):
        self.name = model_name or self.model_name
        self.req = requester
        fields = next(iter(entries.values()))._fields if entries else tuple()
        self.entry_type = namedtuple(f'{self.__class__.__name__}Entry', fields)
        entries = entries or dict()
        super().__init__((i, self.entry_type(*entry)) for i, entry in entries.items())

    def _set(self, entry_list, fields, prev_entries):
        self.entry_type = namedtuple(self.entry_type.__name__, [*self.entry_type._fields, *fields])
        def get_values(ent):
            for field in fields:
                yield ent[field]

        for entry in entry_list:
            i = entry.pop('id')
            self[i] = self.entry_type(*self[i], *get_values(entry))

    @property
    def ids(self):
        return list(self.ids)

    async def execute_kw(self, *args, **kwargs):
        return await self.req.execute_kw(self.name, *args, **kwargs)

    async def get_fields(self):
        return await self.execute_kw('fields_get', [], attributes=['string', 'help', 'type'])

    async def get_entries(self, *fields, ids=tuple(), filters=tuple(), **kwargs):
        if not ids or filters:
            raise ValueError(f'"ids" and "filters" cannot both be None')

        args = list()
        if ids:
            args.append(ids)

        if filters:
            args.append(Filter.make_filters(filters))

        kwargs['fields'] = fields
        return await self.execute_kw('search_read', args, **kwargs)

    async def set_with_filter(self, filters):
        self.ids = [d['id'] for d in (await self.get_entries('id', filters=filters))]
        return self

    def set_with_ids(self, ids):
        self.ids = ids
        return self

    @classmethod
    def _from_ids(cls, instance: "ModelBase", ids):
        return cls(requester=instance.req, model_name=instance.model_name, ids=ids)

    @need_ids
    def subset_from_filter(self, filter):
        



def set_name(name):
    def __init__(self, requester):
        self.req = requester
        self.name = name

    def wrapper(klass):
        setattr(klass, '__init__', __init__)
        return klass

    return wrapper


class ModelOverview(ModelBase):
    model_name = 'ir.model'
    async def get_model_fields(self, model_name):
        return await self.req.execute_kw(model_name, 'fields_get', [], attributes=['string', 'help', 'type'])

    async def models_info(self):
        return await self.execute_kw('search_read', [], fields=['display_name', 'model', 'info'])

class Event(ModelBase):
    model_name = 'event.event'

class Member(ModelBase):
    model_name = 'member.member'

class Registration(ModelBase):
    model_name = 'event.registration'

