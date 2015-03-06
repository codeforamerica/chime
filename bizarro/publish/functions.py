from logging import getLogger
logger = getLogger('bizarro.publish.functions')

from urlparse import urlparse
from os.path import dirname, basename, join, exists
from tempfile import mkdtemp
from zipfile import ZipFile
from io import BytesIO

from requests import get

def extract_commit(commit_url, commit_sha):
    #
    # Convert commit URL to downloadable archive URL.
    # Old: https://github.com/codeforamerica/ceviche-starter/commit/93250f1308daef66c5809fe87fc242d092e61db7
    # New: https://github.com/codeforamerica/ceviche-starter/archive/93250f1308daef66c5809fe87fc242d092e61db7.zip
    #
    _, _, path, _, _, _ = urlparse(commit_url)
    parts = dict(repo=dirname(dirname(path)), sha=commit_sha)
    tarball_url = 'https://github.com/{repo}/archive/{sha}.zip'.format(**parts)
    
    got = get(tarball_url)
    zip = ZipFile(BytesIO(got.content), 'r')
    
    unzip_dir = mkdtemp()
    zip.extractall(unzip_dir)
    
    # ceviche-starter-93250f1308daef66c5809fe87fc242d092e61db7
    subdirectory = '{}-{}'.format(basename(parts['repo']), commit_sha)
    working_dir = unzip_dir
    
    if exists(join(unzip_dir, subdirectory)):
        working_dir = join(unzip_dir, subdirectory)
    else:
        print 'No', join(unzip_dir, subdirectory)
    
    print working_dir
