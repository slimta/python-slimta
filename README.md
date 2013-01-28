### [Project Homepage][5]
### [API Documentation and Manual][6]

--------------------

About
=====

The `slimta` project is a Python library offering the building blocks necessary
to create a full-featured [MTA][1]. Most MTAs must be configured, but an MTA
built with `slimta` is coded. An MTA built with `slimta` can incorporate any
protocol or policy, custom or built-in. An MTA built with `slimta` can
integrate with other Python libraries and take advantage of Python's great
community.

The `slimta` project is released under the [MIT License][4].

[![Build Status](http://ci.slimta.org/job/slimta/badge/icon)](http://ci.slimta.org/job/slimta/)

Getting Started
===============

Use a [virtualenv][2] to get started developing against `slimta`:

    $ cd python-slimta/
    $ virtualenv .venv
    $ source .venv/bin/activate
    (.venv)$ python setup.py develop

To run the suite of unit tests included with `slimta`:

    (.venv)$ pip install nose
    (.venv)$ python setup.py nosetests

To run one of the included examples:

    (.venv)$ python examples/smtpmx.py

***Note:*** Though this particular example will create an [open relay][3] on
port `1337`, it is only accessible from localhost. Hit *Control-C* to exit and
kill the open relay.

[1]: http://en.wikipedia.org/wiki/Message_transfer_agent
[2]: http://pypi.python.org/pypi/virtualenv
[3]: http://en.wikipedia.org/wiki/Open_mail_relay
[4]: http://opensource.org/licenses/MIT
[5]: http://slimta.org/
[6]: http://docs.slimta.org/

