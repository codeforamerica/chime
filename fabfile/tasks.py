# -*- coding: utf-8 -*-

from __future__ import with_statement, print_function

import os
import tempfile
import subprocess
import time
import json

import boto.ec2
from boto import connect_s3
from fabric.operations import local
from fabric.api import task, env, run, sudo
from fabric.colors import green, yellow, red
from fabric.exceptions import NetworkError
from fabric.contrib.project import rsync_project

from fabconf import fabconf


def server_host():
    return _load_hosts()[0]


@task
def spawn_instance():
    '''
    Creates a new EC2 instance and stores the
    resulting DNS in a hosts.txt file.
    '''
    print(green('Spawning new instance...'))
    env.key_filename = fabconf.get('SSH_PRIVATE_KEY_PATH')
    env.host_string = _create_ec2_instance()


@task
def despawn_instance(public_dns=None):
    '''
    Destroys an EC2 instance.
    '''
    if public_dns is None:
        public_dns = server_host()
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
    up chime on that instance.
    '''
    from fabconf import fabconf
    # set some login variables
    env.user = fabconf.get('SERVER_USERNAME')
    env.key_filename = fabconf.get('SSH_PRIVATE_KEY_PATH')
    hosts = _load_hosts()

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
def test_chime(setup=True, despawn=True, despawn_on_failure=False):
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

    public_dns = _find_or_make_a_host()

    if _looks_true(setup):
        _server_setup(public_dns)

    print(green('Running tests...'))
    time.sleep(2)

    handle, output_filename = tempfile.mkstemp(prefix='tests-', suffix='.txt')
    os.environ['OUTPUT_FILE'] = output_filename
    os.close(handle)
    print('Saving output to', output_filename)

    try:
        with open(output_filename, 'w') as output:
            print(json.dumps(dict(start=time.time())), file=output)
        local('nosetests  --processes=9 --process-timeout=300 ' + fabconf.get('FAB_CONFIG_PATH') + '/../test/acceptance')
        with open(output_filename, 'a') as output:
            print(json.dumps(dict(ok=True, end=time.time())), file=output)
        if _looks_true(despawn):
            _despawn(public_dns)
    except:
        with open(output_filename, 'a') as output:
            print(json.dumps(dict(ok=False, end=time.time())), file=output)
        if _looks_true(despawn_on_failure):
            _despawn(public_dns)
        raise
    finally:
        if _looks_true(os.environ.get('REPORT_TO_S3')):
            _send_results_to_cloud(output_filename)

@task
def redeploy():
    env.user = fabconf.get('SERVER_USERNAME')

    _find_host()
    _server_setup()
    rsync_code()
    print(green("restarting chime"))
    sudo('service chime restart')
    print(green("done"))


def _find_host():
    hosts = _load_hosts()
    env.hosts = hosts
    return hosts[0]

def _find_or_make_a_host():
    hosts = _load_hosts()
    if len(hosts) == 0:
        public_dns = _create_ec2_instance()
        print(yellow('Waiting for server to come online...'))
        time.sleep(10)
        print(yellow('Writing public DNS to host file...'))
        _write_host_to_file(public_dns)

    else:
        env.hosts = hosts
        public_dns = hosts[0]
    return public_dns

def _despawn(public_dns):
    print(green('Despawning EC2 instance'))
    _despawn_instance(public_dns)


def _looks_true(argument):
    return argument in [True, 'True', 'true', 't', 'y']


def _load_hosts():
    hostfile = fabconf.get('FAB_HOSTS_FILE')
    try:
        with open(hostfile, 'r') as f:
            hosts = f.read().split(',')
        return [h.strip() for h in hosts if h != '']
    except IOError:
        return []

        if self.output:
            print(self, 'done', file=self.output)


def _write_host_to_file(host):
    hosts = _load_hosts()
    hosts.append(host)
    _save_hosts(hosts)


def _strip_host_from_file(host):
    hosts = _load_hosts()
    hosts.remove(host)
    _save_hosts(hosts)


def _save_hosts(hosts):
    with open(fabconf.get('FAB_HOSTS_FILE'), 'w') as f:
        f.write(",".join(hosts))

def _send_results_to_cloud(filename):
    ''' Send JSON results to the moon.
    '''
    with open(filename) as file:
        results = [json.loads(line) for line in file]

    headers = {'Content-Type': 'application/json'}
    
    # The first and last lines have the start and end times.
    commit = subprocess.check_output('git rev-parse HEAD'.split()).decode('utf8')[:12]
    output = dict(results=results[1:-1], commit=commit)
    output.update(results[0])
    output.update(results[-1])
    string = json.dumps(output, indent=2)

    connection = connect_s3(fabconf.get('AWS_ACCESS_KEY'), fabconf.get('AWS_SECRET_KEY'))

    for key_name in ('acceptance-test-nights.json', 'acceptance-test-nights-{}.json'.format(commit)): 
        key = connection.get_bucket('chimecms-test-results').new_key(key_name)
        key.set_contents_from_string(string, policy='public-read', headers=headers)
        url = key.generate_url(expires_in=0, query_auth=False, force_http=True)

        print('Uploaded to', url)

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
    conn.create_tags([instance.id], {'CreatedBy': fabconf.get('INSTANCE_CREATED_BY')})

    while instance.state == 'pending':
        print(yellow('Instance state: {state}'.format(state=instance.state)))
        time.sleep(10)
        instance.update()

    print(green('Instance state: {state}'.format(state=instance.state)))
    print(green('Public DNS: {dns}'.format(dns=instance.public_dns_name)))

    return instance.public_dns_name


def _despawn_instance(dns, terminate=True):
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

    _wait_until_host_is_ready()

    _make_sure_host_name_is_right(hostname)

    _install_chime_if_necessary()


def _install_chime_if_necessary():
    if run("ps -u chime", quiet=True).succeeded:
        print(green('Chime running; skipping chime install'))
    else:
        print(green('Installing chime'))
        sudo('apt-get -qq update')
        sudo('apt-get -qq dist-upgrade')
        # rsync quietly and don't bother with host keys
        rsync_code()
        print(green('Running chef setup scripts...'))
        time.sleep(2)

        # Directory name needs to match current directory due to rsync:
        # http://docs.fabfile.org/en/1.10/api/contrib/project.html#fabric.contrib.project.rsync_project
        dirname = os.path.basename(os.path.abspath('.'))
        run('cd {dir} && sudo ACCEPTANCE_TEST_MODE=1 chef/run.sh'.format(dir=dirname))


def _make_sure_host_name_is_right(hostname):
    if run('hostname') == hostname:
        print(green('Hostname is correct'))
    else:
        print(green('Setting up hostname'))
        sudo("echo '" + hostname + "' > " + '/etc/hostname')
        sudo('hostname -F /etc/hostname')


def _wait_until_host_is_ready():
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
                raise
            print(yellow('Host still not alive. Waiting five seconds and retrying...'))
            time.sleep(5)


@task
def rsync_code(hostname=None):
    if not hostname:
        hostname = server_host()
    env.host_string = hostname
    env.user = fabconf.get('SERVER_USERNAME')
    print("going for user " + env.user)

    rsync_project(remote_dir='.', default_opts='-pthrz',
                  ssh_opts='-o CheckHostIP=no -o UserKnownHostsFile=/dev/null -o StrictHostkeyChecking=no')
