#!/usr/bin/env python

import login_backend

long_description = open('README.md').read()

setup_args = dict(
    name='login-service-backend',
    version=login_backend.__version__,
    description='Django authentication backend for Summit tools unified Login Service.',
    long_description=long_description,
    author='Jeremy Satterfield',
    author_email='jsatterfield@summitesp.com',
    license='MIT License',
    packages=['login_backend'],
    install_requires=[
        'django>=1.6',
    ],
    classifers=[
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Systems Administration :: Authentication/Directory',
    ],
)

if __name__ == '__main__':
    from distutils.core import setup

    setup(**setup_args)
