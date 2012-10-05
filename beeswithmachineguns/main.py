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

import bees
import re
import sys
from optparse import OptionParser, OptionGroup

NO_TRAILING_SLASH_REGEX = re.compile(r'^.*?\.\w+$')

def parse_options():
    """
    Handle the command line arguments for spinning up bees
    """
    command = sys,
    parser = OptionParser(usage="""
bees COMMAND [options]

Bees with Machine Guns

A utility for arming (creating) many bees (small EC2 instances) to attack
(load test) targets (web applications).

commands:
  up      Start a batch of load testing servers.
  attack  Begin the attack on a specific url.
  down    Shutdown and deactivate the load testing servers.
  report  Report the status of the load testing servers.
    """)

    up_group = OptionGroup(parser, "up",
        """In order to spin up new servers you will need to specify at least the -k command, which is the name of the EC2 keypair to use for creating and connecting to the new servers. The bees will expect to find a .pem file with this name in ~/.ssh/.""")

    # Required
    up_group.add_option('-k', '--key',  metavar="KEY",  nargs=1,
                        action='store', dest='key', type='string',
                        help="The ssh key pair name to use to connect to the new servers.")

    up_group.add_option('-s', '--servers', metavar="SERVERS", nargs=1,
                        action='store', dest='servers', type='int', default=5,
                        help="The number of servers to start (default: 5).")
    up_group.add_option('-g', '--group', metavar="GROUP", nargs=1,
                        action='store', dest='group', type='string', default='default',
                        help="The security group to run the instances under (default: default).")
    up_group.add_option('-z', '--zone',  metavar="ZONE",  nargs=1,
                        action='store', dest='zone', type='string', default='us-east-1d',
                        help="The availability zone to start the instances in (default: us-east-1d).")
    up_group.add_option('-i', '--instance',  metavar="INSTANCE",  nargs=1,
                        action='store', dest='instance', type='string', default='ami-ff17fb96',
                        help="The instance-id to use for each server from (default: ami-ff17fb96).")
    up_group.add_option('-l', '--login',  metavar="LOGIN",  nargs=1,
                        action='store', dest='login', type='string', default='newsapps',
                        help="The ssh username name to use to connect to the new servers (default: newsapps).")

    parser.add_option_group(up_group)

    attack_group = OptionGroup(parser, "attack",
            """Beginning an attack requires that you specify the URL(s) you wish to target, either using -u or -f.""")

    # Required
    attack_group.add_option('-u', '--url', metavar="URL", nargs=1,
                        action='store', dest='url', type='string',
                        help="URL of the target to attack.")
    attack_group.add_option('-f', '--url-file', metavar="URL_FILE", nargs=1,
                        action='store', dest='url_file', type='string',
                        help="file containing URLs of the targets to attack.")

    attack_group.add_option('-n', '--number', metavar="NUMBER", nargs=1,
                        action='store', dest='number', type='int', default=1000,
                        help="The number of total connections to make to the target (default: 1000).")
    attack_group.add_option('-c', '--concurrent', metavar="CONCURRENT", nargs=1,
                        action='store', dest='concurrent', type='int', default=100,
                        help="The number of concurrent connections to make to the target (default: 100).")
    attack_group.add_option('--keepalive', metavar="KEEPALIVE",
                            action='store_true', dest='keepalive', default=False,
                            help='Whether or not to use ab keepalive (default: False)')

    parser.add_option_group(attack_group)

    output_group = OptionGroup(parser, "output")
    
    output_group.add_option('-o', '--output', metavar="OUTPUT_TYPE", nargs=1,
                        action='store', dest='output_type', type='string',
                        help="specify \'csv\' to output a csv row.  specify \'csvh\' to output csv headers prior to the csv row.")
    output_group.add_option('-v', '--verbose', metavar="VERBOSE", 
                        action='store_true', dest='verbose', default=False,
                        help="whether to log verbosely to stderr.")

    parser.add_option_group(output_group)

    (options, args) = parser.parse_args()

    if len(args) <= 0:
        parser.error('Please enter a command.')

    command = args[0]
    
    if options.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)


    if command == 'up':
        if not options.key:
            parser.error('To spin up new instances you need to specify a key-pair name with -k')

        #if options.group == 'default':
        #    print 'New bees will use the "default" EC2 security group. Please note that port 22 (SSH) is not normally open on this group. You will need to use to the EC2 tools to open it before you will be able to attack.'

        bees.up(options.servers, options.group, options.zone, options.instance, options.login, options.key)
    elif command == 'attack':
        
        if options.url_file:
            try:
                # only one url supported for now :-)
                url = open(options.url_file,'rb').readline().strip()
            except IOError:
                parser.error('Could not open url file %s - please try again.' % options.url_file)
        elif options.url:
            if NO_TRAILING_SLASH_REGEX.match(options.url):
                parser.error('It appears your URL lacks a trailing slash, this will disorient the bees. Please try again with a trailing slash.')
            else:
                url = options.url
        else:
            parser.error('To run an attack you need to specify either a url with -u or a file with -f.')


        bees.attack(url, options.number, options.concurrent, options.keepalive, options.output_type)
    elif command == 'down':
        bees.down()
    elif command == 'report':
        bees.report()


def main():
    parse_options()


if __name__=='__main__':
    main()

