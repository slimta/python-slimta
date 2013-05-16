# Copyright (c) 2012 Ian C. Good
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


setup(name='python-slimta-spf',
      version='0.1.0',
      author='Ian Good',
      author_email='icgood@gmail.com',
      description='Adds an SPF authorization extension to python-slimta.',
      license='MIT',
      url='http://slimta.org/',
      packages=find_packages(),
      namespace_packages=['slimta'],
      install_requires=['python-slimta',
                        'pyspf',
                        'pydns'],
      tests_require=['nose',
                     'mox'],
      test_suite = 'nose.collector',
      classifiers=['Development Status :: 3 - Alpha',
                   'Topic :: Communications :: Email :: Mail Transport Agents',
                   'Intended Audience :: Developers',
                   'Intended Audience :: Information Technology',
                   'License :: OSI Approved :: MIT License',
                   'Programming Language :: Python'])


# vim:et:fdm=marker:sts=4:sw=4:ts=4
