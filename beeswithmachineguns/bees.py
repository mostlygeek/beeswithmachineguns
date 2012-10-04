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
from multiprocessing import Pool
import os
import re
import socket
import sys
import time
import urllib2

import boto
import paramiko

from tester import ABTester, TesterResult, get_aggregate_result


EC2_INSTANCE_TYPE = 't1.micro'
STATE_FILENAME = os.path.expanduser('~/.bees')

# Utilities

def _read_server_list():
    instance_ids = []

    if not os.path.isfile(STATE_FILENAME):
        return (None, None, None)

    with open(STATE_FILENAME, 'r') as f:
        username = f.readline().strip()
        key_name = f.readline().strip()
        text = f.read()
        instance_ids = text.split('\n')

        logging.debug('Read %i bees from the roster.' % len(instance_ids))

    return (username, key_name, instance_ids)

def _write_server_list(username, key_name, instances):
    with open(STATE_FILENAME, 'w') as f:
        f.write('%s\n' % username)
        f.write('%s\n' % key_name)
        f.write('\n'.join([instance.id for instance in instances]))

def _delete_server_list():
    os.remove(STATE_FILENAME)

def _get_pem_path(key):
    return os.path.expanduser('~/.ssh/%s.pem' % key)

# Methods

def up(count, group, zone, image_id, username, key_name):
    """
    Startup the load testing server.
    """
    existing_username, existing_key_name, instance_ids = _read_server_list()

    if instance_ids:
        logging.warning('Bees are already assembled and awaiting orders.')
        return

    count = int(count)

    pem_path = _get_pem_path(key_name)

    if not os.path.isfile(pem_path):
        logging.error('No key file found at %s' % pem_path)
        return

    logging.info('Connecting to the hive.')

    ec2_connection = boto.connect_ec2()

    logging.info('Attempting to call up %i bees.' % count)

    reservation = ec2_connection.run_instances(
        image_id=image_id,
        min_count=count,
        max_count=count,
        key_name=key_name,
        security_groups=[group],
        instance_type=EC2_INSTANCE_TYPE,
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

    _write_server_list(username, key_name, reservation.instances)

    logging.info('The swarm has assembled %i bees.' % len(reservation.instances))

def report():
    """
    Report the status of the load testing servers.
    """
    username, key_name, instance_ids = _read_server_list()

    if not instance_ids:
        logging.info('No bees have been mobilized.')
        return

    ec2_connection = boto.connect_ec2()

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
    username, key_name, instance_ids = _read_server_list()

    if not instance_ids:
        logging.info('No bees have been mobilized.')
        return

    logging.info('Connecting to the hive.')

    ec2_connection = boto.connect_ec2()

    logging.info('Calling off the swarm.')

    terminated_instance_ids = ec2_connection.terminate_instances(
        instance_ids=instance_ids)

    logging.info('Stood down %i bees.' % len(terminated_instance_ids))

    _delete_server_list()

def _attack(params):
    """
    Test the target URL with requests.

    Intended for use with multiprocessing.
    """
    logging.info('Bee %i is joining the swarm.' % params['i'])
    logging.debug('Bee %i params: %s' % (params['i'], params))
    
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            params['instance_name'],
            username=params['username'],
            key_filename=_get_pem_path(params['key_name']))

        try:
            logging.debug('Bee %i is firing his machine gun. Bang bang!' % params['i'])
            
            t = ABTester()
    
            cmd = t.get_command(
                params['num_requests'],
                params['concurrent_requests'],
                params['keepalive'],
                params['url']
                )
        
            stdin, stdout, stderr = client.exec_command(cmd)
            output = stdout.read()
            result = t.parse_output(output)
            if result is None:
                msg = 'could not parse result from output (%(i)s/%(instance_id)s):'
                logging.error(msg % params)
                logging.error(output)
            else:
                msg = 'finished testing: (%(i)s/%(instance_id)s)'
                logging.info(msg % params)
            return result

        finally:
            client.close()

    except socket.error, e:
        msg = 'encountered socket error (%(i)s/%(instance_id)s):'
        logging.error(msg % params)
        logging.exception(e)
        return e


def attack(url, n, c, keepalive, output_type):
    """
    Test the root url of this site.
    """
    username, key_name, instance_ids = _read_server_list()

    if not instance_ids:
        logging.info('No bees are ready to attack.')
        return

    logging.info('Connecting to the hive.')

    ec2_connection = boto.connect_ec2()

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

    params = []

    for i, instance in enumerate(instances):
        params.append({
            'i': i,
            'instance_id': instance.id,
            'instance_name': instance.public_dns_name,
            'url': url,
            'concurrent_requests': connections_per_instance,
            'num_requests': requests_per_instance,
            'username': username,
            'key_name': key_name,
            'keepalive': keepalive
        })

    logging.info('Stinging URL so it will be cached for the attack.')

    # Ping url so it will be cached for testing
    urllib2.urlopen(url, timeout=5)

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
