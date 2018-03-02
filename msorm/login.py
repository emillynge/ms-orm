from abc import ABC, abstractmethod
from xmlrpc.client import ServerProxy

import functools
import sys
from collections import MutableMapping

from getpass import getpass
import pathlib
from pathlib import Path
import os
import keyring
import xmlrpc
import asyncio
from aioxmlrpc.client import ServerProxy as AioServerProxy
from configparser import ConfigParser

from typing import Any, Union

CONFIG_DIR = pathlib.Path(os.environ.get('MS_CONFIG_DIR', default='~/.ms'))
from pprint import pprint

# bug with IDEA makes the IDE think this class is not part of the configparser module
class SectionProxy(MutableMapping):
    """A proxy for a single section from a parser."""

    def __init__(self, parser: ConfigParser, name):
        """Creates a view on a section of the specified `name` in `parser`."""
        self._parser = parser
        self._name = name
        for conv in parser.converters:
            key = 'get' + conv
            getter = functools.partial(self.get, _impl=getattr(parser, key))
            setattr(self, key, getter)

    def __repr__(self):
        return '<Section: {}>'.format(self._name)

    def __getitem__(self, key):
        if not self._parser.has_option(self._name, key):
            raise KeyError(key)
        return self._parser.get(self._name, key)

    def __setitem__(self, key, value):
        self._parser._validate_value_types(option=key, value=value)
        return self._parser.set(self._name, key, value)

    def __delitem__(self, key):
        if not (self._parser.has_option(self._name, key) and
                    self._parser.remove_option(self._name, key)):
            raise KeyError(key)

    def __contains__(self, key):
        return self._parser.has_option(self._name, key)

    def __len__(self):
        return len(self._options())

    def __iter__(self):
        return self._options().__iter__()

    def _options(self):
        if self._name != self._parser.default_section:
            return self._parser.options(self._name)
        else:
            return self._parser.defaults()

    @property
    def parser(self):
        # The parser object of the proxy is read-only.
        return self._parser

    @property
    def name(self):
        # The name of the section on a proxy is read-only.
        return self._name

    def get(self, option, fallback=None, *, raw=False, vars=None,
            _impl=None, **kwargs):
        """Get an option value.

        Unless `fallback` is provided, `None` will be returned if the option
        is not found.

        """
        # If `_impl` is provided, it should be a getter method on the parser
        # object that provides the desired type conversion.
        if not _impl:
            _impl = self._parser.get
        return _impl(self._name, option, raw=raw, vars=vars,
                     fallback=fallback, **kwargs)


class Storage(SectionProxy):
    def __init__(self, db_path: Path, *args, **kwargs):
        self.db_path = db_path
        super().__init__(*args, **kwargs)

    def set(self, key, value):
        self[key] = value

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        with self.db_path.open('w') as fp:
            self._parser.write(fp)


class CredentialsBase(ABC):
    @abstractmethod
    @property
    def mno(self) -> int:
        pass


    @abstractmethod
    @property
    def db(self) -> str:
        pass

    @abstractmethod
    @property
    def domain(self) -> str:
        pass


    @abstractmethod
    @property
    def dbpass(self) -> str:
        pass

    @abstractmethod
    @property
    def uid(self) -> str:
        pass

    @abstractmethod
    @uid.setter
    def uid(self, uid: Union[str, type(None)]):
        pass

    @abstractmethod
    def get_or_set(self, key, prompt: str, passw=False, force=False) -> Any:
        pass

    @abstractmethod
    def clear(self, key):
        pass


