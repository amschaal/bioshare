These setup instructions have been tested with Ubuntu 14.04.  Other Linux distributions may vary.

Install ProFTPd and MySQL plugin.  If prompted, choose "standalone" option.
~~~
sudo apt-get install proftpd-basic proftpd-mod-mysql
~~~

Connect to MySQL and create a MySQL user that has read privileges for the "bioshareX_shareftpuser" table:
~~~
GRANT SELECT ON bioshare.bioshareX_shareftpuser TO 'proftpd_user' IDENTIFIED BY 'proftpd_password';
FLUSH PRIVILEGES;
~~~

In /etc/proftpd/proftpd.conf, make sure to enable the following options:
~~~
DefaultRoot                     ~
RequireValidShell               off
Include /etc/proftpd/sql.conf
~~~

Modify /etc/proftpd/sql.conf to look like the following:
~~~
<IfModule mod_sql.c>
  #
  # Choose a SQL backend among MySQL or PostgreSQL.
  # Both modules are loaded in default configuration, so you have to specify the backend
  # or comment out the unused module in /etc/proftpd/modules.conf.
  # Use 'mysql' or 'postgres' as possible values.
  #
  SQLBackend      mysql
  #
  SQLEngine on
  SQLAuthenticate users
  #
  # Use plaintext password
  SQLAuthTypes Plaintext
  #
  # Connection
  SQLConnectInfo bioshare@localhost proftpd_user proftpd_password
  #
  # Describes both users/groups tables
  #
  SQLUserInfo bioshareX_shareftpuser share_id password NULL NULL home NULL
  
  SqlLogFile /var/log/proftpd/sql.log
</IfModule>
~~~

/etc/proftpd/conf.d/sftp.conf
~~~
<IfModule mod_sftp.c>
  SFTPEngine on
  Port 2200
  SFTPLog /var/log/proftpd/sftp.log

  # Configure both the RSA and DSA host keys, using the same host key
  # files that OpenSSH uses.
  SFTPHostKey /etc/ssh/ssh_host_rsa_key
  SFTPHostKey /etc/ssh/ssh_host_dsa_key

  SFTPAuthMethods password

  # Enable compression
  SFTPCompression delayed
</IfModule>
~~~
