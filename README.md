# journal

journald => web gateway

## Attention!

It's not really good python code. I think this code is ugly. Don't use it , okay? (but of course you can)
This is just PoC project!

![](https://github.com/skob/journal/blob/master/screenshot.png "")

This project based on tornado, system-journald python module, bootstrap and select2. Big thanks to many (or maybe to all) users of SO for your help :-)

### options
- `directory` -- for set local/remote journal directory
- `ipaddr` -- default `localhost`
- `port` -- default `8888`
- `UNITS-RE` -- filter options for systemd units

### web
You can view almost live logs and filter its by priority and systemd units.
In case of multi-host journald installation (`man systemd-journal-remote`) you can also filter logs by hostnames.

### Yes I know this
* Yes, you can use `systemd-journal-gatewayd` instead
* ~~Yes, I use too old systemd python library maybe (this is Centos choice)~~
* Yes, feel free to open pull requests
* Yes, you can't just "download and run". This is PoC project, right?
* From docs:
> Note that in order to access the system journal, a non-root user must have the necessary privileges, see journalctl(1) for details. Unprivileged users can access only their own journal
