# Copyright (c) 2021 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

from setuptools import setup, find_packages

with open('README.md') as f:
    readme = f.read()

with open('LICENSE.md') as f:
    license = f.read()

setup(name='python-slimta',
      version='5.0.1',
      author='Ian Good',
      author_email='ian@icgood.net',
      description='Lightweight, asynchronous SMTP libraries.',
      long_description=readme + license,
      long_description_content_type='text/markdown',
      license='MIT',
      url='http://slimta.org/',
      include_package_data=True,
      packages=find_packages(),
      namespace_packages=['slimta'],
      install_requires=['gevent >= 1.1rc',
                        'pysasl >= 0.5.0',
                        'pycares >= 1'],
      extras_require={'spf': ['pyspf', 'py3dns'],
                      'redis': ['redis'],
                      'aws': ['boto'],
                      'disk': ['pyaio >= 0.4; platform_system == "Linux"']},
      classifiers=['Development Status :: 3 - Alpha',
                   'Topic :: Communications :: Email :: Mail Transport Agents',
                   'Intended Audience :: Developers',
                   'Intended Audience :: Information Technology',
                   'License :: OSI Approved :: MIT License',
                   'Programming Language :: Python',
                   'Programming Language :: Python :: 3.6',
                   'Programming Language :: Python :: 3.7',
                   'Programming Language :: Python :: 3.8',
                   'Programming Language :: Python :: 3.9'])


# vim:et:fdm=marker:sts=4:sw=4:ts=4
