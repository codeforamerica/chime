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
import pwd

fabconf = {}

#  Do not edit
fabconf['FAB_CONFIG_PATH'] = os.path.dirname(__file__)
fabconf['FAB_HOSTS_FILE'] = fabconf.get('FAB_CONFIG_PATH') + '/hosts.txt'

# Project name
fabconf['PROJECT_NAME'] = os.environ.get('PROJECT_NAME', 'chime')
fabconf['GIT_BRANCH'] = 'master'

# Username for connecting to EC2 instaces - Do not edit unless you have a reason to
fabconf['SERVER_USERNAME'] = 'ubuntu'

# Don't edit. Full path of the ssh key you use to connect to EC2 instances
fabconf['SSH_PRIVATE_KEY_PATH'] = os.environ.get('SSH_PRIVATE_KEY_PATH')

# Where to install apps
fabconf['APPS_DIR'] = "/home/{user}/web".format(user=fabconf.get('SERVER_USERNAME'))

# Where your project will installed: /<APPS_DIR>/<PROJECT_NAME>
fabconf['PROJECT_PATH'] = '{apps}/{project}'.format(
    apps=fabconf.get('APPS_DIR'),
    project=fabconf.get('PROJECT_NAME')
)

# Space-delimited list of app domains
fabconf['DOMAINS'] = os.environ.get('DOMAINS')

# Name tag for your server instance on EC2
# Use recommendation from https://docs.python.org/2/library/os.html#os.getlogin 
# to get around ioctl error thrown by os.getlogin() in a cron job.
fabconf['INSTANCE_NAME_TAG'] = os.environ.get('INSTANCE_NAME_TAG', 'ChimeCMS Autotest')
fabconf['INSTANCE_CREATED_BY'] = '{}-{}'.format(pwd.getpwuid(os.getuid())[0], os.uname()[1])

# EC2 key.
fabconf['AWS_ACCESS_KEY'] = os.environ['AWS_ACCESS_KEY']

# EC2 secret.
fabconf['AWS_SECRET_KEY'] = os.environ['AWS_SECRET_KEY']

#EC2 region. Defaults to us-east-1
fabconf['EC2_REGION'] = os.environ.get('EC2_REGION', 'us-east-1')

# AMI name. Either pass in a comma-delimited list of values.
# Defaults to Ubuntu 14.04
fabconf['EC2_AMIS'] = os.environ.get('EC2_AMIS', 'ami-6725ea0c').split(',')

# Name of the keypair you use in EC2.
fabconf['EC2_KEY_PAIR'] = os.environ.get('EC2_KEY_PAIR', 'cfa-chime-keypair')

# Name of the security group.
fabconf['AWS_SECURITY_GROUPS'] = os.environ.get('AWS_SECURITY_GROUPS', 'default')

# API Name of instance type. Defaults to t2.micro
fabconf['EC2_INSTANCE_TYPE'] = os.environ.get('EC2_INSTANCE_TYPE', 't2.small')

# Assorted other config (described in AcceptanceTests.md) used here to fail fast
fabconf['TESTING_EMAIL'] = os.environ['TESTING_EMAIL']
fabconf['TESTING_PASSWORD'] = os.environ['TESTING_PASSWORD']
