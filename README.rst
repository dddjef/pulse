Pulse
=====

Pulse is designed to help artists to work on the same project even if they aren't on the same location and with a law bandwidth.

As a resource file system, a studio using Pulse in his pipeline can collaborate transparently with another one.

To achieve this miracle, Pulse will :

- ensure every one working on a project access files the same way, with the same paths.
- take the minimal bandwidth : only the needed versions and dependencies are sent to work
- manage the resource versionning : every time a resource is published, a new immutable version will be created
- a lock system will prevent concurrent editing


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

My artists works all in the same location, is it interesting to use Pulse?
    Yes! Pulse act like a local cache, even with to leverage server access even in the same network


What's the difference between Pulse and Shotgun?
    Pulse is not a production tracker, it does not care about what's approved or done. (even if you could use
    metadata to carry extra information)


