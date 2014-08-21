# -- coding: utf-8 --
from flask import Flask, session
from unittest import main, TestCase

from tempfile import mkdtemp
from StringIO import StringIO
from subprocess import Popen, PIPE
from os.path import join, exists
from os import environ, unlink
from shutil import rmtree
from uuid import uuid4
from re import search
import random
from json import loads
from datetime import date, timedelta

from git import Repo
from box.util.rotunicode import RotUnicode
from httmock import response, HTTMock
from mock import MagicMock

from bizarro import app, jekyll_functions, repo_functions, edit_functions, google_api_functions

import codecs
codecs.register(RotUnicode.search_function)

#
# Tarball of a single-commit Git repo with files index.md and sub/index.md
# and branches "title" and "body" with non-conflicting edits to index.md only.
#
_tarball = '\x1f\x8b\x08\x00\xca_\xf6S\x00\x03\xed\x9d\t|\x14\xd5\x1d\xc7w\xb9\x89\x14P<\xb0Z\x1d\xca!G\xb2yo\xe6\xcd\x15\x8e\x82r\n\x11D\xf0(\xf8I\xe7x\x93,$;qwb\x12\x91\xd6\x1e\xd6\x13Z\xf0B\x0eE+mU\xd4V\xa5\x88~\xd4\x8a\xa8\x84"\x1a\xacEAE-Wk\xb5\x16\xf0\xa2\xc5Og6\xd9\xb0\x9bT\xb3\x1b3oS\xf6\xff\xfd\xc0g\x8f\xcc\xee\x9b\x9d\xdd\xdf\xef\xff\x8e\xff{/T\x18*\t\x05\xfc\x05!$\xcb"\x17\xbf\x95\x1an\x11O\x1an=\x88$s\x98\x17d\x91\x882\x11%\x0ea^$B\x80C>\x9fW\x9c\xaa\x98\xa3E\xddS\xa9\x08\x97VEc\xf3\xc3_u\x9c{\x98e}\xcd\xfb4|\x14\xae\xe9\xf6\xff\x85\xae\xa7v\x0ft\n\x04\x8a5\x83\x9b~\x11w)\xd7\x88\xf7\\\xa0\xa7\xfb\x9f\x0f\x04\x82]\xdd[\xf7qPN\xef-\xc7\xcd\x9a5\xb3\xe1^\xfc\x15\xcb\xdc\xffw7;$x\xec\xf9~\x86]\x11\xd2*+\xcbiH3\xcaC\x0e\xadq\xdc?\x0c\x18\xe8>\xe0p^U\x8cF\x8b&\xbaLp)\x18\xefRp\x9eK\xc1\xb9.\x05\xe3\\\x1a\xae\xb7\xa8\x16\x95\xc4*m\xa7<\\Z\xe6\x14)j\x91V^nW\xe7\x87#e4\x1av\xa8\x99o\x85\xcbiI\xe3\xc3|3\x1c\xa5\x86cGk\x13\xcf\x14E\xa9f\xe6\xd3\x1ajT94\xdf{\xa09N4~\xc7=\x9d\xa6\xfb1\xf7\xef\xee\xd1\xb5y\xedr\xe5;\x04\xa1B\xff\xcbhM\xff\x9e^\x9a\xe9\x9f\x17H\x80\x13\xfd?\xb5\x9c\xd7\x7f\xc8\xf5\x7f=\xaaE\x8c2\x1a\xf3\xab\x8c4\xfd\x1fc\xf7.\xe2\x05\xf7\xfb\'X\x00\xffg\x03\xf8\x7f\x8e\xfb\x7fB\xfd\xfe\x05\x824\xfd?I\xff\x82,a\xf0\x7f\x16x\xfeo\xd8\x11+\\\xea_\x19\xee\xf5\x90$\xf25\xfe/\xb4\xf8\xfeEY\x02\xffgB\x1a\xfe\x1f\xd8\x17h\xf0\xff\xfe\xe9\xbde\x92\xff{\xaf\xf0|\xfe\x9af\x87\x04\x8f=\xcf\xc4\xffs\xd7\xe0[!T\xe8\xb7\xfa[\xd7?F|s\xfd\x0b\xa2\x08\xfag\xc1\x1c\xc3\x8e\xd2\xcb\xf3zFi\xa5\x1d\x0b{u"\xcb\x8eVh\xce\x954\x1a\x0b\xdb\x11n4\x87\xf2zz\x95\xa7\n\xdb\xa4\xee#\'ZE\xf3z\xeaZ\xb4\xe9A\xb6?\x01\xf0M\xf0\xe2\xbfIcF4\\\xe9\xb8\xdf\xb7/ed\x1e\xff\x89$\x12\xd0?\x13 \xfe\xe7x\xfc\xf7[\xfd\xad\xeb\x1f\xc9\xcd\xe3?!\x04\x83\xfeY0;\x12\xd1*\xa8\xc9\x1d\x8b\xff#9j\x86\x1d\xce)\x0b\xc78/\xf0s\x8e\xcdy\xc7p\xee\x93n\xdd\x80+\r;\xd5T\x0f\xe5\x8eD\x8ek\xbc\xf8?y\xc2\xb8\xf1~\x96\xd1\x86\xf6?\x12x\xd0?\x13 \xfe\xe7x\xfc\xf7[\xfdi\xc4\x7f\xbe\xf9\xf8\x0f/a\x19\xf4\xcf\x82(\xb5\x8a\xdc\xe0o\xc5\n\xcb\xbc\xdf\x7fa\x85\x16sh4w~\xff\xb9\x8e\x17\xff\xcbl{\xbeo\x83\xbf\x81\xb6\x8c\xff\nD\x86\xfa?\x1b`\xfc7\xc7\xc7\x7f\xe3\xea\xf75\x0b\xa85\xfd\xa3\x96\xe3\xbf\x82\x17\xffa\xfc\xd7\x7f<\xff\x0fG,\xdb\xcf2\xda\xe0\xff\x02\x02\xffg\x03\xf8\x7f\x8e\xfb\xbf\xa7~\x7f\x93@\xdb\xe0\xff\x98\x07\xffg\x82\xe7\xff\xb6>\xcf\x95\x83\x7f-\x804\xfd?\x9e\xff+\xc5\xf3\x7f\t\x82\xfe\x7fF\x80\xff\xe7\xb8\xff7\xaa\xdf\xc7\x10\x90\xa6\xff\'\xe9_\x90$\xf0\x7f&x\xfe\xefu\xff\xf9YF\x9b\xea\xff\x90\xff\xc5\x06\xf0\xff\x1c\xf7\xffx\xe7\xbf\xafe\xb4\xa5\xfe\xef\xcd\xff\x01\xff\xf7\x9f\xc6\xef?T\x12\x1f\xfe\xf1\xa7\x8c6\xd4\xff\t\xcc\xffb\x04\xf8?\xf8\x7fb\xf0\xd7\xa722\xaf\xff\x13\x1e\xe6\x7f\xb1\xa1\xc9\xff\x1d\xad\xd4\xafF@\xe6\xf5\x7f\xc2\xc3\xfa\x0f\x8c\x00\xff\x07\xff\x8f\x15z\xea\xf7\xad\x11\x90y\xfd\x9f \x19\xfc\x9f\t)\xf1?T\xa2\xdbfm\xbb\x97\x812\xc8\xff\x95D\xe4~\xff\xa2\x00\xf9\x7f\x8c\x80\xfc\xdf\xe3\xdb\xe0[!E\xff\xbe\xa8?\x8d\xfc_\x117\xd7?\x86\xfc\x0f6\xc8\x88\x1a\xa2\xcek\x82,!\x01\xeb\x04\xf3\xaa"\x8b\xbaI$\xc1\xd4-ST-\rS\x95\xea\xb9\xa3\x88\xdc\xa2Y\xfcoH\xffn\xe72\xd2\x8c\xffI\xed\x7fQ\xc6\xa0\x7f6@\xfc\x87\xf8\x9f:\xf9\xa3\xdd\xcbH3\xfe\'\xeb\x9f\xc8\xd0\xff\xc3\x04\xc3\xd4\x05\x9d\xb7,I#\xa6\x86LI\x93\xdco\x83b\x05!\x15\x19\x92\x865\x99ZT\x11\xf9\xdcQDn\xd1,\xfe;a\xa7\x9c\xb6w\x19\x99\xb4\xffEY\xf4\xf4/B\xfcg\x04\xc4\x7f\x88\xff\t\xfd\xfb\xa2\xfe\xcc\xda\xff\x8d\xfa\xe7!\xfe\xb3A\xb3\x0c\x82\rK$<\x954\xd9\x14T\xc5\x9b{\xc5\xbb\xed\x7f$\x8b\xa6\x8ee$*D\xb5p\xee("\xb78\x96\xff\x1b*A\xc4\x9f2P\x06\xe3\xbf\r\xfa\'\xbc\x00\xeb\x7f\xb2\x01\xc6\x7fs|\xfc7\xa1\x7fD\xb2\x9c\xff\x93\xac\x7f$\xc1\xfa\xffLH\xf6\x7f\xec\x93\xe1\xa6\xe9\xff-\xf2\xbf\xc0\xff\x19\x00\xfe\x0f\xfe\x1f\xd7?F\x1d(\xff\x13#\x98\xff\xc5\x84\x14\xff7\xfc)#\x93\xfa?\x92\xe2\xf1_pc\x11\xf8?\x0b\xc0\xff\xc1\xff\x1b\xfc\xdf\xe8\x08\xf5\xffF\xfdc\xaf\xfd\x0f\xfe\xef?)\xfe\xffu\x9f\xef\x1b\xd0\x86\xfa\xbf@ \xff\x93\r\xe0\xff\xe0\xff\r\xfeou\xa4\xfa\xbf,\x82\xff\xb3 \xd9\xff\xc5\xec\xfa\x7fR\xfe/\x81\xfc\x7fV\x80\xff\x83\xff\xc7\xf5/f\xdb\xff\x93\xf5\x8f\t\xf8?\x13\x92\xfd_\xcen\xff\x7f\xf2\xf7\xcf\xc3\xfa\x0f\x8c\x00\xff\x07\xff\x8f\xeb_\xcev\xff\x7f\xb2\xfe\x11\xac\xff\xc0\x86d\xffWx\x7f\xca\xc8\xc4\xff\x1b\xfb\xff \xff\x87\x15\xe0\xff\xe0\xffq\xfd+|G\xf0\xffF\xfdC\xfe\x0f#\x92\xfd_\xed\x00\xfd?\x89\xf1_\x1e\xea\xffl\x00\xff\x07\xff\x8f\xeb_\xed\x10\xfd?\x89\xf1_\x11\xea\xffLH\xf6\x7f\xad\x03\xf8\x7fc\xfe/\x81\xf5?\x18\x01\xfe\x0f\xfe\x1f\xd7\xbf\xd6!\xfc?1\xff\x07\xf6\x7faC\xb2\xff\xeb\x1d\xa7\xff\x07\xf2?Y\x01\xfe\x0f\xfe\x1f\xd7\xbf\xde\x91\xfa\x7f \xff\x93\x11\xc9\xfeo\x08\xfe\x94\x91\x89\xff7\xe5\xff\xf0\xe0\xffL\x00\xff\x07\xff\x8f\xeb\xdf\x10:\x82\xff7\xe5\xff \xf0\x7f\x16\xa4\xf8\xbf\xe9O\x19i\xfa\x7f\xca\xfe/<\xe4\x7f\xb2\x01\xfc\x1f\xfc\xbf\xc1\xff\xcd\x0e\x94\xff\xcf\x8b\x90\xff\xc9\x84d\xff7}X\xfb\xcb#\x93\xfa\x7fS\xff?\x8c\xff\xb2\x01\xfc\x1f\xfc?\xae\x7f\x93v\x84\xfa\x7f\xd3\xfa_0\xfe\xcb\x84d\xff\x0fG,\xdb\x8f22\xf1\xff\xc6\xfd\x7fd\x01\xfa\x7f\xd8\x00\xfe\x0f\xfe\x1f\xd7\xbf\xa7~\x7f"@&\xfe\xdf\xa8\x7fQ\x82\xfe\x1f&$\xfb\x7f\xa5f\xcc\xf7\xa3\x8c\xb6\xf8?\x86\xfd\xdf\xd9\x00\xfe\x0f\xfe\x1f\xd7\xbf\xa7\xfe\x8e\xe3\xff\x04\xf6\x7fgBJ\xfb\xcf\x9b\x02\xa6\xcb\xa2Nx\x99\xa7\xbc&[\xbc\xa6\xc8\xaa\xae\xab\x9a\x84%\xaa\x8a\x96d\x89X\xff\xda\xcb\xf0\xbf\xf0,\x9ed\xb2\xff\x03\x8f%\x19\xe6\x7f\xb1\x01\xf6\x7f8\xbe\r\xbe\x15R\xf4\xef\x8b\xfa[\xd7?r5\xdfL\xffD\x02\xfd3\xa1&8uK\xdd\xf4\x99\x08\x97\xbe\xfa\xfa\xeb{g\x0e\xaf\xcb\xaf\x9b2\xfb\xd1\x99\xbf\xad\xdf;sF\x8f\x0b\xb6\x0e+\x98\x92_\xb7\xf5\x95\x11\xfb:\xd5]u\xdf\xbe={F\xdc\xba\xff\xb4\xbd\xf7\x1d\xb8"\x18\xf8\xdd\x85}O\xc9\xf6\xc9\x03\xdf\x98\x94\xf1\xbfPIz\x9b\x81eXF\x9a\xf1\xff\xd8\xf8\x1f\x8f\xa1\xff\x8f\x15\x10\xff!\xfe\'\xf4\xef\x8b\xfa[\xd7?O\xa4\xe6\xfa\x17y\xd0?\x13j\x82\xab\x16O\xbd\xf1\\\xdc7p\xf9\xfe\x93\x17\xfe\xf8\xf4\xa2U\xdf\xbb\xfe@p_\xdf\xa3K\x17w[\xb4\xa4\xbf\x1c;R[\xbal\xb6\xab\xb3\xbd\xf5\x0b\xe6\x8c\x9dx\xf6_N\x0e.\x1a2Y\x9c\xbb9\xf6r\xdd\x82\xf9\x9d\xc2\x0f\x9f\xb1e\xdf\xcc\xb5\'\xbf\xd9\xbf\xe7\xec\xa7k\xb6\xc4\x9e\x9b\x98\xbf\xb3\xfb\xf9\xf5\xb3/\xd8\xbcl\xe5\'\xbd\x0b\xe6\xadx\xf0\xa6k\xc5\x0b{\xbf3\xe2\xcb\xb5\xbb\x96}\xfc\xda\xc1Eg\x8f|\xf8\xee/\x9e\x91\x95O\xaf\xbc\xe3\xd0\xd2\xff\xfc\xfb\xcc\xdd\xb5\x87\xfb\x95\xddT?r\xd2\x80?\x9e\xd6m\xfc\xba]\x0b\xaf\xa8{V\xaf\x1a6!\xef0\xee:o\xc1\xe69G\x83\x83o\x9d\xfcT\xb6\xaf\xd2\xf1KJ\xfeg\xa8\xc4\xa0\nV\x04L\xa9dI\xa6\xc9\xbbj\'\xba\xa5QDM\x1d!\xcb0\x14\x9eb\xa4dXF&\xed\xffx\xfe\xa7\x1b\xffa\xff7F@\xfc\x87\xf8\x9f\xd0\xbf/\xeao]\xff\x98\xe7\x9b\xeb_\x14\t\xe8\x9f\x055\xc1\x11\xc3\xce/\x9e\x8d\x04\x03\x11\x84\x04|\xe1\xe6\xadS\xa7<\xf4\xea\x9f\x8a\xb5\xeb\xfbT\xf7\xea\xf7\xf4\x07E\x0b/\xb9\xeb\xf9\x93\x0e=\x12#RU\xc9\xed"\x0et\xba\xf6\xfd\xed\x83~\xfe\xc5\x84~\x1f\xbd\xa8>;\xbc\xe2\x91\xddw>W{h\x91\xb9\xfc\xba\xc5(\xf0\xd4Yg<\x93\xedO\x04dB\xca\xfc\xbfP\x89F\xb1$\xf3\xaa"Z\x9a\x8a4\xa4\x8a\x9e \t\xc2\xc4\xb0D\xc5\xd4\\\xa5\x1a\xb2$eXF&\xf1?>\xff\x8f\xc7n\x05\x00\xf4\xcf\x04\x88\xff\x10\xff\x13\xfa\xf7E\xfdi\xb4\xff\x91\xd4L\xff\xeeqP\xffgBMp\xcd\xcb\xa3{oD\xbd\xc6j\xfbVn<-\xf0\xc2\xa2\xd7\xce\xee9`\x88\xd4\xfb\xbd\'#g\xdc6t\xe9\x8aw\xce\xee2\xe9\x07W\xed\xfa\xec\xbe=+\x87\xbf\xdbw\xfa\xeb\xb3\xee\xb1\xf5\xeb\xdfZ7\xbeb\xea\xd0\x93f\\;\xbev\xd0]G\x95\xd5w\x0f\xe5&9W\xffy]\xffQ\xb7\xac\xfd\xcf\x11S-\xdf}\xd2\xdc\xd8\xce\xc3!\xba}C\xff\xd2u\x83\xae\x1e\xf6\x87\xb7\x02\xcf\x8f]\xb8\x1fK\x95\x9f\xae\xfa\xec\x82g>x\xe0G\x03>ZR\xfe\xc8\xc7\x8f\xbdu\xc6\xe1Uco\xcc\xf6U\xc8]R\xd6\x7fq\xdb\xffim\x06\x9ea\x19\x99\xc4\xff\xc6\xf1?\x1e\xe2?# \xfeC\xfcO\xe8\xdf\x17\xf5\xa7\xdd\xff\x9f\xac\x7f$\x81\xfe\x99\xe0\xc6\xff\xc5\xe3zo\xe4\xfa\x06F\x1f\xca\x1b\xb3\xfa\xb2\xca9\x1c~q\xd3c\xbf\xb8\xf4\xf65\x83\xd7\xbd\xc0}\xb9\xfb\xc5\xc2\x9a\xe5\xbb\xb6V^\xbec\xfb\xba\t\xa3\x0e\x0f\xb97xg\xe7\r\xff\xd8\xbci\xd0\x9b#G\xfd\xe6\x9aa\x93\xb6\xd4]\xf5\xe8\x98\xcbn\xac\xaf\xf9\xe4\xde!sv\xd4/]V\xff\xe6\xbb\xd7M\x0b\xf6\xd8x\xcd_\x03=\xba\xa9}\xc6,\xf9\xfd\xedo+\xc3\x8f\x1c\xde \x1d\x1d:\xea\xb5\xd8K\x87\xc3\xff\\s\xe0O\xdf?u\xc3\x15o\xcfYW?\xfc!\xb4j\xde\x8a\x87w\xae\xec|U\xf7m]\x16v\xe9\xbe\xfa\xf3\xf5;\xf7\x16\xde\xf0\xe4+\x8f\x17/u\n\x8f\x0e\xfb\xfb\tS\x82\xd3\xcf\xcc\xf6U:~IY\xff3T\xe2\xd6\xfe\x91i\x8a\x94\x08T\x93EE\x96-]\x95\x14\xa4\x9a*5\xb0*ID\xe1\r\x9c\xe921mh\xff\x0b\x02\xf4\xff\xb1\x01\xe2?\xc4\xff\x84\xfe}Q\x7f\x1a\xf9\x7f\x12i\xd1\xff\x07\xe3\xfflH\xf4\xffK-\xfa\xff\x7f\xb9\x01\xbfTp\xf39\x93\xf7>1=Rvt\xcd\xac];\xd7.\xdd\x10\x18\xa1\xf7\xe9\x9d\xeds\x06\xda\x8f\x94\xfd\x1fB%\xa2 j\xb2D\x88\xabul\x18\x02\xa6\x061\xa8\xa6\x13\xcdB\xba\x8a\x91I\x04\xac\x89~\xb6\xff\x13\xf1\x1f\xc6\xff\x19\x01\xf1\x1f\xe2\x7fB\xff\xbe\xa8?\xb3\xf1\xffD\xfc\x87\xf1\x7f6|\xf5\xf8\xff\xff\x8c\xffC\xba\x8d]=c\xee\xf2M\xe8\xd9\xb2\x8do+\xfb/Y\xf3\xe1\'#\x05\xc5~f\xc9\xb4C\xaf\x9e\xd8-\xb0b\xe1\xb7\x0fd\xfb\x13\x01\x99\x90\xb2\xff_\xa8\x84\x1a\xa2\xcek\x82,\xb9?\x05\x9d`^UdQ7\x89$\x98\xbae\x8a\xaa\xa5a\xaaR=\xc322\x89\xff\x89\xfc\x1f\x18\xffc\x04\xc4\x7f\x88\xff\t\xfd\xfb\xa2\xfet\xfa\xff\xe5\xe6\xfa\x17 \xfe\xb3\xa1&\xb8f[\xb1\xd7\xff?V\xdb\xb1\xf2\'\'\x94u\xdbR\xd2\xcf\x986w\xc1\xf5\x7fC\x8f\xdf7\xb3\xd7\xf6k\xd7\xef\xa8\xe9z\x89\xfd\xd9\xde\x0b\x0b\x06W\xdf\xffr\xe5\x81E\x97m\x1f{\xe6\xac\xfe\'?654\xf1;k\xa5\x8b\xce\xed\xb6\xb8\xdf\xd8\xef\xe6-?\xa5\xcb\xbf6\xbd8\xe7\x8e[&^\xbc\xed\x03\xfc\xc6\xcf\x06r7\xffE9\xa1\xdb\xad\xf7\x98\xe7\x8d_#\xd6\xee\xef\xf2\xd1\xc2\xfb\x8b\xdf\x11\n>\xff\xdczg\xd7\xfc\x97\x0f\xce=\xb8\xe5\x92\x07\x96\\Tq\xe9\x13t\xe3E\x15\x87&<\xa0\x91\xe7~Z=\xf1\xac\xe7:\xf78\xf2\xd0\x95_\x9ep\xe2\xfa\xae\xeb\xef\xfc\xd5\xcayW\xdf\xd4gu\xaf\x0b\xc6d\xfb2\x1d\xb7\xa4\xec\xff\xee\xb6\xffe\xe2\xc6^,\x9a&\x11UY\xd7$J\x90F\x04\xd9\x12U\x83Wt\xf7\x9f)\xe0L\x97\tnC\xfc\x07\xfd\xb3\x02\xe2?\xc4\xff\x84\xfe}Q\x7f:\xf3\xff[\xe4\xffc\x02\xfb\xbf1\xa1i\xfe\xbf\xd6r\xfe\x7fe\xe1\xf9\xc5\x05u[\xa7\x16\xee\xebTW\xbbg\xff\xa0\xe1M\x93\xffk\xf6\xf5~,\xdbg\x0e\xb4\x07\xc7\xf4\x8f\xbd\xf8\xcfK\xbc!h\x94J\x84\x12\xd1R\x88\xac#^\x95\x10\x96\x04\xc3@\x82\x88Ud\x11%\xd3e\xa2\xd3\x8c\xff\xc9\xf3\x7f\x05X\xff\x8d\x11\x10\xff!\xfe\'\xf4\xef\x8b\xfa\xd3\x19\xff\x97\x9b\xeb\x1f#X\xff\x87\tM\xf1\xdfl\x19\xff?.\xac\x9b\\\xf0~\xa7\x1b\x16\x1c[\xf9\xe7\x8dX00\xa1\xf4[7e\xfb\xb4\x81v"I\xff\x86\xb7\x05\x84\xa2\x1an\x1d\\B\x86\xc8\xf3\xc4\x90\x89!\x99\xa2([&/\x89\x82)\x9b\x92&\x13\xd5\xcf\xf6\x7fb\xfc\x1f\xf2\x7f\x19\x01\xf1\x1f\xe2\x7fB\xff\xbe\xa8?\x9d\xf6\xbf\xd0r\xfc\x1f\xea\xffLh\x8a\xff\xb4\x95\xf6\x7f\xea\xea\x7f7\x0c\xee3(\xdb\xa7\x0e\xb4\x03I\xfa\xf7\xc6\xff\x05\x99Z\x82\xe6\xea]\xb3\x0c/\xe1W\x90y\xacY:\xa2\xba\xa8*\x16\xafh\x82@e\x9f\xd6\xffM\xae\xffK<\x8c\xff\xb3\x01\xe2?\xc4\xff\x84\xfe}Q\x7f\x1a\xf9\x7fR\x8b\xf5\xff\x08\x86\xf1?&$\xf2\xff\x88\xa4\xa5\x95\x008C\xfcb\xf0\xe9\xf7O\xe0\xc4\x83\xf3\x8a.\xfe\xe7\xcc\xbb6\xad\x9f%\x14\x1b\xd3\xc6<\x7f\xa6\xf2\xde\xd4\xbbo\x08\xf6\x1dz\xcdmhk\xe1\xf2Jy\xdb\x17\xb3\xc3\x0b\x8en\xeb\xb5m\x85=\xe8\xb5Q\xce\xcf\x06\x1c|a\xcd\x94Kipw?\xb2:\xdb\x9f\x1aHpL\xff\x88x\xf3\xff\rU\x93-Y\xc3\xbaI-E&\x82\xa9\x12\xd3\xd25\xb7\t\xa0h\xbcb\xf2\x9a\xaec?\xd7\xffk\x98\xff\xeb-\x00\n\xfag\x02\xc4\x7f\x88\xff\t\xfd\xfb\xa2\xfet\xf2\xff\x85\xe6\xf3\xffe\x98\xff\xcb\x86\xaf\xce\xff\x7fb\xc7\xe3\xa3w\xde\x7f\xa0\xfe\xe0\xf4\x11\xc3\xab_9\x7f\xeb\x8a#\x1f>x\xf8G\xfd:s3\x86\x86\x8a\xf5e%\xe4\xbd\xc8\xcaC\x0fn\xff\xf4\xc8\xaa\xd3W\xca\xbb\'\xff\xba\xf6@\x8f\xce\x81q{\xce:\x92\xed\x8f\x04d@\xa8a\xdf\xbfP\t\xad1\xca\xab\xfc\xd9\x01\xda\xd5\x83\xdb\x98H\xb3\xff\x1f\xf6\x7fc\x0b\xc4\xff\x1c\x8f\xffq\xfd\xfb\xa8\xfe\xd6\xf5/H-\xf7\x7fCP\xffg\xc2@\xae4\xec\x14\x94\xc7\n\xbc\r\x12c\\A\x81\xed\xb8\x92\xf1\xee4\xfe$\n\xac\xa8]1:\xe4\x1e\x95\xf2K\xc9\x1b\xc8M\x0bG\xdcW8e\x9a\xc3y\xd7\xd0\xe1\xaa\xc3N\x19w\xce\xc0s8-J9W\xd5\x154\xe2\xc4B\xee\x91\x13\xed(\xa7q\x95Q\xdb\xabir\x15v\xcc)\xaf\xe5\xc2\x11\xee\xbc|\xf7\xe5\x94\xb3lO\xac\xe1H)WmW\x95\x9b\x9cN\xdd\xa3Km\xdb\xe4b\xd4\xe1l\xcb}\x87\xc6R\xb9JW\xaa4\x1a\x89qC\xab"\x8d%xoQ\xc1\x85-\xae\xd6\xae\xe2\xaa5\xef\t\x9bsm#\xfe\xfc\xb0"\xf7\xc5\xc3Csl\xedr\xef\xce\x0fsG\xd8\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00@N\xf3_\xdck4;\x00@\x01\x00'

