from setuptools import setup
import versioneer

setup(
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    name='ms-orm',
    packages=['msorm'],
    url='https://github.com/emillynge/ms-orm',
    install_requires=[
        'keyring>=10.2',
        'aioxmlrpc',
        'aiohttp',
        'json_tricks'
    ],
    license='Apache',
    author='emillynge',
    author_email='emillynge24@gmail.com',
    description='A library for fetching uselful data from DDS medlems-service using ORM'
)
