#!/usr/bin/env python
"""Project Setup"""
from setuptools import find_packages, setup

setup(
    name='p8tool',
    version='0.0',
    author='dansanderson',
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
