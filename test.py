# -- coding: utf-8 --
from tempfile import mkdtemp
from StringIO import StringIO
from subprocess import Popen, PIPE
from unittest import TestCase, main
from os.path import join, exists
from os import environ, unlink
from shutil import rmtree
from uuid import uuid4
from re import search

from git import Repo
from box.util.rotunicode import RotUnicode
from httmock import response, HTTMock

import bizarro, jekyll
from app import app

import codecs
codecs.register(RotUnicode.search_function)

#
# Tarball of a single-commit Git repo with files index.md and sub/index.md
# and branches "title" and "body" with non-conflicting edits to index.md only.
#
_tarball = '\x1f\x8b\x08\x00\xb9\t$S\x00\x03\xed\x9d\x0bt\x14W\x19\xc77@S\x08\x9c@\xc1Z\x94J\xa7\x12 \td\xf7\xde\x99;sgx\x9d`yCx#\xc5\xc0\xc1;3w\x92\x85\xecN\xba\xbbi\x12\x04\xdbc\xc5\xd2ZPh\xc5\x02\xa1\xd2JT(\x88\x16"\xa4\x1e\xe9!\xa5\xb4\xa1\xe1\x91T\xc4\xf2l\x95@\x14\x8bJ\xd2\x829\xd2\xe3,\x04\xd6]\x0e.K\xd9\xd95\xbd\xbf\x93\x93\xdd\x9d\xcc\xee73\xff\xfd\xfe\xf7\xde\xef\xceL\x9c.G\xdc\x01\x16\x18\x8b\xc1G\x88E\xf0\xdf\x8f\xd7q@^\x80\x10\x00\x04x\xc1\x01 DHtpb\xfc7\xcd\xe1(\xf1\x07\x88\x8f\xe3\x1c\x1ewA\x89\xcf\xbf\xd0}\xab\xf5\xa2\xfd\xfd\xff\x14\xa7k\xdc\xe8\x91\xa3\xe2\x1b#(\xb0$\xa1[\xeb\xcf\xe3\x08\xfdy\x80\x81\x83\x03\xf1\xdd\xack|\xce\xf5\xf7Qc\x08g\xfd\xf2\xbb\n)\xd1\xfd.\x0f\xf1\x07\xa8/-\xd1\x9b\xc5\xb0\t\xa7\xcb\xed5\xcc\xf86\x02\xb1\xfb?\x8f\xacE\xcc\xffm\xa0M\x7fZ\xa6\x15\x95\xe84>1\xa2\xf9\xbf E\xea/`Q`\xfeo\x07\xfd\xb8\x02w \xa7\xc8\x9fc\xb8\x8b\xa8\x9f\xcb\xc91\x03\x85\xd4\x17|\xd2\xf6\x95\xc81|\xa6g\xb8\xd3Z+\xec\x9b\x92\xd6\x8f\x9b\xe4\xf6Z\xef\x08\x14\x92\x00\x17<\x86\x01\xae\xd4\x1d(\xe4\x06\xf6\x1b\xc8\x11\x1f\xe54\xd3\xe3\xa1\xde\x80\xdfi\xad9\xc6\xf4q\x84+\xf6\x99\x0b\xa8\x16\xe0<\xa6?PT\xce\xb9\xbd\xdc#\x83\xad\xb7S\xce0\x8b\x8a\xccR\xb7\xb7\x80+5K\x8atN\xa5\xd6\xda\x05\xa6\xa9s~\x1a\xe0L\xc3\xfa\x84\xb6\xa8\\1\tX\xcd\x93\xd7\xcfe\x96x\xdb"\x04?\xc2\xc3\xb9\r\xae\xdc,\xe1JIp\x81\xc9\x95\xf8\xe9\xd5\xe5YC\xac7g;\xf3M2/\xf8\xe4\xdb\xaca\x8b\xc0\xe9\xba\xda\xf8\xc75\xc6\x1d\xf9?b\xfeo\x07m\xfa\x07HA\xfc\xbe\x04\xb1\xeb/\x08\x88g\xfa\xdbA\x9b\xfe\xd7:\xffq\x8a\x11\x8b\xfeRp9\x14\x10\x96\x98\xfev\x10\xa6\xbfj\xea\xe5q\x88\x11u\xfc/\xc2\x08\xfd\x91 \xf2\xac\xffg\x07\x18PMTy"`\t\x08PE\x90Wd,\xaa:\x92\x04]5tQ1\x08\xa4\nUY\xc7\xa9}\x12\x96\xff\x01w\xa0(\x0ec\xc0X\xf2_\x0c\xb6\x13\x10\x89\x08\xb1\xfc\xb7\x03bh\x08j\x86\x88x*\x11\xac\x0b\x8a,\x08\x10\xf3V\xfe\x03,\xea*\xc4@\x94\x91b@\x96\xff\xed\x93\xb0\xfc\xbfV\xfc\xbd\xeb1b\xc9\x7f ]\xcd\x7f\x0cY\xfd\xdf\x16\xac\xa6\x9fB\t[\xad\xbeh\x10\x05\x10\xa0\x88\xc1>\x18\xb24\xb0\\A\xd6\t\xe4y\rK\x12\xcb\xff\xf6\x89\xd3Uh\x9a\x0b\xe3[\x00\xba\x83\xfa\x8f\x88Y\xfd\xdf\x16\x9c.\x9d\xfa5\x9f\xbb8\xe06\xbdq\x8a\x11\xd5\xff1\x7fS\xfd\x1f\xb2\xf1\x9f-\xcc\xf2z\x89\x87\xea\x9c\x8f\x16\x9b~w\xc0\xf4\x95\x0f\xe5\xa8\xee\x0eV\xd5\xdd~.8)\x10,\xa7\x07\xd7\xe1\xac\x85\x86\xe9\x0b\xce\x17\x94R\xd5\xc9\x1a\x84v\x81\xd3\xa5\xfa\x88W+\xa4ql\x02\xee\xa0\xfe\xcb\x0b\xac\xfek\x0bN\x97fz\rwA<cD\xf3\x7f\x08"\xfd\x9f\x97x\x89\xf9\xbf\x1d\xe4k\xa6\x8f\xceK\xeb\x12\xf2\x7f\xcb\xe3=$\xf08\xf5\xf9\xad\x1e\x017\x9c\x03i]\x82\xcd\x80\xc7\xd4\xa9\xf5*\xe0+\xa1i]\xd4\xe0\x0co\xdb\x8bD\xef\x01\xe3\xb3\xe0t\x99jpV>\x9e#\x80;\x98\xff\x81l\xfe\xd7\x1eB\xfa\x03\x94\x0c\xf3\x7f\xd7\xea\xbf\x82 \xb0\xf3\x7fm!L\x7fMS\x0860\x81\xaaN\r\x19#AW\x90n\xa8\xc4\xd0y\x99\xf0\xb2\xce\x13U\x85r\xcc1\x82\x02#\xf4?\xda\x7f\xab\xcd\x0f\xd3\x9f\x87<\x10Y\xfbo\x07e)\x83\xb2&\xe4\xcd\x02\x82f\xf5\xbd\x80\x00\xa7\xbdS7q\xfc\xd6\xc3\xef\xe6\x91]Gw\x0c?\xb6\xa9\xa9\xfe\xe2\x94A\xd9\xa5\x87&\xd4\xadk\xfd\xe8\xd5\x96\'zu\xe4\xa6f:\xf3\xd4\x17\xe7\xa3\x0f\xbd\x15\xcd\xaf6|\xd2\xba\xfeK\x15\xf8\xf4\xb8\x9f\x957u\xee\xe8\x18y\xa6ok\xa2w\x89\x11\x03\xa1\xfc\x87Z2\xf8\xff\xb5\xfa\xbf\x80\x00f\xfeo\x07a\xfa\xeb\xb2\xa2Y=0\th"\xcf#\r#M\xd2E\x11[\xf6/\x89\x82\x8eu\x89`\xa4\xe81\xc7\x88\xe6\xff\x00\x0b\xe1\xfa\xf3\x00\xb1\xf1\x9f=\x94\xa5L\xdc_;e:\x80\xf4\xf0\x91#\x8d\xd3\xb3k\x07\xd7\x8e\x9f\xf5\xda\xf4_\xd47N\x9fZ\xec\x9a\x90\x97S[7\xd1u\xb6Cm\xf9\xc6\xb3g\xce\x0cz\xe1\xdc\x03\x8d\x1b\x9b\x1eKq<\xd3\xbf{F\xa27\x9dq\x17\x08\xe5?\x06\xc9\xe0\xffm\xe3?\x81\xd5\xff\xec!L\xff\xdb;\x15,\xe6\x18\xd1\xfc\x9fG8\\\x7f\x1eH<\xeb\xff\xdbBYJ\xe5\xc1\xbc\xf4\x1a\xaeG.9Z\xf1\x9d\xae\x85\xa9\xfb\xe7\xf7\xd2&\xcd\xfd\xd6\xb2\xbf\x80\x1d\x1b\xa7wkX\xba\xf3h\xd9=\xb3\xcdK\x8d\xd3r\xfa\x97n:P\xdc\xb4|NC\xee\x833{\x7fa\xfbD\xe7\x98\xafl\x91f|-uE\xaf\xdc\xaf\xa6\xad\xbd\xbf\xd3?\xf7\xee\xcb\xff\xf1\xf3c\xbe~\xf0<\xfc\xe3w\xfbq\xcf\xfdA\xee\x9a\xfa\xc2\xcb\xfa#\xa3*\xc5\xf2s\x9d.,\xd9\x94wJ\xc8\xb9|\xd98u|\xe1\x81\x8bs/\xee\x9f\xbdy\xe5\x0c\xcf\xa3\xbbh\xcd\x0cO\xf3\xe8\xcd\x04\xedy\xaatL\xdf=\x1d;\xb7n}\xfc\xd3\xae\xf7\xed\xbcg\xe7\x9a\x9fV,X\xfc\xfd\xee\x1b\xbaM\x1e\x91\xe8\xc3\xd4n\t\xe5\xbf\xcc\'\x83\xff\xb7\xf5\xffY\xfd\xc7&\xc2\xf4\x17\x05\x91`\t!IBP\xd3\x04H5\xa4Q\xa2"b\x00U\x81@G\x02$"\x8c9F\xf4\xfa\x0f\x7fs\xff\x9f\xf9\xbf-\xdc\xba\xfe\xf3\xc3j\xf8v\xces\x03\xc75\xee\x9a\xe2-\xbcR9\xf3\xf8\xb1-\xab\xaa\x07\xa4\xe6n\x98:w\xed^\xf0Fa\xcdI\xf9\xdc\xec\xca\x8f>\x1e*\xc8\xe6\xee\x95\x93\x9a\x0f\xdf\x97\xeaX\xb7\xe4\xcbM\x89\xde#F,\x84\xf2_4\x92\xc1\xff\xaf_\xff\x03\xd9\xf5?\xb6\x10\xa6\xbf\x88\x11\x14%(\xea:\x12\x15\xac\x12\x89"@\x90\x80\rQ\xd1xY\xb5~t\x01\xc6\xa3\xfe\xc3G\xf6\xff\x11;\xff\xcb\x1en\xd4\x7fH\x94\xfa\xcf\x99s\x19\xd97\xca?eg\xd3\xb7\'z\xcb\x19w\x83P\xfe+I\xe1\xff\xd7\xeb\xff<\xab\xff\xd8B\x98\xfe\x98W\x80\xae\x8b\x14\t\x94`Q\xc6\xd8P\x15I\x06\x8a\xaeP\r*\xd6\xa8@\xe65(\xc4\x1c#\xaa\xffK(\xb2\xff/`v\xff\x0f[\xb8\xde\xff\x97n\xaf\xff\xef\x18\xa4vOO\xf463\xee\x1e\xa1\xfcW\x93\xa9\xfe\xc3\xe6\x7fm"L\xff\xdb\xbb\x14,\xe6\x18Q\xeb\xff@\x8a\xf4\x7f^`\xd7\xff\xdaBYJ\xe5\x81\xe1\xe95\xa0[.9[Q\xf3\x80\xe3\xad\xe5\xef=\xd4\xe5\xe1\x01R\xfa\x87\xaf{\xfb\xfc(s\xd5\xbaS\x0fu\x1a\xfb\xcdE\xc7/m<S\x91\xfdA\x8f)Gf\xbel\xaa\xcbNT\x8d\xf2L\xcc\xec9u\xe9\xa8\xf2\x8c\x97\xae\xc8\x1b~\x92\xc9\x8d\r,\xfe}U\xefa\xcfo\xf9w\xab\xae\x14\x9d\xee9\xd7\x7f\xac\xc5I\x1b\xaa{\x17Te,\xce\xfa\xcd\t\xc7\x9b\xb9K\xceA\xa9\xf8\x93\xf5\x97&\xef>\xbf\xf9\x89\x87/\xac,\xda\xf6\x8f\xed\'\xfa\xb4\xac\xcf}6\xd1G\xe1\xf3K(\xff5!\x19\xfc\xffF\xfd\x072\xff\xb7\x830\xfd5*CY\x80\x94J\x86\xa4\xeb\xbc,\xf2H5\x08\x05TW\x0104M\xe6)\x04\xf18\xff3\xb2\xfe\x03\x01\xab\xff\xdb\xc3\xad\xeb\xff\xcb\xba\x97v\xeb\xf5\xbb\xf3C\x96\xcc~\xe9\xcd\x9e\xcd\xdb\xfcH*\x99\xbfZ\x84\x8e\x0eK\xff\xd4\x90\xf1\xbd\x7f\x8d\xeeua\x9f\xf2F\xb6g\xdb\xe95{\xca\x9b\x97\xebk\x9f^\x01\x1c\xbf\xed\xdbgw\xa2\xf7\x88\x11\x0b\xa1\xfc\'IQ\xffi;\xff_d\xf7\x7f\xb5\x870\xfdo\xefV01\xc7\x88\xda\xffGR\xc4\xf9\xff\xc0\x1a\x002\xff\xb7\x03\xab\xff\xbfbd\xf0\xfc\x1f\xc7\xf0\xe6\xb4\x11\x1b\xe6\x14\xe7sp\xdf\xde\xed?xtue\xff\xaa\xb7\xb8OO\xefs\x95\xad=^W<\xefhC\xd5\xe8a-\x03^IY\xd3\xb1\xfao\xef\xec\xcdx\x7f\xe8\xb0\x9f?\x995v\x7f\xed\xa2\xd7F\xccy\xb6\xbe\xec\xe3W\x06\xe4\x1f\xad_\xf5b\xfd\xfb\x1f<=)\xa5s\xcd\x93\x7fvtNU\xba\x8fX\xf9\xeb\xd5\'\xe5\xec\xd6\x96j\xe9J\xe6\xb0\xf7\xfco\xb7\xb8\xff^\xd9\xf4\xee7\xbeX\xfd\xd8\xc9\xfc\xaa\xfa\xec\xad`\xfd\x82u\xbf<V\xd1q\xd1\xbd\x07;-\xe9t\xef\x86\xcb;\x8f5\xba\x9ey\xfd\xd0\x8e\xbcU\x01\xd7\x95\xac\xbfv\x1d\x9f2\xe5\xc1D\x1f\xa5\xf6K(\xffu\x9aT\xfe\xcf\xea\xff\xb6\x10\xa6\xbf\xcc\xabXT\x11\x8fy\xca\x13l\xf0D\xc6\x8a\xaa*D\x82\x12UDC2D\xa8\x1aF\xcc1\xa2\xcf\xff\x8a\x91\xfe\x8f\x05\xcc\xfc\xdf\x0en\xcc\xff\x16\xdc<\xff\xdbyr]V\xce\xf8\xc1\xb5u\x87\x06\x9d\xedP\xbb(\xfc\n\x80_M\xebq\x7f\xa27\x9e\xf1\x99\t\xe5\x7f\xfc\xfe\x0fDL\xf5\xff\xab\xf7\x7f@\xd6H\x94\xf9\xbf\x1d\x84\xf4/&\xda\xc2\xe4\xd1\x1f\xb2\xeb\xff\x19\x0c\x06\x83\xc1`0\x18\x0c\x06\xe3\xae\xf2\x1f\xad\xeb\xf2\x05\x00x\x00\x00'

