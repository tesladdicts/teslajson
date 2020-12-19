from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path
import re

# Version defined in teslajson.py ``` __version__ = 'foo' '''
def get_version():
    VERSIONFILE = 'teslajson.py'
    initfile_lines = open(VERSIONFILE, 'rt').readlines()
    VSRE = r"^\s*__version__ = ['\"]([^'\"]*)['\"]"
    for line in initfile_lines:
        mo = re.search(VSRE, line, re.M)
        if mo:
            return mo.group(1)
    raise RuntimeError('Unable to find version string in %s.' % (VERSIONFILE,))

setup(name='teslajson',
      version=get_version(),
      description='Manipulate tesla API, send commands, poll data',
      url='https://github.com/SethRobertson/teslajson',
      py_modules=['teslajson','tesla_parselib'],
      scripts=['tesla_poller','tesla-parser.py','poller_rpc.py'],
      author='Greg Glockner, Seth Robertson, Pedro Mendes',
      license='MIT',
      install_requires=['pytz','psycopg2-binary','psycopg2']
      )
