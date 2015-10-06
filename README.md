## Description

This is to test version upgrades of MySQL.
Now it installs the first version, then waits so you can load
data and then it goes through the whole upgrade cycle.

It uses `mysql_upgrade` to do a inplace upgrade.

## Requirements

* MySQL Sandbox
* Multiple MySQL versions, registered with MySQL Sandbox
* Python 3

If you can't find old versions on https://dev.mysql.com then have a look at http://mysql.mirror.facebook.net/.

## Todo

### Run certain operations in certain steps of the upgrade.

For example:

* After upgrade to 5.6 add fulltext index on InnoDB
* After upgrade to 5.7 add R-Tree index
* Add timestamp columns with microsecond precision

### Test replication

Make a 5.7 → 5.6 → 5.5 → 5.1 → 5.0 → 4.1 chain.

Test &lt;version&gt; → &lt;version-1&gt;

### Detect errors after upgrade

Try to detect these kinds of errors

* Sandbox doesn't start
* Critical errors in data/msandbox.err
