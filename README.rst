Pulse
=====

Pulse is a file manager and version control system for animation film project aimed at remote co-working.

Why would you need Pulse?

- you need to split a project between multiple locations, even with low bandwidth remote artists.
- you need to have the exact same path to access files for everyone involved
- you need to optimize your local network charge and load your files faster
- you need to guarantee your data integrity, by freezing and versionning every published file
- you need to choose where and how each resource will be stored, transparently for the artist

Version Control System
======================
You can think of Pulse as a version control system. Like SVN, the user checkout the resource to get a working copy,
and commit to publish a new version. Pulse shares a few concepts with other VCS:

- Pulse manages the versionning, the user doesn't think about it, he just commits
- a committed resource won't be modified anymore, never. You can rely on your data.
- there's a diff system, showing you the change you made since last version.
- there's a lock system, preventing concurrent work

But they are also a few differences which make Pulse so spicy...

Resource path consistency
=========================
Pulse don't deal with files, it deals with resources.
A resource is one or many files created, work and linked together. A character modeling is a resource, a shot layout is a resource, etc...
The resource is the project's unit : a resource can't be split between repositories, a resource is versioned as a whole.
Unlike other VCS, the user doesn't chose the resource path, it is built by Pulse based on the project configuration. The user just check out the resource by its name, and the files will be downloaded at the very same path for everyone else working on the project.


Tracking Dependencies
=====================
Another difference from a classical version system, is the dependencies tracking. If a user needs to add an input to his working copy, he has to declare it. All resources inputs and outputs are tracked by Pulse. So when a user checkout a resource, all the needed inputs will be downloaded in the user cache, only if they're not already there. He can even check out all the resources during the night, to optimize his bandwidth.
Dependencies tracking also helps to purged unused resources. Pulse have utilities for this based on the unused time.


Storage Freedom
===============
Each Pulse Resource is linked to a repository, and your project can contain many repository, even from different type :
network share, ftp, google drive...
Pulse even comes with a plug-in adapter architecture which allow you
to write your very own repository type.


.. image:: multirepo.png
    :align: center



Q/A
===

My artists work all in the same location, what's the point to use Pulse?
    Yes! Pulse act like a local cache, even with to leverage server access even in the same network


What's the difference between Pulse and Shotgun?
    Pulse is not a production tracker, it does not care about what's approved or done. (even if you could use
    metadata to carry extra information)


