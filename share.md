Share
=====

![Share interface](/images/screenshots/share.png)

This is the main interface of Bioshare.  Here you can view, search, transfer files, and more.  A description of the various functionalities follows.

File list
---------
At the bottom of the interface is the list of files and directories for the share.  Along with the name, various attributes like size and modification date are available.  It is possible to sort files by clicking on the headers, as well as filter them using the input box just above the list.  Clicking on the filename will download that file.  If it is a directory, the link will take you to a directory listing. 

Individual File/Directory actions
---------------------------------
Under the "Actions" header, there are a few actions that can be taken on individual files or directories:
- Add/Edit Metadata: Add notes or comma seperated tags
- Modify file/directory name: Just like it sounds.  Only use alphanumeric characters, periods, underscores, or dashes.
- Create subshare (share owner only):  For the case of a directory, create a share that links to the directory.  The subshare will mirror exactly what is in the directory that was reshared.  This is useful if you want to assign additional permissions for that directory only.

File/Directory action buttons
-----------------------------
- Download:  Download multiple files or directories, instead of individually clicking on links.  Currently supported methods are zipfile (up to a certain size), SFTP, rsync, and wget.
- Upload:  Upload multiple files or directories.  Currently supported methods are by browser, SFTP, and rsync.
- Create folder:  Create a new directory in the current location.  Must abide by the naming restrictions for files and directories.
- Move:  Move selected files and directories into another location in the same share.
- Delete:  Permanently delete selected files and directories.


