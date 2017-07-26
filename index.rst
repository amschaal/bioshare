.. Bioshare documentation master file, created by
   sphinx-quickstart on Wed Jul 26 17:29:48 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Bioshare's documentation!
====================================

About Bioshare
==============

|Share interface| Bioshare is a file sharing web application designed
for sharing the “Big Data” common to bioinformatics. While it was
developed to support the effective sharing of larger datasets, it can
and has been used to share all kinds of data, large and small.

The central goals of Bioshare are:

-  To easily share data with any collaborator. The only thing that is
   needed is an email address.
-  To permit granular permissions, for different levels of access. Users
   can read, write, or administer data shares. See `share permissions`_
   for more details.
-  To provide a variety of file transfer protocols to fit a variety of
   different scenarios. Bioshare currently supports file transfers via
   the browser, SFTP, rsync, and wget.
-  To provide a user friendly interface, which makes searching,
   browsing, and viewing/downloading files easy.

User Guide
==========

Below are links to pages which describe the essential functions of
Bioshare. 



.. |Share interface| image:: /images/screenshots/share.png

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   home.md
   share.md
   create_share.md
   permissions.md
   file_transfer.md

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _share permissions: permissions.md
.. _Home page: home.md
.. _Create Share: create_share.md
.. _Share: share.md
.. _Share permissions: permissions.md
.. _Transfering data: file_transfer.md
