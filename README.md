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


