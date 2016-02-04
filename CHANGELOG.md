
# Change Log

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
[3.0]: https://github.com/slimta/python-slimta/issues?q=milestone%3A3.0
[3.1]: https://github.com/slimta/python-slimta/issues?q=milestone%3A3.1
