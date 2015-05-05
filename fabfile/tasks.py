# -*- coding: utf-8 -*-

import boto.ec2
import time

from fabric.api import task, env, run, sudo
from fabric.colors import green, yellow, red
from fabconf import fabconf

@task
def spawn_instance():
    '''
    Creates a new EC2 instance.

    The DNS will be printed as a
    part of the creation process. This address should be
    logged for later use.
    '''
    print(green('Spawning new instance...'))

    env.host_string = _create_ec2_instance()

@task
def despawn_instance(public_dns):
    '''
    Destroys an EC2 instance.
    '''
    print(yellow('Shutting down instance {dns}'.format(
        dns=public_dns
    )))

    _despawn_instance(public_dns, terminate=True)

@task(alias='boot')
def boot_chime(public_dns=None):
    '''
    Installs and boots up chime.

    Spawns an EC2 instance if no dns is given and boots
    up chime on that instance.
    '''
    # set some login variables
    env.user = fabconf.get('SERVER_USERNAME')

    if public_dns is None and env.hosts == []:
        public_dns = _create_ec2_instance()
        print(yellow('Waiting for server to come online...'))
        time.sleep(10)

        if public_dns not in env.hosts or env.hosts == []:
            env.hosts.extend([public_dns])

    elif len(env.hosts) > 0:
        public_dns = env.hosts[0]

    _server_setup(public_dns)

def _connect_to_ec2():
    '''
    Returns a boto connection object
    '''
    print(yellow('Connecting to EC2...'))
    conn = boto.ec2.connect_to_region(
        fabconf.get('EC2_REGION'), aws_access_key_id=fabconf.get('AWS_ACCESS_KEY'),
        aws_secret_access_key=fabconf.get('AWS_SECRET_KEY')
    )

    return conn

def _create_ec2_instance():
    '''
    Actually creates the ec2 instance
    '''
    conn = _connect_to_ec2()

    print(yellow('Booting up instance...'))

    # get all images returns a list of available images
    image = conn.get_all_images(fabconf.get('EC2_AMIS'))

    # use the first available image to create a new reservation
    # http://docs.pythonboto.org/en/latest/ref/ec2.html#boto.ec2.instance.Reservation
    reservation = image[0].run(
        1, 1, key_name=fabconf.get('EC2_KEY_PAIR'),
        security_groups=[fabconf.get('AWS_SECURITY_GROUPS')],
        instance_type=fabconf.get('EC2_INSTANCE_TYPE')
    )

    # reservation contains a list of instances associated with it.
    # we are going to tag the new instance with our conf name tag
    instance = reservation.instances[0]
    conn.create_tags([instance.id], {'Name': fabconf.get('INSTANCE_NAME_TAG')})

    while instance.state == 'pending':
        print(yellow('Instance state: {state}'.format(state=instance.state)))
        time.sleep(10)
        instance.update()

    print(green('Instance state: {state}'.format(state=instance.state)))
    print(green('Public DNS: {dns}'.format(dns=instance.public_dns_name)))

    return instance.public_dns_name

def _despawn_instance(dns, terminate=False):
    conn = _connect_to_ec2()

    for res in conn.get_all_reservations():
        for instance in res.instances:
            if instance.public_dns_name == dns:
                instance.terminate() if terminate else instance.stop()

                while instance.state in ('running', 'pending', 'stopping', 'shutting-down'):
                    print(yellow('Instance state: {state}'.format(state=instance.state)))
                    time.sleep(10)
                    instance.update()

                print(green('Instance state: {state}'.format(state=instance.state)))
                return

    print(red('DNS not found.'))

def _server_setup(fqdn=None):
    '''
    Runs the commands for setting up a server. Uses a hostfile
    template located in the templates/ directory. You can either
    directly pass a fqdn (fully qualified domain name) or use
    the first available host in env.hosts
    '''

    env.host_string = fqdn if fqdn else env.hosts[0]

    print(green('Setting up hostname'))
    hostname = fqdn if fqdn else env.hosts[0]
    run('ls /')
    sudo("echo '" + hostname + "' > " + '/etc/hostname')
    sudo('hostname -F /etc/hostname')

    print(green('Installing git & chime'))
    time.sleep(2)
    sudo('apt-get update && apt-get install -y git')
    run('git clone https://github.com/codeforamerica/ceviche-cms.git')

    print(green('Running chef setup scripts...'))
    time.sleep(2)
    run('cd ceviche-cms && sudo chef/run.sh')
