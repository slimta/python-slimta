
# Change Log

## Unreleased

### Fixed

- The result of the reverse IP lookup was never consumed in [`SmtpEdge`][9].

## [4.0] - 2016-11-13

### Added

- New `slimta.util` functions for limiting outbound connections to IPv4.
- New [`socket_error_log_level`][6] variable for better log level control.

### Changed

- Constructors and functions that took a `tls` dictionary now take a `context`
  argument that should be an [`SSLContext`][7] object. This allows finer
  control of encryption behavior, as well as the ability to pre-load sensitive
  certificate data before daemonization.
- Client connections will now be opportunistic and try to use TLS if it is
  available, even if a key or cert have not been configured.
- The `AUTH` SMTP extension will now advertise insecure authentication
  mechanisms without TLS, but trying to use them will fail.
- Moved the `slimta.system` module to `slimta.util.system` to de-clutter the
  top-level namespace.

### Fixed

- Fixed a possible race condition on enqueue.
- Fixed exception when given empty EHLO/HELO string.
- Fixed the fallback from EHLO to HELO in certain situations.
- The [`session.auth`][8] variable now correctly contains the tuple described
  in the documentation.

## [3.2] - 2016-05-16

### Added

- The [`parseline`][5] function is now exposed and documented.
- The `slimta.logging.log_exception` function may now be replaced with custom
  functions, for special error handling scenarios.

### Changed

- Unit tests are now run with `py.test` instead of `nosetests`.
- Exception log lines will now include up to 10,000 characters of the traceback
  string.
- Socket errors are no longer logged as unhandled errors and do not include a
  traceback.
- `socket.gaierror` failures are now caught and ignored during PTR lookup.

### Fixed

- Correctly set an empty greenlet pool in `EdgeServer` constructor.
- Corrected a potential duplicate relay scenario in `Queue`.
- `Reply` encoding and decoding now works correctly in Python 2.x.
- Fixed `httplib` imports in Python 3.3.

## [3.1] - 2016-02-04

### Added

- `QueueError` objects may now set the `reply` attribute to tell edge services
  what happened.
- SMTP servers now advertize `SMTPUTF8` and clients will now use UTF-8 sender
  and recipient addresses when connected to servers that advertize it.
- When creating an edge or relay service, now checks for the existence of any
  given TLS key or cert files before proceeding.
- Support for [proxy protocol][1] version 2 and version auto-detection.

### Removed

- Dependence on [six][4] for Python 2/3 compatibility.

### Changed

- The builtin edges now use `451` codes when a `QueueError` occurs, rather than
  `550`.
- The `Bounce` class header and footer templates may now be bytestrings.
- `Envelope.flatten` now returns bytestrings on Python 3, to avoid unnecessary
  encoding and decoding of message data.

### Fixed

- Correctly throws `PermanentRelayError` instead of `ZeroDivisionError` for
  SMTP MX relays when DNS returns no results.

## [3.0] - 2015-12-19

### Added

- Compatibility with Python 3.3+.
- [Proxy protocol][1] version 1 support on edge services.
- Dependence on [pycares][2] for DNS resolution.
- Support for the `socket_creator` option to control how sockets are created
  during SMTP relaying.
- Support for `ehlo_as` functions to allow custom EHLO logic on each delivery
  attempt.
- Support for a new `handle_queued` callback on SMTP edges, to control the reply
  code and message based on queue results.

### Removed

- Compatibility with Python 2.6.x.
- Dependence on [dnspython][3] for DNS resolution.

### Changed

- Relay results that were returned as a list are now returned as a dict, keyed
  on the envelope recipients.

### Fixed

- During SMTP relaying, timeouts and other errors will more consistently return
  the current SMTP command where the error happened.
- Setting a reply code to `221` or `421` in an SMTP edge session will now result
  in the connection closing.

[1]: http://www.haproxy.org/download/1.5/doc/proxy-protocol.txt
[2]: https://github.com/saghul/pycares
[3]: http://www.dnspython.org/
[4]: https://pythonhosted.org/six/
[5]: https://docs.slimta.org/en/latest/api/slimta.logging.html#slimta.logging.parseline
[6]: https://docs.slimta.org/en/latest/api/slimta.logging.socket.html#slimta.logging.socket.socket_error_log_level
[7]: https://docs.python.org/2.7/library/ssl.html#ssl.SSLContext
[8]: https://docs.slimta.org/en/latest/api/slimta.edge.smtp.html#slimta.edge.smtp.SmtpValidators.session
[9]: https://docs.slimta.org/en/latest/api/slimta.edge.smtp.html#slimta.edge.smtp.SmtpEdge
[3.0]: https://github.com/slimta/python-slimta/issues?q=milestone%3A3.0
[3.1]: https://github.com/slimta/python-slimta/issues?q=milestone%3A3.1
[3.2]: https://github.com/slimta/python-slimta/issues?q=milestone%3A3.2
[4.0]: https://github.com/slimta/python-slimta/issues?q=milestone%3A4.0
