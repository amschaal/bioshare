# Bioshare
A file sharing web application designed for sharing the "Big Data" common to bioinformatics.  

Application supports web, sftp, and rsync protocols for uploading/downloading data, utilizing user permissions set within the application.

Installation
------------

### Requirements ###

1. Linux (tested w/ Ubuntu 14.04) 
2. Apache 2.4+, mod_ssl, mod_wsgi, mod_xsendfile
3. Python 2.7.x (virtualenv recommended)
4. MySQL Server (tested w/ MySQL 5.5)
5. Python & MySQL dev libraries (python-dev and libmysqlclient-dev on Ubuntu)
6. (Optionally) ProFTPD for SFTP download support 
 
Clone the repository:
~~~
git clone https://github.com/amschaal/bioshare.git
cd bioshare
~~~
Make a copy of the configuration file and edit it for your database and other settings:
~~~
cp settings/config.py.example settings/config.py
~~~
Copy footer.template.html to footer.html, and modify for your organization.
~~~
cp footer.template.html footer.html
~~~
Install all of the python requirements with pip.  Be sure to activate your virtualenv if you are using one:
~~~
pip install -r requirements.txt
~~~

Collect all of the static files (CSS, JS, images, ...) into the static directory to serve from the web server:
~~~
python manage.py collectstatic
~~~

Ensure that you've created an empty MySQL database granting full privileges to the user specified in your config.py file.  You may now run the database migrations:
~~~
python manage.py migrate
~~~

Create a new superuser, entering a username, email, and password:
~~~
python manage.py createsuperuser
~~~

At this point you may be able to run the development server to see if the configuration file and database are properly set up:
~~~
python manage.py runserver
~~~

Please only use the development server to test your configuration.  Once that is working properly, you'll want to set it up with a production web server.  A sample Apache configuration is included in the apache_example.conf file.

Hopefully you are able to bring up Bioshare in your browser, and are able to log in with your superuser you created.  At this point you'll need to configure one or more filesystems in the Django admin.  Navigate to "https://yourbiosharedomain.net/admin/bioshareX/filesystem/add/", and add a place on the filesystem where you want to store data.  Be sure that apache has read, write, and execute permissions on any directories you add.

At this point, you'll need to make sure that both the web server (apache) as well as the rsync user have access to configured filesystems.  First, create a bioshare group and user within that group.  Be sure to give the bioshare user a home directory using the "-m" option.  The user needs a home directory for rsyncing, so that ssh public keys can be added in "~/.ssh/authorized_keys".
~~~
addgroup bioshare
useradd -m bioshare -G bioshare
usermod www-data --append --groups bioshare
~~~

Change permissions to filesystem (as an example, /data/bioshare) so that the bioshare group and user have read, write, and execute privileges, along with the 's' bit so that shares are also created with the bioshare group.  Now apache can't write to the filesystem however, so we'll add it to the bioshare group.
~~~
chmod -R bioshare:bioshare ug+rwxs /data/bioshare
usermod www-data --append --groups bioshare
~~~

###Rsync###
There are a few settings to modify in settings/config.py.  Tweak the following as necessary:
~~~
# The authorized_keys file must have 600 permissions, so "chmod 600 /home/bioshare/.ssh/authorized_keys" should work
AUTHORIZED_KEYS_FILE = '/home/bioshare/.ssh/authorized_keys'
RSYNC_URL = 'bioshare@server.domain.net'
# Optional, but should be writeable by bioshare user
RSYNC_LOGFILE = '/home/bioshare/rsync_wrapper.log' 
# This is set to system python in settings.py, but you may need to override this if using virtual environments
PYTHON_BIN = '/virtualenv/bioshare/bin/python' 
~~~

There is an added complication when trying to set up rsync support in Bioshare.  When users upload their SSH public keys, the webserver needs to be able to write them to the AUTHORIZED_KEYS_FILE.  As noted above, this file has to be readable and writable ONLY by the bioshare (rsync/ssh) user.  In order to get around this, we just run apache as the bioshare user.  You can see how to configure this in the example apache configuration file.

