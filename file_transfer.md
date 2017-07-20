Downloading/Uploading
=====================

There are multiple ways to download or upload files within Bioshare.  The simplest is generally by using the browser.  Here, files can simply be downloaded by clicking on a link, or by selecting a list of files and directories and downloading them as a zip file.  Uploads are simple as well, using the same mechanisms that most web applications use for selecting files to upload.

There are, however, times where transfering files using the browser is undesirable.  For large or numerous files, browsers do not handle failure well.  It can be difficult or time consuming to know where to things back up.  In these cases, tools like rsync, SFTP, or wget prove to be useful.

Another scenario where using the browser is impractical is when trying to transfer to or from another server.  If for example, I am browsing files on Bioshare using my laptop, but I ultimately want them available on my computing cluster, I would first need to download the files to my laptop, and then upload them from my laptop to the cluster.  This is both inefficient and time consuming.  A much more efficient method is to log in to the server where I want to store the data, then using command line tools (rsync, SFTP, wget), transfer the data directly.

SFTP
====
SFTP is something of a cross platform standard for secure file transfer.  It is available on most any operating system either as a GUI, or as a command line application
