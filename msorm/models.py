import logging
from collections import UserDict, namedtuple
import sys
from typing import List, Dict, Any

from aioxmlrpc.client import Fault

from .login import Requester
import builtins
import re
import functools


class need_properties:
    def __init__(self, *property_names):
        self.props = property_names

    def __call__(_self, method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            if not all(
                    hasattr(self, prop) and getattr(self, prop) is not None
                    for prop in _self.props):
                raise ValueError(
                    f'One or more propersites is missing or unset: {props}')
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
    permitted_fields = ['id']
    default_fields = ['id']

    def __init__(self,
                 requester: Requester,
                 model_name=None,
                 entries: List[Dict[str, Any]]=None):
        self.name = model_name or self.model_name
        self.req = requester
        if entries:
            self.entry_type = namedtuple(f'{self.__class__.__name__}Entry', entries[0].keys())
            entries = entries or dict()
            super().__init__((i, self.entry_type(*entry))
                             for i, entry in entries.items())
        else:
            self.entry_type = None

    def _set(self, entry_list, fields, prev_entries):
        self.entry_type = namedtuple(self.entry_type.__name__,
                                     [*self.entry_type._fields, *fields])

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
        try:
            return await self.req.execute_kw(self.name, *args, **kwargs)
        except Fault as exc:
            sys.stderr.write(exc.faultString)
            raise

    async def get_fields(self):
        fields = await self.execute_kw(
            'fields_get', [], attributes=['string', 'help', 'type'])

        return dict((k, fields[k]) for k in sorted(fields))

    @classmethod
    async def for_entries_request(cls,
                                  requester,
                                  *fields,
                                  ids=tuple(),
                                  filters=tuple(),
                                  model_name=None,
                                  **kwargs):
        return cls(
            requester,
            model_name=model_name,
            entries=(await cls(requester).get_entries(*fields, ids=ids, filters=filters, **kwargs)),
        )

    async def get_entries(self,
                          *fields,
                          ids=tuple(),
                          filters=tuple(),
                          **kwargs):
        if not ids and not filters:
            raise ValueError(f'"ids" and "filters" cannot both be None')

        action = 'search_read'
        args = list()
        if ids:
            args.append(ids)
            action = 'read'

        if filters:
            args.append(Filter.make_filters(filters))

        if fields is None:
            fields = self.permitted_fields
        elif not fields:
            fields = self.default_fields

        kwargs['fields'] = fields
        res = await self.execute_kw(action, args, **kwargs)
        logging.debug(f'Fetched {len(res)} {self.__class__.__name__} entries')
        return res

    async def set_with_filter(self, filters):
        self.ids = [
            d['id'] for d in (await self.get_entries('id', filters=filters))
        ]
        return self

    def set_with_ids(self, ids):
        self.ids = ids
        return self

    @classmethod
    def _from_ids(cls, instance: "ModelBase", ids):
        return cls(
            requester=instance.req, model_name=instance.model_name, ids=ids)

    @need_ids
    def subset_from_filter(self, filter):
        pass


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
        return await self.req.execute_kw(
            model_name,
            'fields_get', [],
            attributes=['string', 'help', 'type'])

    async def models_info(self):
        return await self.execute_kw(
            'search_read', [], fields=['display_name', 'model', 'info'])


class Event(ModelBase):
    model_name = 'event.event'

    registration_ids: List[int]
    name: str


class Member(ModelBase):
    model_name = 'member.member'
    permitted_fields = [
        '__last_update', 'active', 'active_function_ids',
        'active_membership_ids', 'active_profile_ids', 'address_co', 'age',
        'bank_ids', 'birthdate', 'birthdate_short', 'bm_id', 'bm_sso_id',
        'bmhash', 'bmref', 'calendar_last_notif_ack', 'category_id',
        'child_ids', 'city', 'ckr_check_ids', 'color', 'comment',
        'commercial_partner_id', 'company_id', 'complete_address',
        'contact_address', 'context_age', 'contract_ids', 'country_id',
        'create_date', 'create_uid', 'credit', 'credit_limit', 'customer',
        'date', 'date_localization', 'debit', 'debit_limit', 'display_name',
        'ean13', 'edit_birthdate', 'edit_member_number', 'edit_name',
        'edit_restricted_fields', 'email', 'employee',
        'event_registration_ids', 'externalid', 'fax', 'firstname', 'function',
        'function_ids', 'functions_text', 'gender', 'has_image', 'id', 'image',
        'image_medium', 'image_small', 'import_status', 'is_active_leader',
        'is_company', 'lang', 'last_contact_confirm', 'last_import',
        'last_reconciliation_date', 'lastname', 'leader_function_ids',
        'locking_ckr_check_ids', 'locks_name_ids', 'meeting_count',
        'meeting_ids', 'member_id', 'member_number', 'membership_ids',
        'message_follower_ids', 'message_ids', 'message_is_follower',
        'message_last_post', 'message_summary', 'message_unread', 'mobile',
        'mobile_clean', 'municipality_id', 'name', 'notify_email',
        'opportunity_count', 'opportunity_ids', 'opt_out', 'organization_id',
        'parent_id', 'parent_name', 'parish_id', 'partner_id',
        'partner_latitude', 'partner_longitude', 'payer_for_profile_ids',
        'phone', 'phone_combo', 'phonecall_count', 'phonecall_ids',
        'profile_ids', 'property_account_payable', 'property_account_position',
        'property_account_receivable', 'property_payment_term',
        'property_product_pricelist', 'property_stock_customer',
        'property_stock_supplier', 'property_supplier_payment_term', 'ref',
        'ref_companies', 'registered', 'relation_all_ids',
        'relation_all_member_ids', 'relation_count', 'relation_ids',
        'relation_partner_list', 'relation_primary_member_ids',
        'sale_order_count', 'school', 'school_class_letter',
        'school_class_number', 'school_start_year', 'search_relation_date',
        'search_relation_id', 'search_relation_partner_category_id',
        'search_relation_partner_id', 'section_id', 'self',
        'self_relation_partner_list', 'signup_expiration', 'signup_token',
        'signup_type', 'signup_url', 'signup_valid', 'speaker', 'state_id',
        'street', 'street2', 'street_floor', 'street_letter', 'street_name',
        'street_number', 'street_placement', 'supplier', 'task_count',
        'task_ids', 'title', 'type', 'tz', 'tz_offset', 'use_parent_address',
        'user_full_ids', 'user_id', 'user_ids', 'user_read_ids', 'vat',
        'vat_subjected', 'website', 'website_description',
        'website_meta_description', 'website_meta_keywords',
        'website_meta_title', 'website_published', 'website_short_description',
        'write_date', 'write_uid', 'zip'
    ]
    default_fields = [
        'primary_membership_organization_id',
        'birthdate',
        'gender',
        'member_id',
        'organization_structure_parent_id',
        'active_profile_ids',
    ]



class Profile(ModelBase):
    model_name = 'member.profile'
    permitted_fields = [
        '__last_update', 'account_invoice_line_ids', 'active',
        'active_function_ids', 'active_functions_in_profile',
        'active_membership_ids', 'active_memberships_in_profile',
        'active_profile_ids', 'address_co', 'age', 'all_functions_in_profile',
        'all_memberships_in_profile', 'bank_ids', 'birthdate',
        'birthdate_short', 'bm_id', 'bm_sso_id', 'bmhash', 'bmref',
        'calendar_last_notif_ack', 'can_delete', 'can_edit', 'can_expense',
        'can_full_all', 'category_id', 'child_ids', 'city', 'ckr_check_ids',
        'color', 'comment', 'commercial_partner_id', 'company_id',
        'complete_address', 'contact_address', 'context_age', 'contract_ids',
        'country_id', 'create_date', 'create_uid', 'credit', 'credit_limit',
        'customer', 'date', 'date_localization', 'debit', 'debit_limit',
        'diseases', 'display_name', 'ean13', 'edit_birthdate',
        'edit_member_number', 'edit_name', 'edit_organization_id',
        'edit_restricted_fields', 'email', 'employee',
        'event_registration_ids', 'externalid', 'fax', 'firstname', 'function',
        'function_ids', 'functions_text', 'gender', 'handicap', 'has_image',
        'help_info', 'id', 'image', 'image_medium', 'image_small',
        'import_status', 'is_active_leader', 'is_company', 'lang',
        'last_contact_confirm', 'last_import', 'last_reconciliation_date',
        'lastname', 'leader_function_ids', 'locking_ckr_check_ids',
        'locks_name_ids', 'meeting_count', 'meeting_ids', 'member_id',
        'member_number', 'membership_ids', 'message_follower_ids',
        'message_ids', 'message_is_follower', 'message_last_post',
        'message_summary', 'message_unread', 'mobile', 'mobile_clean',
        'municipality_id', 'name', 'notify_email', 'opportunity_count',
        'opportunity_ids', 'opt_out', 'organization_id',
        'organization_structure_parent_id', 'organization_type_id',
        'other_info', 'parent_id', 'parent_name', 'parish_id', 'partner_id',
        'partner_latitude', 'partner_longitude', 'partner_payer_id',
        'payer_for_profile_ids', 'payer_for_profile_this_organization_ids',
        'pbmhash', 'pbmref', 'permission_photo', 'phone', 'phone_combo',
        'phonecall_count', 'phonecall_ids', 'plast_import',
        'preliminary_organization_id', 'primary_membership_organization_id',
        'profile_ids', 'promotion_ids', 'property_account_payable',
        'property_account_position', 'property_account_receivable',
        'property_payment_term', 'property_product_pricelist',
        'property_stock_customer', 'property_stock_supplier',
        'property_supplier_payment_term', 'ref', 'ref_companies', 'registered',
        'relation_all_ids', 'relation_all_member_ids', 'relation_count',
        'relation_ids', 'relation_partner_list', 'relation_primary_member_ids',
        'relative_for_profile_id', 'relative_member_id', 'relative_type_id',
        'sale_order_count', 'school', 'school_class_letter',
        'school_class_number', 'school_start_year', 'scout_name',
        'search_relation_date', 'search_relation_id',
        'search_relation_partner_category_id', 'search_relation_partner_id',
        'section_id', 'self', 'self_relation_partner_list',
        'signup_expiration', 'signup_token', 'signup_type', 'signup_url',
        'signup_valid', 'speaker', 'state', 'state_id', 'stored_partner_id',
        'street', 'street2', 'street_floor', 'street_letter', 'street_name',
        'street_number', 'street_placement', 'subscription_card',
        'subscription_fee_date_end', 'subscription_fee_date_start',
        'subscription_fee_has_draft_lines', 'subscription_fee_receivable',
        'subscription_last_charged_end_date', 'subscription_last_warning_date',
        'subscription_product_id', 'subscription_transaction', 'supplier',
        'task_count', 'task_ids', 'title', 'type', 'tz', 'tz_offset',
        'use_parent_address', 'user_full_ids', 'user_id', 'user_ids',
        'user_read_ids', 'vat', 'vat_subjected', 'waitinglist_date', 'website',
        'website_description', 'website_message_ids',
        'website_meta_description', 'website_meta_keywords',
        'website_meta_title', 'website_published', 'website_short_description',
        'write_date', 'write_uid', 'zip'
    ]

    default_fields = [
        'primary_membership_organization_id',
        'birthdate',
        'gender',
        'member_id',
        'member_number',
        'organization_structure_parent_id',
    ]

class Membership(ModelBase):
    model_name = 'member.membership'


class Registration(ModelBase):
    model_name = 'event.registration'

class Question(ModelBase):
    model_name = 'event.question'

class Answer(ModelBase):
    model_name = 'event.question.response'
    default_fields = [
        'event_registration_id',
        'event_question_id',
        'event_question_option_id',
        'response',
    ]