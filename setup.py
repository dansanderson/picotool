#!/usr/bin/env python
"""Project Setup"""
from setuptools import find_packages, setup

setup(
    name='p8tool',
    version='0.1',
    author='Dan Sanderson',
    author_email='contact@dansanderson.com',
    description='Tools and Python libraries for manipulating Pico-8 game files',
    license='MIT',
    packages=find_packages(where='.', exclude=['tests', 'tests.*']),
    include_package_data=True,
    install_requires=[
        'pypng'
    ],
    tests_require=[
        'nose',
    ],
    test_suite='nose.collector',
    entry_points={
        'console_scripts': [
            'p8tool=pico8.tool:main',
            'p8upsidedown=pico8.demos.upsidedown:main',
        ],
    },
)
