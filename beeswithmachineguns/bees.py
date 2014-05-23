#!/bin/env python

"""
The MIT License

Copyright (c) 2010 The Chicago Tribune & Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import logging
import hashlib
from multiprocessing import Pool
import os
import re
import socket
import sys
import time
import urllib2
import urlparse

import boto, boto.ec2
from boto.s3.key import Key
import paramiko

from tester import ABTester, SiegeTester, TesterResult, WideloadTester, get_aggregate_result


STATE_FILENAME = os.path.expanduser('~/.bees')

# Utilities

def _read_server_list():
    instance_ids = []

    if not os.path.isfile(STATE_FILENAME):
        return (None, None, None, None)

    with open(STATE_FILENAME, 'r') as f:
        region = f.readline().strip()
        username = f.readline().strip()
        key_name = f.readline().strip()
        text = f.read()
        instance_ids = text.split('\n')

        logging.debug('Read %i bees from the roster.' % len(instance_ids))

    return (region, username, key_name, instance_ids)

def _write_server_list(region, username, key_name, instances):
    with open(STATE_FILENAME, 'w') as f:
        f.write('%s\n' % region)
        f.write('%s\n' % username)
        f.write('%s\n' % key_name)
        f.write('\n'.join([instance.id for instance in instances]))

def _delete_server_list():
    os.remove(STATE_FILENAME)

def _get_pem_path(key):
    return os.path.expanduser('~/.ssh/%s.pem' % key)

# Methods

def up(count, group, zone, image_id, instance_type, username, key_name, siege_keepalive):
    """
    Startup the load testing server.
    """
    existing_region, existing_username, existing_key_name, instance_ids = _read_server_list()

    if instance_ids:
        logging.warning('Bees are already assembled and awaiting orders.')
        return

    count = int(count)

    pem_path = _get_pem_path(key_name)

    if not os.path.isfile(pem_path):
        logging.error('No key file found at %s' % pem_path)
        return

    logging.info('Connecting to the hive.')

    region = zone[:-1]
    ec2_connection = boto.ec2.connect_to_region(region)

    logging.info('Attempting to call up %i bees.' % count)

    user_data="""#!/bin/sh

set -e -x

echo 'starting'
apt-get --yes --quiet update
apt-get --yes --quiet install gcc siege apache2-utils
echo 'installing stuff'"""

    if siege_keepalive:
        user_data += """
echo "connection = keep-alive" > /home/%(username)s/.siegerc"""

    user_data += """
