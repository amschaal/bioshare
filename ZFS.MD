Instead of using standard directories to store data, Bioshare can be configured to use ZFS filesystems. If the server being used supports ZFS, a few settings are necessary.  Firstly, you need to have a FileSystem instance, configurable through the Django admin, which is of type ZFS.  There are also a couple of settings to add in config.py:

```python
ZFS_BASE = 'poolname/bioshare/shares' # zfs create will happen under this location, and the path for the filesystem created in the Django admin in this example would be "/poolname/bioshare/shares"
ZFS_CREATE_COMMAND = ['sudo', '/path/to/custom/zfs_create.sh']  # Not required, but you can create a custom script for zfs create which takes as an argument the share ID, such as "poolname/bioshare/shares/{share_id}".  The default command otherwise is ['zfs', 'create'].
ZFS_DESTROY_COMMAND = ['sudo', '/path/to/custom/zfs_destroy.sh'] # similar to zfs create, except for destroy where the default is ['zfs', 'destroy'].
```

OpenZFS in Linux has some quirks, which makes simply running "zfs create poolname/bioshare/{share_id}" not work properly.  While a regular user may create a ZFS filesystem, they cannot mount it.  This has to be done as root.  As a result, either the entire "zfs create" command must be run as root, or "zfs create -u" can be run as the normal user, and then "zfs mount" as root.  However you decide to do it, the bioshare user will need to be able to run something as root.  This can be accomplished with some simple entries into a sudoers file such as:

```
bioshare ALL = (root) NOPASSWD: /path/to/custom/zfs_create.sh poolname/bioshare/shares/*
bioshare ALL = (root) NOPASSWD: /path/to/custom/zfs_destroy.sh poolname/bioshare/shares/*
```

In the above example, it is worth checking the inputs to the commands running as sudo, to ensure nothing malicious gets in with the zfs path (although user input is not relied on to generate this argument, and zfs create and zfs destroy only take a single argument and complain otherwise).

When running zfs create or mount as sudo, ownership may also be wrong, so in the create script, it might be necessary to chown the newly mounted directory as bioshare:bioshare.

If using apache and ZFS, there is one more potential gotcha.  If mounting a filesystem from apache, as is done when using zfs create/mount, that mount point may be made in a different namespace.  It will initially work for apache until restart, but won't work on the system, which is important for a variety of reasons such as use by the SFTP server or rsync.  This can be avoided by setting "PrivateTmp=false" in systemd for the apache service.  On Ubuntu, this can be found in this file:
```
/etc/systemd/system/multi-user.target.wants/apache2.service
```
To avoid having changes lost during system updates, etc, the setting should actually be overriden using:
```
systemctl edit apache2.service
```
and adding the following lines:

```
[Service]
PrivateTmp=false
```
You'll need to restart systemd and apache afterward.
