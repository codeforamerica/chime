from setuptools import setup

setup(
    name = 'Chime',
    version = '0.0.0',
    url = 'https://github.com/chimecms/chime',
    author = 'Code for America',
    description = 'Hashing out some ideas about Git, Jekyll, language, and content management',
    packages = ['chime', 'chime.httpd', 'chime.publish', 'chime.instantiation'],
    package_data = {
        'chime': ['templates/*.html', 'templates/macros/*.html', 'templates/includes/*.html']
    },
    install_requires = [],
    entry_points = dict(
        console_scripts = []
    )
)
