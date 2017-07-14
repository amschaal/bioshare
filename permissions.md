Share permissions
=================

![Share permissions](/images/screenshots/permissions.png)

It is from this page that share admins can manage permissions for the share.  Here, they can share with users or groups, and assign them fine tuned permissions.

General Settings - Secure share
-------------------------------
Check this box if you want users to have to authenticate to view/download files.  If it is not checked, anyone with the URL can access the share.  If checked, a user must be listed in the permissions with browse and download permissions in order to view the share.

Regardless of this setting, users have to be authenticated and have appropriate permissions in order to write, delete, or administer the share.

Permissions
-----------
Using the textarea, enter email addresses seperated by commas for people to be added to the share.  If sharing with a group, you can use the group name instead of an email address.  The group name must be prefixed by "Group:", for example, "Group:my group".  If you have previously shared with that user or group, it may try to autocomplete the address or group name.  After having entered users and/or groups, click on the "Add" button.  They will then be added to the list of users with permissions below.  **They do not yet have permission.**  In order to finish assigning permissions, it is necessary to click on the "Update" button below the list of user permissions.  A description of that process follows.

Permission list
---------------
All users and groups with permissions for the share are listed in this table.  Each row represents a user or a group, and the columns are as follows:
- User (or group): The email address or group name.  An icon will be shown here to warn if the user is being added.  An icon will also be shown indicating whether they will receive an email.
- Browse: This base permission is required to be able to even view the share.
- Download:  Required to be able to downlod files.  If browse and download are selected, the user will also be able to download via SFTP or rsync.
- Write:  Required to create/upload/rename files and directories.
- Delete:  Required to delete files and directories.  Additionally, this permission is required in order to upload via rsync.
- Administer:  Allows the user or group to perform administrative tasks, including modifying the share's permissions.
- Select/Deselect all:  Convenience buttons for rapidly selecting or deselecting permissions.

Below the list, there is a "Send email" checkbox.  If selected, any user/group who is newly added to the share permissions will be sent an email with a link to the share.

Users who do not yet exist in the system will be sent an email with their new user credentials and a link to the share, regardless of if the box is checked.

If a user or group has had their permissions changed, that row will be highlighted in yellow.  Please note, that no permissions will be updated until the "Update" button is clicked.  Once the update button is clicked, a confirmation message should appear in the upper right corner of the screen, and no more rows should be highlighted in yellow.
