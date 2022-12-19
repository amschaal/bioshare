#! /bin/sh
service ssh start
runuser -l bioshare -c 'python /usr/src/app/manage.py start_sftp' &
runuser -l bioshare -c 'python /usr/src/app/manage.py runserver 0.0.0.0:8000'