class TestJekyll (TestCase):

    def test_good_files(self):
        front = dict(title='Greeting'.encode('rotunicode'))
        body, file = u'World: Hello.'.encode('rotunicode'), StringIO()

        jekyll_functions.dump_jekyll_doc(front, body, file)
        _front, _body = jekyll_functions.load_jekyll_doc(file)

        self.assertEqual(_front['title'], front['title'])
        self.assertEqual(_body, body)

        file.seek(0)
        file.read(4) == '---\n'

    def test_bad_files(self):
        file = StringIO('Missing front matter')

        with self.assertRaises(Exception):
            jekyll_functions.load_jekyll_doc(file)

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
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)

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
        repo_functions.save_working_file(*args)

        #
        # See if the branch made it to clone 2
        #
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)

        self.assertTrue(name in self.clone2.branches)
        self.assertEquals(branch2.commit.hexsha, branch1.commit.hexsha)
        self.assertEquals(branch2.commit.message, message)

    def test_new_file(self):
        ''' Make a new file and delete an old file in a clone, verify that it appears in the other.
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)

        self.assertTrue(name in self.clone1.branches)
        self.assertTrue(name in self.origin.branches)

        #
        # Make a new file in the branch and push it.
        #
        branch1.checkout()

        edit_functions.create_new_page(self.clone1, '', 'hello.md',
                                       dict(title='Hello'), 'Hello hello.')

        args = self.clone1, 'hello.md', str(uuid4()), branch1.commit.hexsha, 'master'
        repo_functions.save_working_file(*args)

        #
        # Delete an existing file in the branch and push it.
        #
        message = str(uuid4())

        edit_functions.delete_file(self.clone1, '', 'index.md')

        args = self.clone1, 'index.md', message, branch1.commit.hexsha, 'master'
        repo_functions.save_working_file(*args)

        #
        # See if the branch made it to clone 2
        #
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)

        self.assertTrue(name in self.clone2.branches)
        self.assertEquals(branch2.commit.hexsha, branch1.commit.hexsha)
        self.assertEquals(branch2.commit.message, message)
        self.assertEquals(branch2.commit.author.email, self.session['email'])
        self.assertEquals(branch2.commit.committer.email, self.session['email'])

        branch2.checkout()

        with open(join(self.clone2.working_dir, 'hello.md')) as file:
            front, body = jekyll_functions.load_jekyll_doc(file)

            self.assertEquals(front['title'], 'Hello')
            self.assertEquals(body, 'Hello hello.')

        self.assertFalse(exists(join(self.clone2.working_dir, 'index.md')))

    def test_move_file(self):
        ''' Change the path of a file.
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)

        self.assertTrue(name in self.clone1.branches)
        self.assertTrue(name in self.origin.branches)

        #
        # Rename a file in the branch.
        #
        branch1.checkout()

        args = self.clone1, 'index.md', 'hello/world.md', branch1.commit.hexsha, 'master'
        repo_functions.move_existing_file(*args)

        #
        # See if the new file made it to clone 2
        #
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)
        branch2.checkout()

        self.assertTrue(exists(join(self.clone2.working_dir, 'hello/world.md')))
        self.assertFalse(exists(join(self.clone2.working_dir, 'index.md')))

    def test_content_merge(self):
        ''' Test that non-conflicting changes on the same file merge cleanly.
        '''
        branch1 = repo_functions.start_branch(self.clone1, 'master', 'title')
        branch2 = repo_functions.start_branch(self.clone2, 'master', 'body')

        branch1.checkout()
        branch2.checkout()

        with open(self.clone1.working_dir + '/index.md') as file:
            front1, _ = jekyll_functions.load_jekyll_doc(file)

        with open(self.clone2.working_dir + '/index.md') as file:
            _, body2 = jekyll_functions.load_jekyll_doc(file)

        #
        # Show that only the title branch title is now present on master.
        #
        repo_functions.complete_branch(self.clone1, 'master', 'title')

        with open(self.clone1.working_dir + '/index.md') as file:
            front1b, body1b = jekyll_functions.load_jekyll_doc(file)

        self.assertEqual(front1b['title'], front1['title'])
        self.assertNotEqual(body1b, body2)

        #
        # Show that the body branch body is also now present on master.
        #
        repo_functions.complete_branch(self.clone2, 'master', 'body')

        with open(self.clone2.working_dir + '/index.md') as file:
            front2b, body2b = jekyll_functions.load_jekyll_doc(file)

        self.assertEqual(front2b['title'], front1['title'])
        self.assertEqual(body2b, body2)
        self.assertTrue(self.clone2.commit().message.startswith('Merged work from'))

    def test_content_merge_extra_change(self):
        ''' Test that non-conflicting changes on the same file merge cleanly.
        '''
        branch1 = repo_functions.start_branch(self.clone1, 'master', 'title')
        branch2 = repo_functions.start_branch(self.clone2, 'master', 'body')

        branch1.checkout()
        branch2.checkout()

        with open(self.clone1.working_dir + '/index.md') as file:
            front1, _ = jekyll_functions.load_jekyll_doc(file)

        with open(self.clone2.working_dir + '/index.md') as file:
            front2, body2 = jekyll_functions.load_jekyll_doc(file)

        #
        # Show that only the title branch title is now present on master.
        #
        repo_functions.complete_branch(self.clone1, 'master', 'title')

        with open(self.clone1.working_dir + '/index.md') as file:
            front1b, body1b = jekyll_functions.load_jekyll_doc(file)

        self.assertEqual(front1b['title'], front1['title'])
        self.assertNotEqual(body1b, body2)

        #
        # Show that the body branch body is also now present on master.
        #
        edit_functions.update_page(self.clone2, 'index.md',
                                   front2, 'Another change to the body')

        repo_functions.save_working_file(self.clone2, 'index.md', 'A new change',
                                         self.clone2.commit().hexsha, 'master')

        #
        # Show that upstream changes from master have been merged here.
        #
        with open(self.clone2.working_dir + '/index.md') as file:
            front2b, body2b = jekyll_functions.load_jekyll_doc(file)

        self.assertEqual(front2b['title'], front1['title'])
        self.assertEqual(body2b.strip(), 'Another change to the body')
        self.assertTrue(self.clone2.commit().message.startswith('Merged work from'))

    def test_multifile_merge(self):
        ''' Test that two non-conflicting new files merge cleanly.
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)

        #
        # Make new files in each branch and save them.
        #
        branch1.checkout()
        branch2.checkout()

        edit_functions.create_new_page(self.clone1, '', 'file1.md',
                                       dict(title='Hello'), 'Hello hello.')

        edit_functions.create_new_page(self.clone2, '', 'file2.md',
                                       dict(title='Goodbye'), 'Goodbye goodbye.')

        #
        # Show that the changes from the first branch made it to origin.
        #
        args1 = self.clone1, 'file1.md', '...', branch1.commit.hexsha, 'master'
        commit1 = repo_functions.save_working_file(*args1)

        self.assertEquals(self.origin.branches[name].commit, commit1)
        self.assertEquals(self.origin.branches[name].commit.author.email, self.session['email'])
        self.assertEquals(self.origin.branches[name].commit.committer.email, self.session['email'])
        self.assertEquals(commit1, branch1.commit)

        #
        # Show that the changes from the second branch also made it to origin.
        #
        args2 = self.clone2, 'file2.md', '...', branch2.commit.hexsha, 'master'
        commit2 = repo_functions.save_working_file(*args2)

        self.assertEquals(self.origin.branches[name].commit, commit2)
        self.assertEquals(self.origin.branches[name].commit.author.email, self.session['email'])
        self.assertEquals(self.origin.branches[name].commit.committer.email, self.session['email'])
        self.assertEquals(commit2, branch2.commit)

        #
        # Show that the merge from the second branch made it back to the first.
        #
        branch1b = repo_functions.start_branch(self.clone1, 'master', name)

        self.assertEquals(branch1b.commit, branch2.commit)
        self.assertEquals(branch1b.commit.author.email, self.session['email'])
        self.assertEquals(branch1b.commit.committer.email, self.session['email'])

    def test_same_branch_conflict(self):
        ''' Test that a conflict in two branches appears at the right spot.
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)

        #
        # Make new files in each branch and save them.
        #
        branch1.checkout()
        branch2.checkout()

        edit_functions.create_new_page(self.clone1, '', 'conflict.md',
                                       dict(title='Hello'), 'Hello hello.')

        edit_functions.create_new_page(self.clone2, '', 'conflict.md',
                                       dict(title='Goodbye'), 'Goodbye goodbye.')

        #
        # Show that the changes from the first branch made it to origin.
        #
        args1 = self.clone1, 'conflict.md', '...', branch1.commit.hexsha, 'master'
        commit1 = repo_functions.save_working_file(*args1)

        self.assertEquals(self.origin.branches[name].commit, commit1)
        self.assertEquals(commit1, branch1.commit)

        #
        # Show that the changes from the second branch conflict with the first.
        #
        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            args2 = self.clone2, 'conflict.md', '...', branch2.commit.hexsha, 'master'
            commit2 = repo_functions.save_working_file(*args2)

        self.assertEqual(conflict.exception.remote_commit, commit1)

        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)

        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].a_blob.name, 'conflict.md')
        self.assertEqual(diffs[0].b_blob.name, 'conflict.md')

    def test_upstream_pull_conflict(self):
        ''' Test that a conflict in two branches appears at the right spot.
        '''
        name1, name2 = str(uuid4()), str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name1)
        branch2 = repo_functions.start_branch(self.clone2, 'master', name2)

        #
        # Make new files in each branch and save them.
        #
        branch1.checkout()
        branch2.checkout()

        edit_functions.create_new_page(self.clone1, '', 'conflict.md',
                                       dict(title='Hello'), 'Hello hello.')

        edit_functions.create_new_page(self.clone2, '', 'conflict.md',
                                       dict(title='Goodbye'), 'Goodbye goodbye.')

        #
        # Show that the changes from the first branch made it to origin.
        #
        args1 = self.clone1, 'conflict.md', '...', branch1.commit.hexsha, 'master'
        commit1 = repo_functions.save_working_file(*args1)

        self.assertEquals(self.origin.branches[name1].commit, commit1)
        self.assertEquals(commit1, branch1.commit)

        #
        # Merge the first branch to master.
        #
        commit2 = repo_functions.complete_branch(self.clone1, 'master', name1)
        self.assertFalse(name1 in self.origin.branches)

        #
        # Show that the changes from the second branch conflict with the first.
        #
        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            args2 = self.clone2, 'conflict.md', '...', branch2.commit.hexsha, 'master'
            repo_functions.save_working_file(*args2)

        self.assertEqual(conflict.exception.remote_commit, commit2)

        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)

        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].a_blob.name, 'conflict.md')
        self.assertEqual(diffs[0].b_blob.name, 'conflict.md')

    def test_upstream_push_conflict(self):
        ''' Test that a conflict in two branches appears at the right spot.
        '''
        name1, name2 = str(uuid4()), str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name1)
        branch2 = repo_functions.start_branch(self.clone2, 'master', name2)

        #
        # Make new files in each branch and save them.
        #
        branch1.checkout()
        branch2.checkout()

        edit_functions.create_new_page(self.clone1, '', 'conflict.md',
                                       dict(title='Hello'), 'Hello hello.')

        edit_functions.create_new_page(self.clone2, '', 'conflict.md',
                                       dict(title='Goodbye'), 'Goodbye goodbye.')

        #
        # Push changes from the two branches to origin.
        #
        args1 = self.clone1, 'conflict.md', '...', branch1.commit.hexsha, 'master'
        commit1 = repo_functions.save_working_file(*args1)

        args2 = self.clone2, 'conflict.md', '...', branch2.commit.hexsha, 'master'
        commit2 = repo_functions.save_working_file(*args2)

        #
        # Merge the two branches to master; show that second merge will fail.
        #
        repo_functions.complete_branch(self.clone1, 'master', name1)
        self.assertFalse(name1 in self.origin.branches)

        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            repo_functions.complete_branch(self.clone2, 'master', name2)

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
        branch1 = repo_functions.start_branch(self.clone1, 'master', 'title')
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)

        #
        # Add goner.md in branch1.
        #
        branch1.checkout()

        edit_functions.create_new_page(self.clone1, '', 'goner.md',
                                       dict(title=name), 'Woooo woooo.')

        args = self.clone1, 'goner.md', '...', branch1.commit.hexsha, 'master'
        commit = repo_functions.save_working_file(*args)

        #
        # Change index.md in branch2 so it conflicts with title branch.
        #
        branch2.checkout()

        edit_functions.update_page(self.clone2, 'index.md',
                                   dict(title=name), 'Hello hello.')

        args = self.clone2, 'index.md', '...', branch2.commit.hexsha, 'master'
        commit = repo_functions.save_working_file(*args)

        #
        # Merge the original title branch, fail to merge our conflicting branch.
        #
        repo_functions.complete_branch(self.clone1, 'master', 'title')

        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            repo_functions.complete_branch(self.clone2, 'master', name)

        self.assertEqual(conflict.exception.local_commit, commit)

        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)

        self.assertEqual(len(diffs), 2)
        self.assertTrue(diffs[0].a_blob.name in ('index.md', 'goner.md'))
        self.assertTrue(diffs[1].a_blob.name in ('index.md', 'goner.md'))

        #
        # Merge our conflicting branch and clobber the default branch.
        #
        repo_functions.clobber_default_branch(self.clone2, 'master', name)

        with open(join(self.clone2.working_dir, 'index.md')) as file:
            front, body = jekyll_functions.load_jekyll_doc(file)

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
        branch1 = repo_functions.start_branch(self.clone1, 'master', 'title')
        branch2 = repo_functions.start_branch(self.clone2, 'master', name)

        #
        # Change index.md in branch2 so it conflicts with title branch.
        # Also add goner.md, which we'll later want to disappear.
        #
        branch2.checkout()

        edit_functions.update_page(self.clone2, 'index.md',
                                   dict(title=name), 'Hello hello.')

        edit_functions.create_new_page(self.clone2, '', 'goner.md',
                                       dict(title=name), 'Woooo woooo.')

        args = self.clone2, 'index.md', '...', branch2.commit.hexsha, 'master'
        commit = repo_functions.save_working_file(*args)

        args = self.clone2, 'goner.md', '...', branch2.commit.hexsha, 'master'
        commit = repo_functions.save_working_file(*args)

        #
        # Merge the original title branch, fail to merge our conflicting branch.
        #
        repo_functions.complete_branch(self.clone1, 'master', 'title')

        with self.assertRaises(repo_functions.MergeConflict) as conflict:
            repo_functions.complete_branch(self.clone2, 'master', name)

        self.assertEqual(conflict.exception.local_commit, commit)

        diffs = conflict.exception.remote_commit.diff(conflict.exception.local_commit)

        self.assertEqual(len(diffs), 2)
        self.assertTrue(diffs[0].b_blob.name in ('index.md', 'goner.md'))
        self.assertTrue(diffs[1].b_blob.name in ('index.md', 'goner.md'))

        #
        # Merge our conflicting branch and abandon it to the default branch.
        #
        repo_functions.abandon_branch(self.clone2, 'master', name)

        with open(join(self.clone2.working_dir, 'index.md')) as file:
            front, body = jekyll_functions.load_jekyll_doc(file)

        self.assertNotEqual(front['title'], name)
        self.assertFalse(name in self.origin.branches)

        # If goner.md is still around, then the branch wasn't fully abandoned.
        self.assertFalse(exists(join(self.clone2.working_dir, 'goner.md')))
        self.assertTrue(self.clone2.commit().message.startswith('Abandoned work from'))

    def test_peer_review(self):
        ''' Change the path of a file.
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)

        #
        # Make a commit.
        #
        environ['GIT_AUTHOR_NAME'] = 'Jim Content Creator'
        environ['GIT_COMMITTER_NAME'] = 'Jim Content Creator'
        environ['GIT_AUTHOR_EMAIL'] = 'creator@example.com'
        environ['GIT_COMMITTER_EMAIL'] = 'creator@example.com'

        branch1.checkout()
        self.assertFalse(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))

        edit_functions.update_page(self.clone1, 'index.md',
                                   dict(title=name), 'Hello you-all.')

        repo_functions.save_working_file(self.clone1, 'index.md', 'I made a change',
                                         self.clone1.commit().hexsha, 'master')

        self.assertTrue(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), 'creator@example.com')

        #
        # Approve the work as someone else.
        #
        environ['GIT_AUTHOR_NAME'] = 'Joe Reviewer'
        environ['GIT_COMMITTER_NAME'] = 'Joe Reviewer'
        environ['GIT_AUTHOR_EMAIL'] = 'reviewer@example.com'
        environ['GIT_COMMITTER_EMAIL'] = 'reviewer@example.com'

        repo_functions.mark_as_reviewed(self.clone1)

        self.assertFalse(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertTrue(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), None)

        #
        # Make another commit.
        #
        edit_functions.update_page(self.clone1, 'index.md',
                                   dict(title=name), 'Hello you there.')

        repo_functions.save_working_file(self.clone1, 'index.md', 'I made a change',
                                         self.clone1.commit().hexsha, 'master')

        self.assertTrue(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), 'reviewer@example.com')

        #
        # Approve the work as someone else.
        #
        environ['GIT_AUTHOR_NAME'] = 'Jane Reviewer'
        environ['GIT_COMMITTER_NAME'] = 'Jane Reviewer'
        environ['GIT_AUTHOR_EMAIL'] = 'reviewer@example.org'
        environ['GIT_COMMITTER_EMAIL'] = 'reviewer@example.org'

        repo_functions.mark_as_reviewed(self.clone1)

        self.assertFalse(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertTrue(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), None)

    def test_peer_rejected(self):
        '''
        '''
        name = str(uuid4())
        branch1 = repo_functions.start_branch(self.clone1, 'master', name)

        #
        # Make a commit.
        #
        environ['GIT_AUTHOR_NAME'] = 'Jim Content Creator'
        environ['GIT_COMMITTER_NAME'] = 'Jim Content Creator'
        environ['GIT_AUTHOR_EMAIL'] = 'creator@example.com'
        environ['GIT_COMMITTER_EMAIL'] = 'creator@example.com'

        branch1.checkout()
        self.assertFalse(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))

        edit_functions.update_page(self.clone1, 'index.md',
                                   dict(title=name), 'Hello you-all.')

        repo_functions.save_working_file(self.clone1, 'index.md', 'I made a change',
                                         self.clone1.commit().hexsha, 'master')

        self.assertTrue(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_rejected(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), 'creator@example.com')

        #
        # Approve the work as someone else.
        #
        environ['GIT_AUTHOR_NAME'] = 'Joe Reviewer'
        environ['GIT_COMMITTER_NAME'] = 'Joe Reviewer'
        environ['GIT_AUTHOR_EMAIL'] = 'reviewer@example.com'
        environ['GIT_COMMITTER_EMAIL'] = 'reviewer@example.com'

        repo_functions.provide_feedback(self.clone1, 'This sucks.')

        self.assertFalse(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertTrue(repo_functions.is_peer_rejected(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), None)

        #
        # Make another commit.
        #
        edit_functions.update_page(self.clone1, 'index.md',
                                   dict(title=name), 'Hello you there.')

        repo_functions.save_working_file(self.clone1, 'index.md', 'I made a change',
                                         self.clone1.commit().hexsha, 'master')

        self.assertTrue(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_rejected(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), 'reviewer@example.com')

        #
        # Approve the work as someone else.
        #
        environ['GIT_AUTHOR_NAME'] = 'Jane Reviewer'
        environ['GIT_COMMITTER_NAME'] = 'Jane Reviewer'
        environ['GIT_AUTHOR_EMAIL'] = 'reviewer@example.org'
        environ['GIT_COMMITTER_EMAIL'] = 'reviewer@example.org'

        repo_functions.provide_feedback(self.clone1, 'This still sucks.')

        self.assertFalse(repo_functions.needs_peer_review(self.clone1, 'master', name))
        self.assertFalse(repo_functions.is_peer_approved(self.clone1, 'master', name))
        self.assertTrue(repo_functions.is_peer_rejected(self.clone1, 'master', name))
        self.assertEqual(repo_functions.ineligible_peer(self.clone1, 'master', name), None)

        #

        (email2, message2), (email1, message1) = repo_functions.get_rejection_messages(self.clone1, 'master', name)

        self.assertEqual(email1, 'reviewer@example.com')
        self.assertTrue('This sucks.' in message1)
        self.assertEqual(email2, 'reviewer@example.org')
        self.assertTrue('This still sucks.' in message2)

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
        environ['PROFILE_ID'] = '12345678'
        environ['CLIENT_ID'] = 'client_id'
        environ['CLIENT_SECRET'] = 'meow_secret'

        random.choice = MagicMock(return_value="P")

        self.app = app.test_client()

    def persona_verify(self, url, request):
        if url.geturl() == 'https://verifier.login.persona.org/verify':
            return response(200, '''{"status": "okay", "email": "user@example.com"}''', headers=dict(Link='<https://api.github.com/user/337792/repos?page=1>; rel="prev", <https://api.github.com/user/337792/repos?page=1>; rel="first"'))

        else:
            raise Exception('Asked for unknown URL ' + url.geturl())

    def mock_google_authorization(self, url, request):
        if 'https://accounts.google.com/o/oauth2/auth' in url.geturl():
            content = {'access_token': 'meowser_token', 'token_type': 'meowser_type', 'refresh_token': 'refresh_meows', 'expires_in': 3920,}
            return response(200, content)

        else:
            raise Exception('Asked for unknown URL ' + url.geturl())

    def mock_successful_google_callback(self, url, request):
        if 'https://accounts.google.com/o/oauth2/token' in url.geturl():
            content = {'access_token': 'meowser_token', 'token_type': 'meowser_type', 'refresh_token': 'refresh_meows', 'expires_in': 3920,}
            return response(200, content)

        else:
            raise Exception('Asked for unknown URL ' + url.geturl())

    def mock_failed_google_callback(self, url, request):
        if 'https://accounts.google.com/o/oauth2/token' in url.geturl():
            return response(500)

        else:
            raise Exception('Asked for unknown URL ' + url.geturl())

    def mock_google_analytics(self, url, request):
        start_date = (date.today() - timedelta(days=7)).isoformat()
        end_date = date.today().isoformat()
        url_string = url.geturl()

        if 'ids=ga%3A12345678' in url_string and 'end-date='+end_date in url_string and 'start-date='+start_date in url_string and 'filters=ga%3ApagePathhello.md' in url_string:
            return response(200, '''{"ga:previousPagePath": "/about/", "ga:pagePath": "/lib/", "ga:pageViews": "12", "ga:avgTimeOnPage": "56.17", "ga:exiteRate": "43.75"}''')

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

        with HTTMock(self.mock_google_analytics):
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

    def test_google_callback_is_successful(self):
        ''' Ensure we are redirected to the authorize-complete page
            when we successfully auth with google
        '''
        with HTTMock(self.persona_verify):
            self.app.post('/sign-in', data={'email': 'erica@example.com'})

        with HTTMock(self.mock_google_authorization):
            self.app.post('/authorize')

        with HTTMock(self.mock_successful_google_callback):
            response = self.app.get('/callback?state=PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP&code=code')

        self.assertTrue('authorization-complete' in response.location)

    def test_google_callback_fails(self):
        ''' Ensure we are redirected to the authorize-failed page
            when we fail to auth with google
        '''
        with HTTMock(self.persona_verify):
            self.app.post('/sign-in', data={'email': 'erica@example.com'})

        with HTTMock(self.mock_google_authorization):
            self.app.post('/authorize')

        with HTTMock(self.mock_failed_google_callback):
            response = self.app.get('/callback?state=PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP&code=code')

        self.assertTrue('authorization-failed' in response.location)

    def tearDown(self):
        rmtree(app.config['WORK_PATH'])
        rmtree(app.config['REPO_PATH'])

if __name__ == '__main__':
    main()
