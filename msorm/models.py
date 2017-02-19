from .login import Requester
import builtins
import re

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


class ModelBase:
    model_name = None
    def __init__(self, requester: Requester, model_name=None):
        self.name = model_name or self.model_name
        self.req = requester

    async def execute_kw(self, *args, **kwargs):
        return await self.req.execute_kw(self.name, *args, **kwargs)

    async def get_fields(self):
        return await self.execute_kw('fields_get', [], attributes=['string', 'help', 'type'])

    async def get_entries(self, *fields, filters=tuple(), **kwargs):
        _filters = Filter.make_filters(filters)
        kwargs['fields'] = fields
        return await self.execute_kw('search_read', [_filters], **kwargs)


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