class TestJekyll (TestCase):

    def test_good_files(self):
        front = dict(title='Greeting'.encode('rotunicode'))
        body, file = u'World: Hello.'.encode('rotunicode'), StringIO()

        jekyll.dump_jekyll_doc(front, body, file)
        _front, _body = jekyll.load_jekyll_doc(file)

        self.assertEqual(_front['title'], front['title'])
        self.assertEqual(_body, body)
        
        file.seek(0)
        file.read(4) == '---\n'

    def test_bad_files(self):
        file = StringIO('Missing front matter')
        
        with self.assertRaises(Exception):
            jekyll.load_jekyll_doc(file)

class TestRepo (TestCase):

    def setUp(self):
        dirname = mkdtemp(prefix='bizarro-')
        
        tar = Popen(('tar', '-C', dirname, '-xzf', '-'), stdin=PIPE)
        tar.stdin.write(_tarball)
        tar.stdin.close()
        tar.wait()
        
        self.origin = Repo(dirname)
        self.clone1 = self.origin.clone(mkdtemp(prefix='bizarro-'))
        self.clone2 = self.origin.clone(mkdtemp(prefix='bizarro-'))
        
        self.session = dict(email=str(uuid4()))
    
        environ['GIT_AUTHOR_NAME'] = ' '
        environ['GIT_COMMITTER_NAME'] = ' '
        environ['GIT_AUTHOR_EMAIL'] = self.session['email']
        environ['GIT_COMMITTER_EMAIL'] = self.session['email']

    def test_repo_features(self):
        self.assertTrue(self.origin.bare)
        
        branch_names = [b.name for b in self.origin.branches]
        self.assertEqual(set(branch_names), set(['master', 'title', 'body']))
    
    def test_start_branch(self):
        ''' Make a simple edit in a clone, verify that it appears in the other.
        '''
        name = str(uuid4())
        branch1 = bizarro.repo.start_branch(self.clone1, 'master', name)
        
        self.assertTrue(name in self.clone1.branches)
        self.assertTrue(name in self.origin.branches)
        
        #
        # Make a change to the branch and push it.
        #
        branch1.checkout()
        message = str(uuid4())
        
        with open(join(self.clone1.working_dir, 'index.md'), 'a') as file:
            file.write('\n\n...')
        
        args = self.clone1, 'index.md', message, branch1.commit.hexsha, 'master'
        bizarro.repo.save_working_file(*args)
        
        #
        # See if the branch made it to clone 2
        #
        branch2 = bizarro.repo.start_branch(self.clone2, 'master', name)

        self.assertTrue(name in self.clone2.branches)
        self.assertEquals(branch2.commit.hexsha, branch1.commit.hexsha)
        self.assertEquals(branch2.commit.message, message)
    
    def test_new_file(self):
        ''' Make a new file and delete an old file in a clone, verify that it appears in the other.
        '''
        name = str(uuid4())
        branch1 = bizarro.repo.start_branch(self.clone1, 'master', name)
        
        self.assertTrue(name in self.clone1.branches)
        self.assertTrue(name in self.origin.branches)
        
        #
        # Make a new file in the branch and push it.
        #
        branch1.checkout()
        
        bizarro.edit.create_new_page(self.clone1, '', 'hello.md',
                                     dict(title='Hello'), 'Hello hello.')
        
        args = self.clone1, 'hello.md', str(uuid4()), branch1.commit.hexsha, 'master'
        bizarro.repo.save_working_file(*args)
        
        #
        # Delete an existing file in the branch and push it.
        #
        message = str(uuid4())
        
        bizarro.edit.delete_file(self.clone1, '', 'index.md')
        
        args = self.clone1, 'index.md', message, branch1.commit.hexsha, 'master'
        bizarro.repo.save_working_file(*args)
        
        #
        # See if the branch made it to clone 2
        #
        branch2 = bizarro.repo.start_branch(self.clone2, 'master', name)

        self.assertTrue(name in self.clone2.branches)
        self.assertEquals(branch2.commit.hexsha, branch1.commit.hexsha)
        self.assertEquals(branch2.commit.message, message)
        self.assertEquals(branch2.commit.author.email, self.session['email'])
        self.assertEquals(branch2.commit.committer.email, self.session['email'])
        
        branch2.checkout()
        
        with open(join(self.clone2.working_dir, 'hello.md')) as file:
            front, body = jekyll.load_jekyll_doc(file)
            
            self.assertEquals(front['title'], 'Hello')
            self.assertEquals(body, 'Hello hello.')
        
        self.assertFalse(exists(join(self.clone2.working_dir, 'index.md')))
    
    def test_move_file(self):
        ''' Change the path of a file.
        '''
        name = str(uuid4())
        branch1 = bizarro.repo.start_branch(self.clone1, 'master', name)
        
        self.assertTrue(name in self.clone1.branches)
        self.assertTrue(name in self.origin.branches)
        
        #
        # Rename a file in the branch.
        #
        branch1.checkout()

        args = self.clone1, 'index.md', 'hello/world.md', branch1.commit.hexsha, 'master'
        bizarro.repo.move_existing_file(*args)
        
        #
        # See if the new file made it to clone 2
        #
        branch2 = bizarro.repo.start_branch(self.clone2, 'master', name)
        branch2.checkout()
        
        self.assertTrue(exists(join(self.clone2.working_dir, 'hello/world.md')))
        self.assertFalse(exists(join(self.clone2.working_dir, 'index.md')))
    
    def test_content_merge(self):
        ''' Test that non-conflicting changes on the same file merge cleanly.
        '''
        branch1 = bizarro.repo.start_branch(self.clone1, 'master', 'title')
        branch2 = bizarro.repo.start_branch(self.clone2, 'master', 'body')
        
        branch1.checkout()
        branch2.checkout()
        
        with open(self.clone1.working_dir + '/index.md') as file:
            front1, _ = jekyll.load_jekyll_doc(file)
        
        with open(self.clone2.working_dir + '/index.md') as file:
            _, body2 = jekyll.load_jekyll_doc(file)
        
        #
        # Show that only the title branch title is now present on master.
        #
        bizarro.repo.complete_branch(self.clone1, 'master', 'title')
        
        with open(self.clone1.working_dir + '/index.md') as file:
            front1b, body1b = jekyll.load_jekyll_doc(file)
        
        self.assertEqual(front1b['title'], front1['title'])
        self.assertNotEqual(body1b, body2)
        
        #
        # Show that the body branch body is also now present on master.
        #
        bizarro.repo.complete_branch(self.clone2, 'master', 'body')
        
        with open(self.clone2.working_dir + '/index.md') as file:
            front2b, body2b = jekyll.load_jekyll_doc(file)
        
        self.assertEqual(front2b['title'], front1['title'])
        self.assertEqual(body2b, body2)
        self.assertTrue(self.clone2.commit().message.startswith('Merged work from'))
    
    def test_content_merge_extra_change(self):
        ''' Test that non-conflicting changes on the same file merge cleanly.
        '''
        branch1 = bizarro.repo.start_branch(self.clone1, 'master', 'title')
        branch2 = bizarro.repo.start_branch(self.clone2, 'master', 'body')
        
        branch1.checkout()
        branch2.checkout()
        
        with open(self.clone1.working_dir + '/index.md') as file:
            front1, _ = jekyll.load_jekyll_doc(file)
        
        with open(self.clone2.working_dir + '/index.md') as file:
            front2, body2 = jekyll.load_jekyll_doc(file)
        
        #
        # Show that only the title branch title is now present on master.
        #
        bizarro.repo.complete_branch(self.clone1, 'master', 'title')
        
        with open(self.clone1.working_dir + '/index.md') as file:
            front1b, body1b = jekyll.load_jekyll_doc(file)
        
        self.assertEqual(front1b['title'], front1['title'])
        self.assertNotEqual(body1b, body2)
        
        #
        # Show that the body branch body is also now present on master.
        #
        bizarro.edit.update_page(self.clone2, 'index.md',
                                 front2, 'Another change to the body')
        
        bizarro.repo.save_working_file(self.clone2, 'index.md', 'A new change',
                                       self.clone2.commit().hexsha, 'master')
        
        #
        # Show that upstream changes from master have been merged here.
        #
        with open(self.clone2.working_dir + '/index.md') as file:
            front2b, body2b = jekyll.load_jekyll_doc(file)
        
        self.assertEqual(front2b['title'], front1['title'])
        self.assertEqual(body2b.strip(), 'Another change to the body')
        self.assertTrue(self.clone2.commit().message.startswith('Merged work from'))
    
    def test_multifile_merge(self):
        ''' Test that two non-conflicting new files merge cleanly.
        '''
        name = str(uuid4())
        branch1 = bizarro.repo.start_branch(self.clone1, 'master', name)
        branch2 = bizarro.repo.start_branch(self.clone2, 'master', name)
        
        #
        # Make new files in each branch and save them.
        #
        branch1.checkout()
        branch2.checkout()
        
        bizarro.edit.create_new_page(self.clone1, '', 'file1.md',
                                     dict(title='Hello'), 'Hello hello.')

        bizarro.edit.create_new_page(self.clone2, '', 'file2.md',
                                     dict(title='Goodbye'), 'Goodbye goodbye.')

        #
        # Show that the changes from the first branch made it to origin.
        #
        args1 = self.clone1, 'file1.md', '...', branch1.commit.hexsha, 'master'
        commit1 = bizarro.repo.save_working_file(*args1)

        self.assertEquals(self.origin.branches[name].commit, commit1)
        self.assertEquals(self.origin.branches[name].commit.author.email, self.session['email'])
        self.assertEquals(self.origin.branches[name].commit.committer.email, self.session['email'])
        self.assertEquals(commit1, branch1.commit)
        
        #
        # Show that the changes from the second branch also made it to origin.
        #
        args2 = self.clone2, 'file2.md', '...', branch2.commit.hexsha, 'master'
        commit2 = bizarro.repo.save_working_file(*args2)

        self.assertEquals(self.origin.branches[name].commit, commit2)
        self.assertEquals(self.origin.branches[name].commit.author.email, self.session['email'])
        self.assertEquals(self.origin.branches[name].commit.committer.email, self.session['email'])
        self.assertEquals(commit2, branch2.commit)
        
        #
        # Show that the merge from the second branch made it back to the first. 
        #
        branch1b = bizarro.repo.start_branch(self.clone1, 'master', name)

        self.assertEquals(branch1b.commit, branch2.commit)
        self.assertEquals(branch1b.commit.author.email, self.session['email'])
        self.assertEquals(branch1b.commit.committer.email, self.session['email'])
    
    def test_same_branch_conflict(self):
        ''' Test that a conflict in two branches appears at the right spot.
        '''
        name = str(uuid4())
        branch1 = bizarro.repo.start_branch(self.clone1, 'master', name)
        branch2 = bizarro.repo.start_branch(self.clone2, 'master', name)
        
        #
        # Make new files in each branch and save them.
        #
        branch1.checkout()
        branch2.checkout()
        
        bizarro.edit.create_new_page(self.clone1, '', 'conflict.md',
                                     dict(title='Hello'), 'Hello hello.')

        bizarro.edit.create_new_page(self.clone2, '', 'conflict.md',
                                     dict(title='Goodbye'), 'Goodbye goodbye.')

        #
        # Show that the changes from the first branch made it to origin.
        #
        args1 = self.clone1, 'conflict.md', '...', branch1.commit.hexsha, 'master'
        commit1 = bizarro.repo.save_working_file(*args1)

        self.assertEquals(self.origin.branches[name].commit, commit1)
        self.assertEquals(commit1, branch1.commit)
        
        #
        # Show that the changes from the second branch conflict with the first.
        #
        with self.assertRaises(bizarro.repo.MergeConflict) as conflict:
            args2 = self.clone2, 'conflict.md', '...', branch2.commit.hexsha, 'master'
            commit2 = bizarro.repo.save_working_file(*args2)
        
        self.assertEqual(conflict.exception.remote_commit, commit1)
        
        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)
        
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].a_blob.name, 'conflict.md')
        self.assertEqual(diffs[0].b_blob.name, 'conflict.md')
    
    def test_upstream_pull_conflict(self):
        ''' Test that a conflict in two branches appears at the right spot.
        '''
        name1, name2 = str(uuid4()), str(uuid4())
        branch1 = bizarro.repo.start_branch(self.clone1, 'master', name1)
        branch2 = bizarro.repo.start_branch(self.clone2, 'master', name2)
        
        #
        # Make new files in each branch and save them.
        #
        branch1.checkout()
        branch2.checkout()
        
        bizarro.edit.create_new_page(self.clone1, '', 'conflict.md',
                                     dict(title='Hello'), 'Hello hello.')

        bizarro.edit.create_new_page(self.clone2, '', 'conflict.md',
                                     dict(title='Goodbye'), 'Goodbye goodbye.')

        #
        # Show that the changes from the first branch made it to origin.
        #
        args1 = self.clone1, 'conflict.md', '...', branch1.commit.hexsha, 'master'
        commit1 = bizarro.repo.save_working_file(*args1)

        self.assertEquals(self.origin.branches[name1].commit, commit1)
        self.assertEquals(commit1, branch1.commit)
        
        #
        # Merge the first branch to master.
        #
        commit2 = bizarro.repo.complete_branch(self.clone1, 'master', name1)
        self.assertFalse(name1 in self.origin.branches)
        
        #
        # Show that the changes from the second branch conflict with the first.
        #
        with self.assertRaises(bizarro.repo.MergeConflict) as conflict:
            args2 = self.clone2, 'conflict.md', '...', branch2.commit.hexsha, 'master'
            bizarro.repo.save_working_file(*args2)
        
        self.assertEqual(conflict.exception.remote_commit, commit2)
        
        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)
        
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].a_blob.name, 'conflict.md')
        self.assertEqual(diffs[0].b_blob.name, 'conflict.md')
    
    def test_upstream_push_conflict(self):
        ''' Test that a conflict in two branches appears at the right spot.
        '''
        name1, name2 = str(uuid4()), str(uuid4())
        branch1 = bizarro.repo.start_branch(self.clone1, 'master', name1)
        branch2 = bizarro.repo.start_branch(self.clone2, 'master', name2)
        
        #
        # Make new files in each branch and save them.
        #
        branch1.checkout()
        branch2.checkout()
        
        bizarro.edit.create_new_page(self.clone1, '', 'conflict.md',
                                     dict(title='Hello'), 'Hello hello.')

        bizarro.edit.create_new_page(self.clone2, '', 'conflict.md',
                                     dict(title='Goodbye'), 'Goodbye goodbye.')

        #
        # Push changes from the two branches to origin.
        #
        args1 = self.clone1, 'conflict.md', '...', branch1.commit.hexsha, 'master'
        commit1 = bizarro.repo.save_working_file(*args1)

        args2 = self.clone2, 'conflict.md', '...', branch2.commit.hexsha, 'master'
        commit2 = bizarro.repo.save_working_file(*args2)
        
        #
        # Merge the two branches to master; show that second merge will fail.
        #
        bizarro.repo.complete_branch(self.clone1, 'master', name1)
        self.assertFalse(name1 in self.origin.branches)
        
        with self.assertRaises(bizarro.repo.MergeConflict) as conflict:
            bizarro.repo.complete_branch(self.clone2, 'master', name2)
        
        self.assertEqual(conflict.exception.remote_commit, self.origin.commit())
        self.assertEqual(conflict.exception.local_commit, self.clone2.commit())
        
        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)
        
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].a_blob.name, 'conflict.md')
        self.assertEqual(diffs[0].b_blob.name, 'conflict.md')
    
    def test_conflict_resolution_clobber(self):
        ''' Test that a conflict in two branches can be clobbered.
        '''
        name = str(uuid4())
        branch1 = bizarro.repo.start_branch(self.clone1, 'master', 'title')
        branch2 = bizarro.repo.start_branch(self.clone2, 'master', name)
        
        #
        # Add goner.md in branch1.
        #
        branch1.checkout()
        
        bizarro.edit.create_new_page(self.clone1, '', 'goner.md',
                                     dict(title=name), 'Woooo woooo.')

        args = self.clone1, 'goner.md', '...', branch1.commit.hexsha, 'master'
        commit = bizarro.repo.save_working_file(*args)

        #
        # Change index.md in branch2 so it conflicts with title branch.
        #
        branch2.checkout()
        
        bizarro.edit.update_page(self.clone2, 'index.md',
                                 dict(title=name), 'Hello hello.')
        
        args = self.clone2, 'index.md', '...', branch2.commit.hexsha, 'master'
        commit = bizarro.repo.save_working_file(*args)

        #
        # Merge the original title branch, fail to merge our conflicting branch.
        #
        bizarro.repo.complete_branch(self.clone1, 'master', 'title')

        with self.assertRaises(bizarro.repo.MergeConflict) as conflict:
            bizarro.repo.complete_branch(self.clone2, 'master', name)
        
        self.assertEqual(conflict.exception.local_commit, commit)
        
        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)
        
        self.assertEqual(len(diffs), 2)
        self.assertTrue(diffs[0].a_blob.name in ('index.md', 'goner.md'))
        self.assertTrue(diffs[1].a_blob.name in ('index.md', 'goner.md'))
        
        #
        # Merge our conflicting branch and clobber the default branch.
        #
        bizarro.repo.clobber_default_branch(self.clone2, 'master', name)
        
        with open(join(self.clone2.working_dir, 'index.md')) as file:
            front, body = jekyll.load_jekyll_doc(file)
        
        self.assertEqual(front['title'], name)
        self.assertFalse(name in self.origin.branches)
        
        # If goner.md is still around, then master wasn't fully clobbered.
        self.clone1.branches['master'].checkout()
        self.clone1.git.pull('origin', 'master')
        self.assertFalse(exists(join(self.clone2.working_dir, 'goner.md')))
        self.assertTrue(self.clone2.commit().message.startswith('Clobbered with work from'))
    
    def test_conflict_resolution_abandon(self):
        ''' Test that a conflict in two branches can be abandoned.
        '''
        name = str(uuid4())
        branch1 = bizarro.repo.start_branch(self.clone1, 'master', 'title')
        branch2 = bizarro.repo.start_branch(self.clone2, 'master', name)
        
        #
        # Change index.md in branch2 so it conflicts with title branch.
        # Also add goner.md, which we'll later want to disappear.
        #
        branch2.checkout()
        
        bizarro.edit.update_page(self.clone2, 'index.md',
                                 dict(title=name), 'Hello hello.')
        
        bizarro.edit.create_new_page(self.clone2, '', 'goner.md',
                                     dict(title=name), 'Woooo woooo.')

        args = self.clone2, 'index.md', '...', branch2.commit.hexsha, 'master'
        commit = bizarro.repo.save_working_file(*args)

        args = self.clone2, 'goner.md', '...', branch2.commit.hexsha, 'master'
        commit = bizarro.repo.save_working_file(*args)

        #
        # Merge the original title branch, fail to merge our conflicting branch.
        #
        bizarro.repo.complete_branch(self.clone1, 'master', 'title')

        with self.assertRaises(bizarro.repo.MergeConflict) as conflict:
            bizarro.repo.complete_branch(self.clone2, 'master', name)
        
        self.assertEqual(conflict.exception.local_commit, commit)
        
        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)
        
        self.assertEqual(len(diffs), 2)
        self.assertTrue(diffs[0].b_blob.name in ('index.md', 'goner.md'))
        self.assertTrue(diffs[1].b_blob.name in ('index.md', 'goner.md'))
        
        #
        # Merge our conflicting branch and abandon it to the default branch.
        #
        bizarro.repo.abandon_branch(self.clone2, 'master', name)
        
        with open(join(self.clone2.working_dir, 'index.md')) as file:
            front, body = jekyll.load_jekyll_doc(file)
        
        self.assertNotEqual(front['title'], name)
        self.assertFalse(name in self.origin.branches)
        
        # If goner.md is still around, then the branch wasn't fully abandoned.
        self.assertFalse(exists(join(self.clone2.working_dir, 'goner.md')))
        self.assertTrue(self.clone2.commit().message.startswith('Abandoned work from'))
    
    def test_peer_review(self):
        ''' Change the path of a file.
        '''
        name = str(uuid4())
        branch1 = bizarro.repo.start_branch(self.clone1, 'master', name)
        
        #
        # Make a commit.
        #
        environ['GIT_AUTHOR_NAME'] = 'Jim Content Creator'
        environ['GIT_COMMITTER_NAME'] = 'Jim Content Creator'
        environ['GIT_AUTHOR_EMAIL'] = 'creator@example.com'
        environ['GIT_COMMITTER_EMAIL'] = 'creator@example.com'
        
        branch1.checkout()
        self.assertFalse(bizarro.repo.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(bizarro.repo.is_peer_reviewed(self.clone1, 'master', name))
        
        bizarro.edit.update_page(self.clone1, 'index.md',
                                 dict(title=name), 'Hello you-all.')
        
        bizarro.repo.save_working_file(self.clone1, 'index.md', 'I made a change',
                                       self.clone1.commit().hexsha, 'master')
        
        self.assertTrue(bizarro.repo.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(bizarro.repo.is_peer_reviewed(self.clone1, 'master', name))
        self.assertEqual(bizarro.repo.ineligible_peer(self.clone1, 'master', name), 'creator@example.com')
        
        #
        # Approve the work as someone else.
        #
        environ['GIT_AUTHOR_NAME'] = 'Joe Reviewer'
        environ['GIT_COMMITTER_NAME'] = 'Joe Reviewer'
        environ['GIT_AUTHOR_EMAIL'] = 'reviewer@example.com'
        environ['GIT_COMMITTER_EMAIL'] = 'reviewer@example.com'
        
        bizarro.repo.mark_as_reviewed(self.clone1)

        self.assertFalse(bizarro.repo.needs_peer_review(self.clone1, 'master', name))
        self.assertTrue(bizarro.repo.is_peer_reviewed(self.clone1, 'master', name))
        self.assertEqual(bizarro.repo.ineligible_peer(self.clone1, 'master', name), None)
        
        #
        # Make another commit.
        #
        bizarro.edit.update_page(self.clone1, 'index.md',
                                 dict(title=name), 'Hello you there.')
        
        bizarro.repo.save_working_file(self.clone1, 'index.md', 'I made a change',
                                       self.clone1.commit().hexsha, 'master')
        
        self.assertTrue(bizarro.repo.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(bizarro.repo.is_peer_reviewed(self.clone1, 'master', name))
        self.assertEqual(bizarro.repo.ineligible_peer(self.clone1, 'master', name), 'reviewer@example.com')
        
        #
        # Approve the work as someone else.
        #
        environ['GIT_AUTHOR_NAME'] = 'Jane Reviewer'
        environ['GIT_COMMITTER_NAME'] = 'Jane Reviewer'
        environ['GIT_AUTHOR_EMAIL'] = 'reviewer@example.org'
        environ['GIT_COMMITTER_EMAIL'] = 'reviewer@example.org'
        
        bizarro.repo.mark_as_reviewed(self.clone1)

        self.assertFalse(bizarro.repo.needs_peer_review(self.clone1, 'master', name))
        self.assertTrue(bizarro.repo.is_peer_reviewed(self.clone1, 'master', name))
        self.assertEqual(bizarro.repo.ineligible_peer(self.clone1, 'master', name), None)
    
    def tearDown(self):
        rmtree(self.origin.git_dir)
        rmtree(self.clone1.working_dir)
        rmtree(self.clone2.working_dir)

class TestApp (TestCase):

    def setUp(self):
        work_path = mkdtemp(prefix='bizarro-repo-clones-')
        repo_path = mkdtemp(prefix='bizarro-sample-site-')
        
        tar = Popen(('tar', '-C', repo_path, '-xzf', '-'), stdin=PIPE)
        tar.stdin.write(_tarball)
        tar.stdin.close()
        tar.wait()
        
        app.config['WORK_PATH'] = work_path
        app.config['REPO_PATH'] = repo_path

        self.app = app.test_client()
    
    def persona_verify(self, url, request):
        if url.geturl() == 'https://verifier.login.persona.org/verify':
            return response(200, '''{"status": "okay", "email": "user@example.com"}''', headers=dict(Link='<https://api.github.com/user/337792/repos?page=1>; rel="prev", <https://api.github.com/user/337792/repos?page=1>; rel="first"'))

        else:
            raise Exception('Asked for unknown URL ' + url.geturl())

    def test_login(self):
        ''' Check basic log in / log out flow without talking to Persona.
        '''
        response = self.app.get('/')
        self.assertFalse('user@example.com' in response.data)

        with HTTMock(self.persona_verify):
            response = self.app.post('/sign-in', data={'email': 'user@example.com'})
            self.assertEquals(response.status_code, 200)

        response = self.app.get('/')
        self.assertTrue('user@example.com' in response.data)

        response = self.app.post('/sign-out')
        self.assertEquals(response.status_code, 200)
    
        response = self.app.get('/')
        self.assertFalse('user@example.com' in response.data)
    
    def test_branches(self):
        ''' Check basic branching functionality.
        '''
        with HTTMock(self.persona_verify):
            self.app.post('/sign-in', data={'email': 'user@example.com'})
        
        response = self.app.post('/start', data={'branch': 'do things'},
                                 follow_redirects=True)

        self.assertTrue('user@example.com/do-things' in response.data)
        
        response = self.app.post('/tree/user@example.com%252Fdo-things/edit/',
                                 data={'action': 'add', 'path': 'hello.md'},
                                 follow_redirects=True)

        self.assertEquals(response.status_code, 200)
        
        response = self.app.get('/tree/user@example.com%252Fdo-things/edit/')

        self.assertTrue('hello.md' in response.data)
        
        response = self.app.get('/tree/user@example.com%252Fdo-things/edit/hello.md')
        hexsha = search(r'<input name="hexsha" value="(\w+)"', response.data).group(1)

        response = self.app.post('/tree/user@example.com%252Fdo-things/save/hello.md',
                                 data={'layout': 'multi', 'hexsha': hexsha,
                                       'title': 'Greetings', 'body': 'Hello world.\n',
                                       'title-es': '', 'title-zh-cn': '',
                                       'body-es': '', 'body-zh-cn': '',
                                       'url-slug': 'hello'},
                                 follow_redirects=True)

        self.assertEquals(response.status_code, 200)
    
    def tearDown(self):
        rmtree(app.config['WORK_PATH'])
        rmtree(app.config['REPO_PATH'])

if __name__ == '__main__':
    main()