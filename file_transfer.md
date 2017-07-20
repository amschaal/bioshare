Downloading/Uploading
=====================

There are multiple ways to download or upload files within Bioshare.  The simplest is generally by using the browser.  Here, files can simply be downloaded by clicking on a link, or by selecting a list of files and directories and downloading them as a zip file.  Uploads are simple as well, using the same mechanisms that most web applications use for selecting files to upload.

There are, however, times where transfering files using the browser is undesirable.  For large or numerous files, browsers do not handle failure well.  It can be difficult or time consuming to know where to things back up.  In these cases, tools like rsync, SFTP, or wget prove to be useful.

Another scenario where using the browser is impractical is when trying to transfer to or from another server.  If for example, I am browsing files on Bioshare using my laptop, but I ultimately want them available on my computing cluster, I would first need to download the files to my laptop, and then upload them from my laptop to the cluster.  This is both inefficient and time consuming.  A much more efficient method is to log in to the server where I want to store the data, then using command line tools (rsync, SFTP, wget), transfer the data directly.

SFTP
====

SFTP is something of a cross platform standard for secure file transfer.  It is available on most any operating system either as a GUI, or as a command line application.  Bioshare supports both downloads and uploads using SFTP.

Using FileZilla
---------------
As far as graphical applications that support SFTP go, I often suggest [FileZilla](https://filezilla-project.org), as it is free, open source, and available on Windows, Mac, and Linux.  There are plenty of other options as well, such as Cyberduck, but not all support all platforms.

The simplest way to connect to Bioshare using FileZilla is simply by using the "Quickconnect" parameters at the top of the window.  Here, you need to enter the host (ie: sftp://bioshare.bigdata.org), username (same as you log into Bioshare with), password (again, same as you log in with), and port (depends on how Bioshare was configured).  Once entered, click "Quickconnect" and you should see some details below as FileZilla attempt to log in.  After successful authentication, you'll have a list of all of your available shares on the right side of the window.  You can simply drag and drop files or directories between Bioshare and your local machine.

Using the command line
----------------------
Again, this is a useful option when trying to transfer files to/from a remote server.  Connecting using sftp is quite simple, and will look something like (depending on port number, username, etc):
```
sftp -P 2200 'joe@bigdata.org'@bioshare.bigdata.org
```
To view a list of shares, use the "ls" command.  To change into a directory, use "cd DIRECTORY_NAME".  To download files, use "get FILENAME".  If it is a directory, use "get -r DIRECTORY_NAME".  For uploading files, use "put /local/path/to/file" or for a directory "put -r /local/path/to/directory".  These are a few very simple examples.  For more details on how to use sftp on the linux or mac command line, see the [manual](https://man.openbsd.org/sftp).
