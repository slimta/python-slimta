#### [Project Homepage][5]
#### [API Documentation and Manual][6]

--------------------

About
=====

The `python-slimta` project is a Python library offering the building blocks
necessary to create a full-featured [MTA][1]. Most MTAs must be configured, but
an MTA built with `python-slimta` is coded. An MTA built with `python-slimta`
can incorporate any protocol or policy, custom or built-in. An MTA built with
`python-slimta` can integrate with other Python libraries and take advantage of
Python's great community.

The `python-slimta` project is released under the [MIT License][4]. It requires
Python 2.6+ and is **not** currently compatible with 3.x.

[![Build Status](http://ci.slimta.org/job/python-slimta/badge/icon)](http://ci.slimta.org/job/python-slimta/)

Getting Started
===============

Use a [virtualenv][2] to get started developing against `python-slimta`:

    $ cd python-slimta/
    $ virtualenv .venv
    $ source .venv/bin/activate
    (.venv)$ python setup.py develop

To run the suite of unit tests included with `slimta`:

    (.venv)$ pip install -r test/requirements.txt
    (.venv)$ nosetests

Running the Example
===================

The example in [`examples/slimta-mail.py`](examples/slimta-mail.py) provides a
fully functional mail server for inbound and outbound email. It needs several
things to run:

* An activated `virtualenv` as created above in *Getting Started*.

* A TLS certificate and key file. The easiest way to generate one:

```
openssl req -x509 -nodes -subj '/CN=localhost' -newkey rsa:1024 -keyout cert.pem -out cert.pem
```
    
* Superuser privileges at startup.

  The example starts services on ports 25, 587, and 465 by default, which are
  privileged ports on Linux machines.

* A user and group to run as.

  Once the privileged ports are open, the example attempts to drop down to a
  non-privileged user and group for security purposes.
  
* A populated [`examples/site_data.py`](examples/site_data.py) config file.
  
Please see in the in-line example documentation by running:

    (.venv)$ ./slimta-mail.py --help

[1]: http://en.wikipedia.org/wiki/Message_transfer_agent
[2]: http://pypi.python.org/pypi/virtualenv
[3]: http://en.wikipedia.org/wiki/Open_mail_relay
[4]: http://opensource.org/licenses/MIT
[5]: http://slimta.org/
[6]: http://docs.slimta.org/

