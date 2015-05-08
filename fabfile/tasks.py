# -*- coding: utf-8 -*-

from __future__ import with_statement

import boto.ec2
import time

from fabric.context_managers import cd
from fabric.operations import local
from fabric.api import task, env, run, sudo
from fabric.colors import green, yellow, red
from fabric.exceptions import NetworkError

@task
def spawn_instance():
    '''
    Creates a new EC2 instance and stores the
    resulting DNS in a hosts.txt file.
    '''
    from fabconf import fabconf
    print(green('Spawning new instance...'))
    env.key_filename = fabconf.get('SSH_PRIVATE_KEY_PATH')
    env.host_string = _create_ec2_instance()

@task
def despawn_instance(public_dns=None):
    '''
    Destroys an EC2 instance.
    '''
    from fabconf import fabconf
    if public_dns is None:
        public_dns = _read_hosts_from_file()[0]
        env.key_filename = fabconf.get('SSH_PRIVATE_KEY_PATH')
    print(yellow('Shutting down instance {dns}'.format(
        dns=public_dns
    )))

    _despawn_instance(public_dns, terminate=True)

@task(alias='boot')
def boot_chime():
    '''
    Installs and boots up chime.

    Spawns an EC2 instance if no dns is given and boots
    up chime on that instance. Can only deploy the master
    branch.
    '''
    from fabconf import fabconf
    # set some login variables
    env.user = fabconf.get('SERVER_USERNAME')
    env.key_filename = fabconf.get('SSH_PRIVATE_KEY_PATH')
    hosts = _read_hosts_from_file()

    if len(hosts) == 0:
        public_dns = _create_ec2_instance()
        print(yellow('Waiting for server to come online...'))
        time.sleep(10)
        print(yellow('Writing public DNS to host file...'))
        _write_host_to_file(public_dns)
    else:
        env.hosts = hosts
        public_dns = hosts[0]

    _server_setup(public_dns)

@task
def test_chime(setup=True, despawn=True, branch=None):
    '''
    Create a chime instance and run selenium tests.

    Takes two optional params: setup, and despawn.
    When setup is True, it will set up the server to work
    with Chime. When despawn is True, it will terminate
    the instance after running the tests. Accepted values
    for setup/despawn to be considered True are 'True', 't',
    'true', and 'y'. Using any other value will either
    not run the setup scripts or keep the instance alive,
    respectively.

    Additionally, the branch that should be tested can be
    specified with the branch argument
    '''
    from fabconf import fabconf
    env.user = fabconf.get('SERVER_USERNAME')
    env.key_filename = fabconf.get('SSH_PRIVATE_KEY_PATH')
    hosts = _read_hosts_from_file()

    if len(hosts) == 0:
        public_dns = _create_ec2_instance()
        print(yellow('Waiting for server to come online...'))
        time.sleep(10)
        print(yellow('Writing public DNS to host file...'))
        _write_host_to_file(public_dns)

    else:
        env.hosts = hosts
        public_dns = hosts[0]

    if setup in [True, 'True', 'true', 't', 'y']:
        _server_setup(public_dns)

    if branch:
        if env.host_string is None:
            hosts = _read_hosts_from_file()
            env.host_string = hosts[0]
        print(green('Checking out to {branch}...'.format(branch=branch)))
        with cd('ceviche-cms'):
            run('git checkout -q {branch}'.format(branch=branch))

    print(green('Running tests...'))
    time.sleep(2)
    local('python ' + fabconf.get('FAB_CONFIG_PATH') + '/../test/selenium/e2e.py')

    if despawn in [True, 'True', 'true', 't', 'y']:
        print(green('Despawning EC2 instance'))
        _despawn_instance(public_dns)

def _read_hosts_from_file():
    from fabconf import fabconf
    hostfile = fabconf.get('FAB_HOSTS_FILE')
    try:
        with open(hostfile, 'r+') as f:
            hosts = f.read().split(',')
        return [h for h in hosts if h != '']
    except IOError:
        return []

def _write_host_to_file(host):
    from fabconf import fabconf
    hostfile = fabconf.get('FAB_HOSTS_FILE')
    with open(hostfile, 'w+') as f:
        f.write(host + ',')

def _strip_host_from_file(host):
    from fabconf import fabconf
    hostfile = fabconf.get('FAB_HOSTS_FILE')
    hosts = _read_hosts_from_file()
    hosts.remove(host)
    with open(hostfile, 'w+') as f:
        for remainder in hosts:
            f.write(remainder+',')

def _connect_to_ec2():
    '''
    Returns a boto connection object
    '''
    from fabconf import fabconf
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
    from fabconf import fabconf
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
                print(green('Removing {dns} from hosts file').format(dns=dns))
                _strip_host_from_file(dns)
                return

    print(red('DNS not found.'))

def _server_setup(fqdn=None):
    '''
    Runs the commands for setting up a server. Uses a hostfile
    template located in the templates/ directory. You can either
    directly pass a fqdn (fully qualified domain name) or use
    the first available host in env.hosts
    '''

    hostname = fqdn if fqdn else env.hosts[0]
    env.host_string = hostname

    print(yellow('Waiting for host to come online...'))
    retries = 0
    while retries < 10:
        try:
            run('whoami')
            retries = 10
        except NetworkError:
            retries += 1
            if retries >= 10:
                print(red('Host still not online. Aborting.'))
                return
            print(yellow('Host still not alive. Waiting five seconds and retrying...'))
            time.sleep(5)

    print(green('Setting up hostname'))
    sudo("echo '" + hostname + "' > " + '/etc/hostname')
    sudo('hostname -F /etc/hostname')

    print(green('Installing git & chime'))
    time.sleep(2)
    sudo('apt-get update && apt-get install -y git')
    run('git clone https://github.com/codeforamerica/ceviche-cms.git')

    print(green('Running chef setup scripts...'))
    time.sleep(2)
    run('cd ceviche-cms && sudo chef/run.sh')
