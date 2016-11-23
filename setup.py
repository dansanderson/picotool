from setuptools import setup

setup(
    name='picotool',
    version='0.1',
    packages=['pico8'],
    url='https://github.com/dansanderson/picotool',
    license='MIT',
    author='Dan Sanderson',
    author_email='contact@dansanderson.com',
    description='Tools and Python libraries for manipulating Pico-8 game files',
    entry_points = {
        'console_scripts': [
            'p8tool=pico8.tool:main_ep',
            'p8upsidedown=pico8.demos.upsidedown:main_ep',
        ]
    },
)
