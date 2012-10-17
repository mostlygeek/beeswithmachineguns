#!/usr/bin/env python
from setuptools import setup, find_packages

# work around a bug in nose setuptools integration
from multiprocessing import util

setup(name='beeswithmachineguns',
      version='0.1.6.4',
      description='A utility for arming (creating) many bees (micro EC2 instances) to attack (load test) targets (web applications).',
      author='Christopher Groskopf',
      author_email='cgroskopf@tribune.com',
      url='http://github.com/Magentic/python-libs',
      license='MIT',
      packages=['beeswithmachineguns'],
      scripts=['bees', 'siege_calc'],
      setup_requires=['nose'],
      test_suite='nose.collector',
      install_requires=[
          'boto>=2.6',
          'paramiko>=1.8'
          ],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Software Development :: Testing :: Traffic Generation',
          'Topic :: Utilities',
          ],
     )
