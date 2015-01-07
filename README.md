blackbird-fio-status
====================

[![Build Status](https://travis-ci.org/Vagrants/blackbird-fio-status.png?branch=development)](https://travis-ci.org/Vagrants/blackbird-fio-status)

Get information of [Fusion-io](http://www.fusionio.com/) product (ex. ioDrive) by using `fio-status`.


## before using blackbird-fio-status

`/usr/bin/fio-status` needs root privilege, so blackbird user (default bbd) must be able to sudo with NOPASSWD.

```
# cat /etc/sudoers.d/bbd
Defaults:bbd !requiretty
bbd ALL=(ALL) NOPASSWD: /usr/bin/fio-status
```

Or you must run blackbird in root user.

```
# cat /etc/blackbird/defaults.cfg
[global]
user = root
group = root
```

## low level discovery

`blackbird-fio-status` module discovers device name and vsu name.

