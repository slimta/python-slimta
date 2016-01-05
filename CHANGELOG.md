
# Change Log

## [3.1] - _Unreleased_

### Added

- `QueueError` objects may now set the `reply` attribute to tell edge services
  what happened.

### Changed

- The builtin edges now use `451` codes when a `QueueError` occurs, rather than
  `550`.

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
[3.0]: https://github.com/slimta/python-slimta/issues?q=milestone%3A3.0
[3.1]: https://github.com/slimta/python-slimta/issues?q=milestone%3A3.1