class Credentials(CredentialsBase):
    def clear(self, key):
        if key in self._passwords:
            self._passwords.pop(key)

    def __init__(self, ms_conf_dir: Path=None, **conf_overrides):
        self.ms_conf_dir = (ms_conf_dir or CONFIG_DIR).expanduser()
        self._config: ConfigParser = None
        self.db_path = self.ms_conf_dir.joinpath(f'databases.ini')
        self._storage = None
        self.conf_overrides = conf_overrides
        self._passwords = dict()

    def ensure_conf_dir(self):
        if self.ms_conf_dir.exists():
            if not self.ms_conf_dir.is_dir():
                raise ValueError(f'{self.ms_conf_dir} is a file. It should be a folder!')

        else:
            os.mkdir(self.ms_conf_dir.expanduser())

    def init_storage(self):
        self.ensure_conf_dir()
        self._config = ConfigParser()
        if self.db_path.exists():
            with self.db_path.open('r') as fp:
                self._config.read_file(fp)

        if not self.config.has_section('default'):
            domain = self.conf_overrides.get('domain', None) or input('Enter domain for MedlemsService: ').strip(' \'"')
            db = self.conf_overrides.get('db', None) or self._choose_db(domain)

            self.config.add_section('default')
            self.config['default']['db'] = db
            self.config['default']['domain'] = domain

        else:
            self.config['default']['db'] = self.conf_overrides.get('db', None) or self.config['default']['db']
            self.config['default']['domain'] = self.conf_overrides.get('domain', None) or self.config['default']['domain']


        db = self.config['default']['db']
        if not self.config.has_section(db):
            self.config.add_section(db)

        self._storage = Storage(self.db_path, self.config, db)

        for key, val in self.conf_overrides.items():
            self._storage.set(key, val)

        self._storage['domain'] = self.config['default']['domain']

    def _choose_db(self, domain=None):
        dblist = list(self.get_db_list(domain=domain))
        print(f'{"Databases:":<20}')
        for i, db in enumerate(dblist):
            print(f'{" "*10}{i:<3}{db}')

        db_i = -1
        while 0 > db_i or db_i >= len(dblist):
            db_i = int(input('Choose database: '))

        db = dblist[db_i]
        print(f'Active database: "{db}"')
        return db

    @property
    def db(self):
        return self.storage.name

    @property
    def config(self) -> ConfigParser:
        if not self._config:
            self.init_storage()
        return self._config

    @property
    def storage(self) -> Storage:
        if not self._storage:
            self.init_storage()
        return self._storage

    def get_or_set(self, key, prompt: str, passw=False, force=False):
        if passw:
            if key not in self._passwords or force:
                user = self.mno
                pw = keyring.get_password(f'ms-{self.db}-{key}', user)
                if pw is None or force:
                    pw = getpass(prompt.format(user=user, key=key, db=self.db))
                    keyring.set_password(f'ms-{self.db}-{key}', user, pw)
                self._passwords[key] = pw
            return self._passwords[key]

        if key not in self.storage or force:
            self.storage[key] = input(prompt.format(key=key, db=self.db))
        return self.storage[key]

    @property
    def mno(self):
        return self.get_or_set(key='mno', prompt='Enter Member Number: ')

    @property
    def domain(self):
        return self.get_or_set(key='domain', prompt='Enter domain name for MedlemsService (e.g. dds-beta.steingabelgaard.dk): ')

    @property
    def dbpass(self):
        return self.get_or_set(passw=True, key='dbpass', prompt='Enter code for {user}@{db}: ')

    def get_db_list(self, domain=None):
        domain = domain or self.domain
        return ServerProxy(f'https://{domain}/xmlrpc/2/db').list()

    @property
    def uid(self):
        if 'uid' in self.storage:
            return int(self.storage['uid'])
        return None

    @uid.setter
    def uid(self, val):
        self.storage['uid'] = str(val)


class Requester:
    def __init__(self, credentials: CredentialsBase):
        self.cred = credentials
        self.common = AioServerProxy(f'https://{self.cred.domain}/xmlrpc/2/common')
        self.models = AioServerProxy(f'https://{self.cred.domain}/xmlrpc/2/object')

    async def execute_kw(self, *args, **kwargs):
        try:
            return await self.models.execute_kw(self.cred.db, self.cred.uid, self.cred.dbpass, *args, kwargs)
        except xmlrpc.client.Fault as exc:
            if exc.faultCode == 3:
                print('Credentials ot working. trying re-login')
            else:
                raise

        await self.login(force=True)
        return self.models.execute_kw(self.cred.db, self.cred.uid, self.cred.dbpass, *args, kwargs)

    async def login(self, force=False):
        if self.cred.uid is not None and not force:
            return

        uid = await self.common.authenticate(self.cred.db, self.cred.mno, self.cred.dbpass, {})
        if uid is not False:
            self.cred.uid = uid
            return

        try:
            self.cred.get_or_set('dbpass',  'login failed for {user}@{db}. Reenter password', passw=True, force=True)
        except KeyboardInterrupt:
            try:
                i = int(input("""
options:
[1] change user
[2] change db
[3] exit 
choice: """))
            except ValueError as exc:
                raise ValueError('Only integers allowed...') from exc

            if i == 1:
                self.cred.get_or_set('mno', 'Enter new MemberNumber for {db}: ', force=True)
            elif i == 3:
                sys.exit()
            else:
                raise NotImplementedError()
            self.cred.clear('dbpass')
        await self.login()

    async def __aenter__(self):
        await self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    async def __aexit__(self, *args):
        return self.__exit__(*args)

    def close(self):
        self.common.close()
        self.models.close()


async def get_dblist(credentials):
    dblist = await AioServerProxy(f'https://{credentials.domain}/xmlrpc/2/db').list()
    print(dblist)


async def main(loop):
    models = Requester(Credentials())
    for m in (await models.get_model_fields('event.event')):
        pprint(m)
    models.close()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))