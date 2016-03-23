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
# Use a backend-crypted or a crypted password
#SQLAuthTypes Backend Crypt
#
# Connection
SQLConnectInfo bioshare@localhost proftpd_user proftpd_password
#
# Describes both users/groups tables
#
#SQLUserInfo users userid passwd uid gid homedir shell
#SQLGroupInfo groups groupname gid members
#
SQLUserInfo bioshareX_shareftpuser share_id password NULL NULL home NULL

SqlLogFile /var/log/proftpd/sql.log
</IfModule>
~~~
