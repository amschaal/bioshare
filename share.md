Share
=====

![Share interface](/images/screenshots/share.png)

This is the main interface of Bioshare.  Here you can view, search, transfer files, and more.  A description of the various functionalities follows.

Share information
-----------------
At the top of the interface are links which indicate the share's name, as well as the full path to the current subdirectory, if applicable.  Clicking on the links will bring you to that particular directory in the share.  Below the share actions is a box containing general information about the share, including the owner, who it is being shared with, a description, tags, and a link that can be clicked to calculate the size of the current directory (including sub-directories).  

Share actions
-------------
To the right of the share name, there are a few buttons that perform actions for the entire share:
- Email:  Opens a dialog that permits the user to quickly send an email to all accounts that have access to the share.
- Permissions:  Redirects to the page for [managing share permissions](permissions.md).
- Edit:  Redirects to a form that allows the user to update share details.
- Delete Share:  Delete the share and all it's contents.  Confirmation will be required prior to deletion.

File list
---------
At the bottom of the interface is the list of files and directories for the share.  Along with the name, various attributes like size and modification date are available.  It is possible to sort files by clicking on the headers, as well as filter them using the input box just above the list.  Clicking on the filename will download that file.  If it is a directory, the link will take you to a directory listing. 

File/Directory action buttons
-----------------------------
- Download:  Download multiple files or directories, instead of individually clicking on links.  Currently supported methods are zipfile (up to a certain size), SFTP, rsync, and wget.
- Upload:  Upload multiple files or directories.  Currently supported methods are by browser, SFTP, and rsync.
- Create folder:  Create a new directory in the current location.  Must abide by the naming restrictions for files and directories (alphanumeric characters, periods, underscores, or dashes).
- Move:  Move selected files and directories into another location in the same share.
- Delete:  Permanently delete selected files and directories.

Individual File/Directory actions
---------------------------------
Under the "Actions" column, there are a few actions that can be taken on individual files or directories:
- Add/Edit Metadata: Add notes or comma seperated tags
- Modify file/directory name: Just like it sounds.  Only use alphanumeric characters, periods, underscores, or dashes.
- Create subshare (share owner only):  For the case of a directory, create a share that links to the directory.  The subshare will mirror exactly what is in the directory that was reshared.  This is useful if you want to assign additional permissions for that directory only.
