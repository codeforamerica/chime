from logging import getLogger
logger = getLogger('chime.publish')

from os import mkdir
from os.path import join
from tempfile import mkdtemp
from urlparse import urljoin
from shutil import rmtree
from io import BytesIO

from flask import Blueprint, Flask
from logging import getLogger, DEBUG

from .functions import process_local_commit

def announce_commit(base_href, repo, commit_ref):
    '''
    '''
    build_url = urljoin(base_href, '/checkouts/{}.zip'.format(commit_ref))
    
    raise Exception(build_url)

def retrieve_commit_checkout(running_dir, repo, commit_ref):
    '''
    '''
    logger.debug('Retrieve commit {}'.format(commit_ref))
    
    try:
        working_dir = mkdtemp()
        archive_path = join(working_dir, 'archive.zip')
        
        with open(archive_path, 'w') as file:
            repo.archive(file, commit_ref, format='zip')
        
        with open(archive_path, 'r') as file:
            bytes = BytesIO(file.read())
        
        return bytes
        
    except Exception as e:
        print e
        logger.warning(e)

    finally:
        rmtree(working_dir)

def release_commit(running_dir, repo, commit_ref):
    '''
    '''
    logger.debug('Release commit {}'.format(commit_ref))
    
    try:
        working_dir = mkdtemp()
        archive_path = join(working_dir, 'archive.zip')
        
        with open(archive_path, 'w') as file:
            repo.archive(file, commit_ref, format='zip')
        
        zip = process_local_commit(archive_path)
        extract_dir = join(running_dir, 'master')
        
        try:
            mkdir(extract_dir)
        except OSError:
            pass

        logger.debug('Extracting zip archive to {}'.format(extract_dir))
        zip.extractall(extract_dir)
        
    except Exception as e:
        print e
        logger.warning(e)

    finally:
        rmtree(working_dir)

publish = Blueprint('chime.publish', __name__, template_folder='templates')

def create_app(environ):
    app = Flask(__name__, static_folder='static')
    app.secret_key = 'boop'

    # attach routes and custom error pages here
    app.register_blueprint(publish)

    @app.before_first_request
    def before_first_request():
        '''
        '''
        if app.debug:
            getLogger('chime.publish').setLevel(DEBUG)

    return app

from . import views
