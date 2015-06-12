from setuptools import setup
from os.path import join, dirname
import sys

#with open(join(dirname(__file__), 'openaddr', 'VERSION')) as file:
#    version = file.read().strip()

setup(
    name = 'Chime',
    version = '0.0.0',
    url = 'https://github.com/chimecms/chime',
    author = 'Code for America',
    description = 'Hashing out some ideas about Git, Jekyll, language, and content management',
    packages = ['chime', 'chime.httpd', 'chime.publish', 'chime.instantiation'],
    package_data = {
        'chime': []
    },
    install_requires = [],
    entry_points = dict(
        console_scripts = []
    )
)
