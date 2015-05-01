# -*- coding: utf-8 -*-

'''
--------------------------------------------------------------------------------------
project_conf.py
--------------------------------------------------------------------------------------
Configuration settings that detail EC2 instances. Note that we are not using
the built-in env from fabric.api -- there are no official recommendations on
best practice. See: http://lists.gnu.org/archive/html/fab-user/2013-11/msg00006.html
'''

import os
import os.path

fabconf = {}

#  Do not edit
fabconf['FAB_CONFIG_PATH'] = os.path.dirname(__file__)

# Project name
fabconf['PROJECT_NAME'] = os.environ.get('PROJECT_NAME', 'chime')

# Username for connecting to EC2 instaces - Do not edit unless you have a reason to
fabconf['SERVER_USERNAME'] = 'ubuntu'

# Full local path for .ssh
fabconf['SSH_PATH'] = os.environ.get('SSH_PATH', '~/.ssh')

# Name of the private key file you use to connect to EC2 instances
fabconf['EC2_KEY_NAME'] = os.environ.get('EC2_KEY_NAME')

# Don't edit. Full path of the ssh key you use to connect to EC2 instances
fabconf['SSH_PRIVATE_KEY_PATH'] = os.environ.get(
    'SSH_PRIVATE_KEY_PATH',
    '{path}/{name}'.format(path=fabconf.get('SSH_PATH'), name=fabconf.get('EC2_KEY_NAME'))
)

# SSL certificate and key location
fabconf['SSL_CERT_PATH'] = os.environ.get('SSL_CERT_PATH')
fabconf['SSL_CERT_NAME'] = os.environ.get('SSL_CERT_NAME')
fabconf['SSL_CERT_KEY'] = os.environ.get('SSL_CERT_KEY')

# Where to install apps
fabconf['APPS_DIR'] = "/home/{user}/web".format(user=fabconf.get('SERVER_USERNAME'))

# Where your project will installed: /<APPS_DIR>/<PROJECT_NAME>
fabconf['PROJECT_PATH'] = '{apps}/{project}'.format(
    apps=fabconf.get('APPS_DIR'),
    project=fabconf.get('PROJECT_NAME')
)

# Space-delimited list of app domains
fabconf['DOMAINS'] = os.environ.get('DOMAINS')

# Path for virtualenvs
fabconf['VIRTUALENV_DIR'] = "/home/{user}/.virtualenvs".format(user=fabconf.get('SERVER_USERNAME'))

# Virtualenv activate command
fabconf['ACTIVATE'] = "source /home/{user}/.virtualenvs/{project}/bin/activate".format(
    user=fabconf.get('SERVER_USERNAME'),
    project=fabconf.get('PROJECT_NAME')
)

# Name tag for your server instance on EC2
fabconf['INSTANCE_NAME_TAG'] = os.environ.get('INSTANCE_NAME_TAG')

# EC2 key.
fabconf['AWS_ACCESS_KEY'] = os.environ.get('AWS_ACCESS_KEY')

# EC2 secret.
fabconf['AWS_SECRET_KEY'] = os.environ.get('AWS_SECRET_KEY')

#EC2 region. Defaults to us-west-1
fabconf['EC2_REGION'] = os.environ.get('EC2_REGION', 'us-west-1')

# AMI name. Either pass in a comma-delimited list of values.
# Defaults to Ubuntu 14.04
fabconf['EC2_AMIS'] = os.environ.get('EC2_AMIS', 'ami-d05e75b8').split(',')

# Name of the keypair you use in EC2.
fabconf['EC2_KEY_PAIR'] = os.environ.get('EC2_KEY_PAIR')

# Name of the security group.
fabconf['AWS_SECURITY_GROUPS'] = os.environ.get('AWS_SECURITY_GROUPS')

# API Name of instance type. Defaults to t2.micro
fabconf['EC2_INSTANCE_TYPE'] = os.environ.get('EC2_INSTANCE_TYPE', 't2.micro')

# Existing instances - add the public dns of your instances here when you have spawned them
fabconf['EC2_INSTANCES'] = []
