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
    >>> file.read(4) == '---\\n'
    True
'''
import yaml

def load_jekyll_doc(file):
    ''' Load jekyll front matter and remaining content from a file.
    '''
    # Check for presence of document marker.
    file.seek(0)
    
    if file.read(len("---\n")) != "---\n":
        raise Exception('File lacks front-matter: %s' % getattr(file, 'name', None))
    
    # Seek to just after the initial document marker.
    file.seek(len("---\n"))
    
    for token in yaml.scan(file):
        # Look for a token that shows we're about to reach the content.
        if type(token) is yaml.DocumentStartToken:
        
            # Seek to the beginning, and load the front matter as a document.
            file.seek(0)
            bytes = file.read(token.end_mark.index)
            front_matter = yaml.safe_load(bytes)
            
            # Seek just after the document separator, and get remaining string.
            file.read(len("\n---\n"))
            content = file.read().decode('utf-8')
            
            return front_matter, content
    
    raise Exception('Never found a yaml.DocumentStartToken')

def dump_jekyll_doc(front_matter, content, file):
    ''' Dump jekyll front matter and content to a file.
    
        To provide some guarantee of human-editable output, front matter
        is dumped using the newline-preserving block literal form.
        
        Sample output:
        
          ---
          "title": |-
            Greeatings
          ---
          Hello world.
    '''
    # Use newline-preserving block literal form.
    # yaml.SafeDumper ensures best unicode output.
    dump_kwargs = dict(Dumper=yaml.SafeDumper, default_flow_style=False,
                       canonical=False, default_style='|', indent=2)
    
    # Write front matter to the start of the file.
    file.seek(0)
    file.truncate()
    file.write("---\n")
    yaml.dump(front_matter, file, **dump_kwargs)

    # Write content to the end of the file.
    file.write("---\n")
    file.write(content.encode('utf8'))

if __name__ == '__main__':
    import doctest
    doctest.testmod()