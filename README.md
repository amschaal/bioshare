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
 
Clone repository
~~~
git clone https://github.com/amschaal/bioshare.git
cd bioshare
~~~
Make a copy of the configuration file and edit it for your database and other settings
~~~
cp settings/config.py.example settings/config.py
~~~
Install all of the python requirements with pip.  Be sure to activate your virtualenv if you are using one
~~~
pip install -r requirements.txt
~~~

Ensure that you've created an empty MySQL database granting full privileges to the user specified in your config.py file.  You may now run the database migrations:
~~~
python manage.py migrate
~~~

TO BE CONTINUED...
