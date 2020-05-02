Pulse
=====

Pulse is designed to help artists and studios to work together even if they aren't on the same location and with a law bandwidth.

Pulse manage complexity for you this main areas :

- project structure : every one working on a project use the same filepath
- versionning system : every one sharing a resource will use the same tools
- optimize bandwidth : only the needed dependencies are sent to artist


Further from this, Pulse will also :

- manage the resource versionning : every time a resource is published, a new immutable version will be created
- a lock system will prevent concurrent editing
- store files the way you like : ftp, vpn, and you can define multiple repositories for the same project.

.. image:: multirepo.png
    :align: center




Version Control
===============

You can see Pulse as version control system. But unlike SVN or Git, users doesn't deal with arbitrary files, it deals with resources.
A resource is a group of files an artist will modify, share and reference together to accomplish a project (typically, a movie).
The resource path are relevant to project configuration, thus the user doesn't care about this, he just have to checkout and commit.

Some command line examples:


Customizing
===========

Pulse managed only the way artists access to files, the way you store published files and pulse data are up to you.
By default Pulse comes with a repository adapter to write files on FTP, and another one on a network share.
But you can easily write your own repository adapter to write files on cloud. With the same versatility in mind
by default Pulse data are stored on a json database, you can write your own adapter to save them in your database system,
or your production tracker.

Pulse have a hook system to give you the opportunity to insert your own logic between the main user action : pre commit,
post commit, pre checkout, post checkout, etc...

Q/A
===

My artists work all in the same location, what's the point to use Pulse?
    Yes! Pulse act like a local cache, even with to leverage server access even in the same network


What's the difference between Pulse and Shotgun?
    Pulse is not a production tracker, it does not care about what's approved or done. (even if you could use
    metadata to carry extra information)


