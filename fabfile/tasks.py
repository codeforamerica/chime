# -*- coding: utf-8 -*-

import boto.ec2
import time

from fabric.api import task, env
from fabric.colors import green, yellow, red
from fabconf import fabconf

@task
def spawn_instance():
    '''
    Creates a new EC2 instance. The DNS will be printed as a
    part of the creation process. This address should be
    logged for later use.
    '''
    print(green('Spawning new instance...'))

    env.host_string = _create_ec2_instance()

@task
def despawn_instance(public_dns):
    print(yellow('Shutting down instance {dns}'.format(
        dns=public_dns
    )))

    _despawn_instance(public_dns, terminate=True)

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

                while instance.state in ('running', 'pending', 'stopping'):
                    print(yellow('Instance state: {state}'.format(state=instance.state)))
                    time.sleep(10)
                    instance.update()

                print(green('Instance state: {state}'.format(state=instance.state)))
                return

    print(red('DNS not found.'))
