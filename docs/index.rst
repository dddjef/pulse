.. Pulse documentation master file, created by
   sphinx-quickstart on Mon Jun  1 21:40:09 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Pulse's documentation!
=================================

Pulse is a resource version control system. I think you already know what a version control system is (GIT, SVN, etc..)
but what the heck is a resource?

When one need to break apart a project in little pieces for team working, for versionning, it's a resource.
A resource can be a prop's modeling, a character's rigging, a shot's animation...

Pulse is written object oriented, and thus you will also meet other concepts than the resource. This is how
they articulate.


.. image:: pulse_objects.png
    :align: center

API Installation
=================================
Pulse APi is written in pure python, you don't need to install any external libraries to use it.

You'll need to add /python directory to you python path. Then you can use the launch the standard test :
/tests/test.py

By default, test data are generated under the tests directory, they are ignored by git

Adapters
=================================

To connect to a database or a file repository, Pulse has an "adapter" strategy.
You can find them in /python/pulse/database_adapters and /python/pulse/repository_adapters
In each folder you will find an interface_class.py you can derive from.
An adapter determine the way you want to share data : the protocol you will use, and how it's stored.
It's transparent for the user.

By default, API is set to use json_db.py adapter for database, and file_storage.py for file
repository.

json_db.py is a very simple database, writing data to json files, stored in their class directory. It's mainly
used for testing the api, because it's fast and easy to debug. But you could use it for simple projects where
everybody work on the same network.

file_storage.py is a simple file repository system. It can stores files in any path writable for the user.
This adapter is also used for the api test, because it's fast and easy to debug. It's also a good choice
if you wish to store all the project's resources under a single network path.

Custom adapters
=================================
You can write your own adapters, but Pulse also come with two custom adapters : a mysql database adapter,
and a ftp repository adapter.
Those adapters have their own test file : test_custom_adapters.py. Of course, you will have to setup a few things before
using it.

First, you will have to install mysql connector, available with pip : # pip install mysql-connector-python

Then you will have to create a tests/custom_adapters_config.ini according to your own connection parameters.
The mysql adapter has been test with mariaDB 10 server. The mysql account you will mention needs to have permission to
create or remove a database. The ftp account needs to write and delete in the root folder you will mention.


.. code-block:: ini

   [db]
   host=192.168.1.2
   port=3306
   login=pulseAdmin
   password=***
   [ftp]
   host=192.168.1.2
   port=21
   login=pulseTest
   password=***
   root=pulseTest/


.. toctree::
   :maxdepth: 2
   :caption: Contents:

.. automodule:: pulse.api

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
