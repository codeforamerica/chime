from logging import getLogger
logger = getLogger('bizarro.publish.functions')

from urlparse import urlparse
from os.path import dirname, basename, join, exists
from tempfile import mkdtemp
from zipfile import ZipFile
from shutil import rmtree
from io import BytesIO

from requests import get

from ..jekyll_functions import build_jekyll_site

def process_commit(commit):

    try:
        working_dir = mkdtemp()
        checkout_dir = extract_commit(working_dir, commit['url'], commit['sha'])
        build_jekyll_site(checkout_dir)

    except Exception as e:
        logger.warning(e)

    finally:
        rmtree(working_dir)

def extract_commit(unzip_dir, commit_url, commit_sha):
    #
    # Convert commit URL to downloadable archive URL.
    # Old: https://github.com/codeforamerica/ceviche-starter/commit/93250f1308daef66c5809fe87fc242d092e61db7
    # New: https://github.com/codeforamerica/ceviche-starter/archive/93250f1308daef66c5809fe87fc242d092e61db7.zip
    #
    _, _, path, _, _, _ = urlparse(commit_url)
    parts = dict(repo=dirname(dirname(path)), sha=commit_sha)
    tarball_url = 'https://github.com{repo}/archive/{sha}.zip'.format(**parts)
    
    got = get(tarball_url)
    zip = ZipFile(BytesIO(got.content), 'r')
    zip.extractall(unzip_dir)
    
    #
    # Check for a specially-named subdirectory made by Github.
    # ceviche-starter-93250f1308daef66c5809fe87fc242d092e61db7
    #
    subdirectory = '{}-{}'.format(basename(parts['repo']), commit_sha)
    checkout_dir = join(unzip_dir, subdirectory)
    
    if not exists(checkout_dir):
        checkout_dir = unzip_dir
    
    return checkout_dir
