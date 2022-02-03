
#### [API Documentation and Manual][5]

--------------------

About
=====

The `python-slimta` project is a Python library offering the building blocks
necessary to create a full-featured [MTA][1]. Most MTAs must be configured, but
an MTA built with `python-slimta` is coded. An MTA built with `python-slimta`
can incorporate any protocol or policy, custom or built-in. An MTA built with
`python-slimta` can integrate with other Python libraries and take advantage of
Python's great community.

The `python-slimta` project is released under the [MIT License][4]. It is
tested for Python 3.6+.

[![build](https://github.com/slimta/python-slimta/actions/workflows/python-package.yml/badge.svg)](https://github.com/slimta/python-slimta/actions/workflows/python-package.yml)
[![PyPI](https://img.shields.io/pypi/v/python-slimta.svg)](https://pypi.python.org/pypi/python-slimta)
[![PyPI](https://img.shields.io/pypi/pyversions/python-slimta.svg)](https://pypi.python.org/pypi/python-slimta)
[![PyPI](https://img.shields.io/pypi/l/python-slimta.svg)](https://pypi.python.org/pypi/python-slimta)


Getting Started
===============

Use a [virtualenv][2] to get started developing against `python-slimta`:

    $ cd python-slimta/
    $ python3 -m venv .venv
    $ source .venv/bin/activate
    (.venv)$ pip install -U pip wheel setuptools

To run the suite of unit tests included with `slimta`:

    (.venv)$ pip install -r requirements-dev.txt
    (.venv)$ py.test

Running the Example
===================

The example in [`examples/slimta-mail.py`](examples/slimta-mail.py) provides a
fully functional mail server for inbound and outbound email. To avoid needing
to run as superuser, the example uses ports `1025`, `1465` and `1587` instead.

It needs several things to run:

* An activated `virtualenv` as created above in *Getting Started*.

* A TLS certificate and key file. The easiest way to generate one:

```
openssl req -x509 -nodes -subj '/CN=localhost' -newkey rsa:1024 -keyout cert.pem -out cert.pem
```

* A populated [`examples/site_data.py`](examples/site_data.py) config file.

Check out the in-line documentation with `--help`, and then run:

    (.venv)$ ./slimta-mail.py

Manually or with a mail client, you should now be able to deliver messages. On
port `1025`, messages will go to unique files in the current directory. On port
`1587`, messages will be delivered to others using MX records! To try out a TLS
connection:

    $ openssl s_client -host localhost -port 1587 -starttls smtp

Contributing
============

If you want to fix a bug or make a change, follow the [fork pull request][6]
model. We've had quite a few [awesome contributors][7] over the years, and are
always open to more.

Special thanks to [JocelynDelalande][8] for extensive work bringing Python 3
compatibility to the project!

[1]: http://en.wikipedia.org/wiki/Message_transfer_agent
[2]: http://pypi.python.org/pypi/virtualenv
[3]: http://en.wikipedia.org/wiki/Open_mail_relay
[4]: http://opensource.org/licenses/MIT
[5]: http://slimta.org/
[6]: https://help.github.com/articles/using-pull-requests/
[7]: https://github.com/slimta/python-slimta/graphs/contributors
[8]: https://github.com/JocelynDelalande