touch /home/%(username)s/ready"""

    user_data = user_data % {'username': username}

    reservation = ec2_connection.run_instances(
        image_id=image_id,
        min_count=count,
        max_count=count,
        key_name=key_name,
        security_groups=[group],
        instance_type=instance_type,
        user_data=user_data,
        placement=zone)

    logging.info('Waiting for bees to load their machine guns...')

    instance_ids = []

    for instance in reservation.instances:
        while instance.state != 'running':
            logging.debug('.')
            time.sleep(5)
            instance.update()

        instance_ids.append(instance.id)

        logging.info('Bee %s is ready for the attack.' % instance.id)

    ec2_connection.create_tags(instance_ids, { "Name": "a bee!" })

    _write_server_list(region, username, key_name, reservation.instances)

    logging.info('The swarm has assembled %i bees.' % len(reservation.instances))

def report():
    """
    Report the status of the load testing servers.
    """
    region, username, key_name, instance_ids = _read_server_list()

    if not instance_ids:
        logging.info('No bees have been mobilized.')
        return

    ec2_connection = boto.ec2.connect_to_region(region)

    reservations = ec2_connection.get_all_instances(instance_ids=instance_ids)

    instances = []

    for reservation in reservations:
        instances.extend(reservation.instances)

    for instance in instances:
        logging.info('Bee %s: %s @ %s' % (instance.id, instance.state, instance.ip_address))

def down():
    """
    Shutdown the load testing server.
    """
    region, username, key_name, instance_ids = _read_server_list()

    if not instance_ids:
        logging.info('No bees have been mobilized.')
        return

    logging.info('Connecting to the hive.')

    ec2_connection = boto.ec2.connect_to_region(region)

    logging.info('Calling off the swarm.')

    terminated_instance_ids = ec2_connection.terminate_instances(
        instance_ids=instance_ids)

    logging.info('Stood down %i bees.' % len(terminated_instance_ids))

    _delete_server_list()


def _exec_command_blocking(ssh_client, command, ident):
    """
    """
    exit_status = et = 'unknown'
    try:
        t1 = time.time()
        stdin, stdout, stderr = ssh_client.exec_command(command, bufsize=1)
        exit_status = stdout.channel.recv_exit_status()
        et = '%s seconds' % (time.time() - t1)
        return (stdin, stdout, stderr)
    finally:
        msg = '************ [%s] `%s` (exit: %s, elapsed: %s)'
        logging.info(msg % (ident, command, exit_status, et))


def _attack(params):
    """
    Test the target URL with requests.

    Intended for use with multiprocessing.
    """
    logging.info('Bee %i is joining the swarm.' % params['i'])
    logging.debug('Bee %i params: %s' % (params['i'], params))

    # for logging
    ident = '%s/%s' % (params['i'], params['instance_id'])

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            params['instance_name'],
            username=params['username'],
            key_filename=_get_pem_path(params['key_name']))

        if params['url_file']:
            logging.debug('checking for url file %s' % params['url_file'])
            stdin, stdout, stderr = _exec_command_blocking(client, 'stat %s' % params['url_file'], ident)
            if 'No such file or directory' in stderr.read():
                logging.info('file %s not found on instance, retrieving via curl')
                cmd = 'curl -O "http://s3.amazonaws.com/%s/%s"' % (params['url_file_bucket'], params['url_file'])
                _exec_command_blocking(client, cmd, ident)
            else:
                logging.debug('found file!')

            if params['url_file'].endswith('.gz'):
                logging.debug('gunzipping to urls.txt')
                _exec_command_blocking(client, 'gunzip -c %s > urls.txt' % params['url_file'], ident)
            else:
                logging.debug('copying to urls.txt')
                _exec_command_blocking(client, 'cp %s urls.txt' % params['url_file'], ident)

        try:
            logging.debug('Bee %i is firing his machine gun. Bang bang!' % params['i'])

            engines = {
                'ab': ABTester,
                'siege': SiegeTester,
                'wideload': WideloadTester,
            }
            t = engines[params['engine']]()

            cmd = t.get_command(
                params['num_requests'],
                params['concurrent_requests'],
                params['keepalive'],
                params['url']
                )


            t1 = time.time()
            stdin, stdout, stderr = _exec_command_blocking(client, cmd, ident)

            if params['engine'] == 'siege':
                output = stderr.read()
                logging.debug(output)
            else:
                output = stdout.read()
            result = t.parse_output(output)
            if result is None:
                msg = 'could not parse result from output (%s):' % ident
                logging.error(msg)
                logging.error(output)
            else:
                msg = 'finished testing: (%s)' % ident
                logging.info(msg)
            return result

        finally:
            client.close()

    except socket.error, e:
        msg = 'encountered socket error (%s):' % ident
        logging.error(msg)
        logging.exception(e)
        return e


def attack(url, url_file, n, c, keepalive, output_type, engine):
    """
    Test the root url of this site.
    """
    region, username, key_name, instance_ids = _read_server_list()

    if not instance_ids:
        logging.info('No bees are ready to attack.')
        return

    logging.info('Connecting to the hive.')

    ec2_connection = boto.ec2.connect_to_region(region)

    logging.info('Assembling bees.')

    reservations = ec2_connection.get_all_instances(instance_ids=instance_ids)

    instances = []

    for reservation in reservations:
        instances.extend(reservation.instances)

    instance_count = len(instances)
    requests_per_instance = int(float(n) / instance_count)
    connections_per_instance = int(float(c) / instance_count)
    keepalive = bool(keepalive)

    logging.debug( 'Each of %i bees will fire %s rounds, %s at a time.' % (instance_count, requests_per_instance, connections_per_instance))

    # default s3 bucket when we use it for url files
    bucket_name = 'com.domdex.loadtest'

    # if there's a url file, it's time to:
    # 1) verify it's already present on the worker instances
    # 2a) if not, copy it to s3
    # 2b) and then pull it down from s3 to the workers
    if url_file:

        s3 = boto.connect_s3()

        if url_file.startswith('s3://'):
            # make sure the file exists
            url_parts = urlparse.urlparse(url_file)
            bucket_name, s3_name = url_parts.netloc, url_parts.path[1:]
            logging.debug('bucket_name: [%s]  s3_name: [%s]' % (bucket_name, s3_name))
            lt_bucket = s3.get_bucket(bucket_name)
            key = lt_bucket.get_key(s3_name)
            if not key:
                # invalid file
                msg = 'invalid s3 bucket/key: [%s] [%s]'  % (bucket_name, s3_name)
                logging.error(msg)
                raise Exception, msg
        else:
            # local file
            md5 = hashlib.md5()
            f = open(url_file, 'rb')
            try:
                while True:
                    data = f.read(2**20)
                    if not data:
                        break
                    md5.update(data)
            finally:
                f.close()
            local_hash = md5.hexdigest()
            logging.debug('hash of local url file is %s' % local_hash)

            s3_name = os.path.basename(url_file)
            lt_bucket = s3.get_bucket(bucket_name)
            logging.debug('s3 bucket is %s' % lt_bucket)
            key = lt_bucket.get_key(s3_name)
            logging.debug('key is %s' % key)

            if key:
                remote_hash = key.etag.replace('"','')
                # if etag matches local hash, nothing to be done.
                # if they differ, fail and force the user to either rename the
                # local file or manually overwrite the existing version in s3.
                if remote_hash != local_hash:
                    msg = 'a urls file with the same name [%s], different md5 [%s] '
                    msg+= 'already exists in the bucket.  Please rename the local '
                    msg+= 'urls file or manually overwrite the existing file in s3.'
                    logging.error(msg % (s3_name, remote_hash))
                    raise Exception, msg % (s3_name, remote_hash)
            else:
                # needs to be uploaded.
                logging.info('uploading urls file to %s' % s3_name)
                key = lt_bucket.new_key(s3_name)
                key.set_contents_from_filename(url_file)
                key.set_acl('public-read') # FIXME security
                logging.info('...upload complete')

        url_file = s3_name
        logging.info('using url file: %s' % url_file)

    params = []

    for i, instance in enumerate(instances):
        params.append({
            'i': i,
            'instance_id': instance.id,
            'instance_name': instance.public_dns_name,
            'url': url,
            'url_file': url_file,
            'url_file_bucket': bucket_name,
            'concurrent_requests': connections_per_instance,
            'num_requests': requests_per_instance,
            'username': username,
            'key_name': key_name,
            'keepalive': keepalive,
            'engine': engine,
        })

    logging.info('Stinging URL so it will be cached for the attack.')

    # Ping url so it will be cached for testing
    #if url:
    #    #urllib2.urlopen(url, timeout=5)

    # Spin up processes for connecting to EC2 instances
    pool = Pool(len(params))
    results = pool.map(_attack, params)

    logging.debug('Offensive complete.')

    timeout_bees = [r for r in results if r is None]
    exception_bees = [r for r in results if type(r) == socket.error]
    complete_bees = [r for r in results if r is not None and type(r) != socket.error]

    logging.info('%s of %s clients succeeded.' % (len(complete_bees), len(results)))

    aggregate_result = get_aggregate_result(complete_bees)

    if output_type=='csvh':
        print >> sys.stdout, ','.join(aggregate_result._fields)
        output_type = 'csv'

    if output_type=='csv':
        # it is presumed that csv output should be suppressed when some
        # workers failed.
        if not timeout_bees and not exception_bees:
            print >> sys.stdout, ','.join(map(str,aggregate_result))
        else:
            logging.warning('test results invalid - one or more clients failed')
    else:
        aggregate_result.print_text(sys.stdout)


    logging.info('The swarm is awaiting new orders.')
