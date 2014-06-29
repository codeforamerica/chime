'''
Dump and load complete Jekyll files.

Provides two functions, load_jekyll_doc() and dump_jekyll_doc(), that read and
write YAML-formatted front matter and arbitrary bytes after a "---" separator.

Test with short sample data:

    >>> from StringIO import StringIO
    >>> front, body, file = dict(title=u'Greeting'), 'World: hello.', StringIO()
    >>> dump_jekyll_doc(front, body, file)
    >>> _front, _body = load_jekyll_doc(file)

Input and output are identical:

    >>> _front['title'] == front['title'] and _body == body
    True

Jekyll likes to have the "---" document separator at the top:

    >>> file.seek(0)
    >>> file.read(4) == _marker
    True
'''
import yaml

_marker = "---\n"

def load_jekyll_doc(file):
    ''' Load jekyll front matter and remaining content from a file.
        
        Sample output:
          
          {"title": "Greetings"}, "Hello world."
    '''
    # Check for presence of document separator.
    file.seek(0)
    
    if file.read(len(_marker)) != _marker:
        raise Exception('No front-matter in %s' % getattr(file, 'name', None))
    
    # Seek to just after the initial document separator.
    file.seek(len(_marker))
    
    for token in yaml.scan(file):
        # Look for a token that shows we're about to reach the content.
        if type(token) is yaml.DocumentStartToken:
        
            # Seek to the beginning, and load the complete content.
            file.seek(0)
            chars = file.read().decode('utf8')

            # Load the front matter as a document.
            front_matter = yaml.safe_load(chars[:token.end_mark.index])
            
            # Seek just after the document separator, and get remaining string.
            content = chars[token.end_mark.index + len("\n" + _marker):]
            
            return front_matter, content
    
    raise Exception('Never found a yaml.DocumentStartToken')

def dump_jekyll_doc(front_matter, content, file):
    ''' Dump jekyll front matter and content to a file.
    
        To provide some guarantee of human-editable output, front matter
        is dumped using the newline-preserving block literal form.
        
        Sample output:
        
          ---
          "title": |-
            Greetings
          ---
          Hello world.
    '''
    # Use newline-preserving block literal form.
    # yaml.SafeDumper ensures best unicode output.
    dump_kwargs = dict(Dumper=yaml.SafeDumper, default_flow_style=False,
                       canonical=False, default_style='|', indent=2,
                       allow_unicode=True)
    
    # Write front matter to the start of the file.
    file.seek(0)
    file.truncate()
    file.write(_marker)
    yaml.dump(front_matter, file, **dump_kwargs)

    # Write content to the end of the file.
    file.write(_marker)
    file.write(content.encode('utf8'))

def build_jekyll_site(dirname):
    '''
    '''
    from subprocess import Popen
    
    build = Popen(['jekyll', 'build'], cwd=dirname)
    build.wait()

if __name__ == '__main__':
    import doctest
    doctest.testmod()