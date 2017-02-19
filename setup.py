from setuptools import setup

setup(
    name='ms-orm',
    version='1.0.0',
    packages=['msorm'],
    url='https://github.com/emillynge/ms-orm',
    install_requires=[
        'keyring>=10.2',
        'aioxmlrpc',
        'aiohttp',

    ],
    license='Apache',
    author='emillynge',
    author_email='emillynge24@gmail.com',
    description='A library for fetching uselful data from DDS medlems-service using ORM'
)
