from urlparse import urlparse
from re import match
    
def get_redirect(req_path, ref_url):
    '''
    >>> get_redirect('/style.css', 'http://preview.local/tree/foo/view/')
    '/tree/foo/view/style.css'

    >>> get_redirect('/style.css', 'http://preview.local/tree/foo/view/quux.html')
    '/tree/foo/view/style.css'

    >>> get_redirect('/quux/style.css', 'http://preview.local/tree/foo/view/')
    '/tree/foo/view/quux/style.css'
    '''
    _, ref_host, ref_path, _, _, _ = urlparse(ref_url)
    ref_git_preamble_match = match(r'((/[^/]+){3})', ref_path)
    
    return ref_git_preamble_match.group(1) + req_path

def needs_redirect(req_host, req_path, ref_url):
    '''
    Don't redirect when the request and referer hosts don't match:
    >>> needs_redirect('preview.local', '/style.css', 'http://example.com/tree/foo/view/')
    False

    Don't redirect when the referer doesn't appear to include a git path.
    >>> needs_redirect('preview.local', '/style.css', 'http://preview.local/about/')
    False

    Don't redirect when the request path already includes the git preamble.
    >>> needs_redirect('preview.local', '/tree/foo/view/style.css', 'http://preview.local/tree/foo/view/')
    False

    >>> needs_redirect('preview.local', '/', 'http://preview.local/tree/foo/view/')
    True

    >>> needs_redirect('preview.local', '/style.css', 'http://preview.local/tree/foo/view/')
    True

    >>> needs_redirect('preview.local', '/fee/fi/fo/fum/style.css', 'http://preview.local/tree/foo/view/')
    True
    '''
    _, ref_host, ref_path, _, _, _ = urlparse(ref_url)
    
    #
    # Don't redirect when the request and referer hosts don't match.
    #
    if req_host != ref_host:
        return False
    
    ref_git_preamble_match = match(r'(/tree/[^/]+/view/)', ref_path)
    
    #
    # Don't redirect when the referer doesn't appear to include a git path.
    #
    if not ref_git_preamble_match:
        return False
    
    #
    # Don't redirect when the request path already includes the git preamble.
    #
    if req_path.startswith(ref_git_preamble_match.group(1)):
        return False
    
    return True

if __name__ == '__main__':
    import doctest
    doctest.testmod()
