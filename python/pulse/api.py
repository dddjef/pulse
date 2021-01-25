"""
Created on 07 September 2020
@author: Jean Francois Sarazin
"""

import json
import os
import file_utils as fu
import shutil
import time
import imp
from pulse.database_adapters.interface_class import *
from pulse.exception import *
import pulse.uri_standards as uri_standards
import tempfile
from datetime import datetime


DEFAULT_VERSION_PADDING = 3
DEFAULT_VERSION_PREFIX = "V"
template_name = "_template"
pulse_filename = ".pulse"


class PulseDbObject:
    """
        abstract class for all objects which need to save persistent data
    """
    def __init__(self, project, uri):
        self.uri = uri
        """universal resource identifier - string"""
        self.project = project
        """the project this object rely to - Project"""
        self.metas = {}
        """Store custom attributes, passed to repository - dict"""
        self._storage_vars = []
        """list of attributes name saved in db - list"""

    def _db_update(self, attribute_list):
        """
            save selected attributes value to database

            :param: attribute_list: attributes name which will be saved to database
            :type: attribute_list: list
        """
        data = dict((name, getattr(self, name)) for name in attribute_list)
        self.project.cnx.db.update(self.project.name, self.__class__.__name__, self.uri, data)

    def db_read(self):
        """
            read all object attributes from database.

            Will pass if the database have an attribute missing on the object

            :return: PulseDbObject
            :rtype: PulseDbObject
        """
        data = self.project.cnx.db.read(self.project.name, self.__class__.__name__, self.uri)
        for k in data:
            if k not in vars(self):
                continue
            setattr(self, k, data[k])
        return self

    def db_create(self):
        """
            initialize the object in database

            use all the attributes lists in ._storage.vars and save them to the DB
            the key is the uri
            raise DbError if the object already exists
        """
        data = dict((name, getattr(self, name)) for name in self._storage_vars)
        self.project.cnx.db.create(self.project.name, self.__class__.__name__, self.uri, data)


class Product:
    """
        abstract class for all products
    """
    def __init__(self, parent, product_type):
        self.uri = uri_standards.convert_from_dict({
            "entity": parent.resource.entity,
            "resource_type": parent.resource.resource_type,
            "product_type": product_type,
            "version": parent.version
        })
        self.parent = parent
        self.product_type = product_type
        self.directory = os.path.join(parent.get_products_directory(), product_type)
        self.product_users_file = os.path.join(self.directory, "product_users.pipe")

    def add_product_user(self, user_directory):
        """
        add a local resource or product as product's user

        :param user_directory: the resource path
        """
        fu.json_list_append(self.product_users_file, user_directory)

    def remove_product_user(self, user_directory):
        """
        remove the specified local resource or product from the product's user

        :param user_directory: the resource path
        """
        fu.json_list_remove(self.product_users_file, user_directory)

    def get_product_users(self):
        """
        return the list of local resources or product using this product

        :return: resources filepath list
        """
        return fu.json_list_get(self.product_users_file)

    def get_unused_time(self):
        """
        return the time since the local product has not been used by any resource or product.
        Mainly used to purge local products from pulse's cache

        :return: time value
        """
        if not os.path.exists(self.directory):
            return -1
        users = self.get_product_users()
        if users:
            return -1
        if os.path.exists(self.product_users_file):
            return time.time() - os.path.getmtime(self.product_users_file) + 0.01
        else:
            return time.time() - os.path.getctime(self.directory)


class CommitProduct(PulseDbObject, Product):
    """
        Product which has been published to database
    """
    def __init__(self, parent, product_type):
        Product.__init__(self, parent, product_type)
        PulseDbObject.__init__(self, parent.project, self.uri)
        self.products_inputs = []
        self._storage_vars = ['product_type', 'products_inputs', 'uri']

    def download(self):
        """
        download the product to local pulse cache

        :return: the product's local filepath
        """
        self.project.cnx.repositories[self.parent.resource.repository].download_product(self)
        if not os.path.exists(self.parent.pulse_filepath):
            open(self.parent.pulse_filepath, 'a').close()

        fu.write_data(self.product_users_file, [])
        self.register_to_user_products()
        for uri in self.products_inputs:
            product = self.project.get_product(uri)
            product.download()
            product.add_product_user(self.directory)
        return self.directory

    def register_to_user_products(self):
        """
        register the product to the user local products list
        """
        fu.json_list_append(self.project.cfg.get_user_products_list_filepath(), self.uri)

    def unregister_to_user_products(self):
        """
        unregister the product to the user local products list
        """
        fu.json_list_remove(self.project.cfg.get_user_products_list_filepath(), self.uri)

    def remove_from_user_products(self, recursive_clean=False):
        """
        remove the product from local pulse cache
        will raise a pulse error if the product is used by a resource
        will raise an error if the product's folder is locked by the filesystem
        """
        if len(self.get_product_users()) > 0:
            raise PulseError("Can't remove a product still in use")

        # test the folder can be moved
        if not fu.test_path_write_access(self.directory):
            raise PulseError("folder is in used by a process : " + self.directory)

        # unregister from its inputs
        for uri in self.products_inputs:
            product_input = self.project.get_product(uri)
            product_input.remove_product_user(self.directory)
            if recursive_clean:
                try:
                    product_input.remove_from_user_products(recursive_clean=True)
                except PulseError:
                    pass
        for path, subdirs, files in os.walk(self.directory):
            for name in files:
                filepath = os.path.join(path, name)
                if filepath.endswith(".pipe"):
                    os.chmod(filepath, 0o777)
        shutil.rmtree(self.directory)
        # remove also the version directory if it's empty now
        fu.remove_empty_parents_directory(os.path.dirname(self.directory), [self.project.cfg.get_product_user_root()])
        self.unregister_to_user_products()


class Commit(PulseDbObject):
    """
        Object created when a resource has been published to database
        The commit is a versionned resource
    """
    def __init__(self, resource, version):
        self.uri = resource.uri + "@" + str(version)
        PulseDbObject.__init__(self, resource.project, self.uri)
        self.resource = resource
        self.comment = ""
        self.files = []
        self.products_inputs = []
        self.version = int(version)
        self.products = []
        self.pulse_filepath = os.path.join(self.get_products_directory(), pulse_filename)
        """ list of product names"""
        self._storage_vars = ['version', 'products', 'files', 'comment']

    def get_product(self, product_type):
        """
        return the commit's product with the specified product type. If the product doesn't exists return a
        pulseDataBaseMissingObject exception

        :param product_type: string
        :return: a CommitProduct
        """
        return CommitProduct(self, product_type).db_read()

    def get_products(self):
        """
        return the commit's products list
        """
        products = []
        for product_name in self.products:
            products.append(CommitProduct(self, product_name))
        return products

    def get_products_directory(self):
        """
        return the commit's products directory

        :return: filepath
        """
        return self.resource.get_products_directory(self.version)


class WorkNode:
    """
        abstract class for unpublished data (work or product)
    """
    def __init__(self, project, directory):
        self.directory = directory
        self.products_inputs_file = os.path.join(directory, "product_inputs.json")
        self.project = project

    def get_inputs(self):
        """
        return a list of products used by this local work or product

        :return: products uri list
        """
        return [self.project.get_product(uri) for uri in fu.json_list_get(self.products_inputs_file)]

    def add_input(self, product):
        """
        add a local product to work or product inputs list

        :param product: product object
        """
        if not os.path.exists(product.directory):
            # if the product is a WorkProduct try to convert it first
            product = self.project.get_product(product.uri)
            product.download()
        fu.json_list_append(self.products_inputs_file, product.uri)
        product.add_product_user(self.directory)

    def remove_input(self, local_product):
        """
        remove a product from object's inputs list

        :param local_product: local product object
        """
        fu.json_list_remove(self.products_inputs_file, local_product.uri)
        local_product.remove_product_user(self.directory)


class WorkProduct(Product, WorkNode):
    """
        class for products which has not been registered to database yet
    """
    def __init__(self, work, product_type):
        Product.__init__(self, work, product_type)
        WorkNode.__init__(self, work.project, self.directory)


class Work(WorkNode):
    """
        Resource downloaded locally to be modified
    """
    def __init__(self, resource):
        WorkNode.__init__(self, resource.project, resource.sandbox_path)
        self.resource = resource
        self.version = None
        self.data_file = os.path.join(self.directory, "work.pipe")
        
    def _check_exists_in_user_workspace(self):
        if not os.path.exists(self.directory):
            raise PulseMissingNode("Missing work space : " + self.directory)

    def _get_trash_directory(self):
        date_time = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        path = os.path.join(self.project.cfg.get_work_user_root(), self.project.name, "TRASH") + os.sep
        path += self.resource.resource_type + "-" + self.resource.entity.replace(":", "_") + "-" + date_time
        return path

    def _get_work_files(self):
        files_dict = {}
        for root, dirs, files in os.walk(self.directory, topdown=True):
            # ignore pulse version directory
            dirs[:] = [d for d in dirs if pulse_filename not in os.listdir(os.path.join(root, d))]
            for f in files:
                filepath = os.path.join(root, f)
                relative_path = filepath[len(self.directory):]
                files_dict[relative_path.replace(os.sep, "/")] = {"checksum": fu.md5(filepath)}
        return files_dict

    def get_product(self, product_type):
        """
        return the resource's work product based on the given type

        :param product_type:
        :return: a work product
        """
        return WorkProduct(self, product_type)

    def list_products(self):
        """
        return the work's product's type list

        :return: a string list
        """
        return fu.read_data(self.data_file)["outputs"]

    def create_product(self, product_type):
        """
        create a new product for the work

        :param product_type: string
        :return: the new work product object
        """
        self._check_exists_in_user_workspace()
        outputs = self.list_products()
        if product_type in outputs:
            raise PulseError("product already exists : " + product_type)
        work_product = WorkProduct(self, product_type)
        os.makedirs(work_product.directory)
        pulse_filepath = os.path.join(self.get_products_directory(), pulse_filename)
        if not os.path.exists(pulse_filepath):
            open(pulse_filepath, 'a').close()
        # update work pipe file with the new output
        outputs.append(product_type)
        data_dict = fu.read_data(self.data_file)
        data_dict["outputs"] = outputs
        fu.write_data(self.data_file, data_dict)

        return work_product

    def trash_product(self, product_type):
        """
        move the specified product to the trash directory

        :param product_type: string
        """
        self._check_exists_in_user_workspace()
        if product_type not in self.list_products():
            raise PulseError("product does not exists : " + product_type)
        product = WorkProduct(self, product_type)

        if not fu.test_path_write_access(product.directory):
            raise PulseError("can't move folder " + product.directory)

        users = product.get_product_users()
        if users:
            raise PulseError("work can't be trashed if its product is used : " + users[0])

        # unregister from products
        for input_product in product.get_inputs():
            if os.path.exists(input_product.directory):
                input_product.remove_product_user(self.directory)

        # create the trash work directory
        trash_directory = self._get_trash_directory()
        if not os.path.exists(trash_directory):
            os.makedirs(trash_directory)

        # move folder
        shutil.move(product.directory, os.path.join(trash_directory, "PRODUCTS", product_type))

        # remove the product from work outputs
        data_dict = fu.read_data(self.data_file)
        data_dict["outputs"].remove(product_type)
        fu.write_data(self.data_file, data_dict)

        # remove the products directory if it's empty
        products_directory = self.get_products_directory()
        if not os.listdir(products_directory):
            shutil.rmtree(products_directory)

    def write(self):
        """
        write the work object to user workspace
        """
        # create work folder if needed
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)

        # remove old version file
        old_version_file = self.version_pipe_filepath(self.resource.last_version)
        if os.path.exists(old_version_file):
            os.remove(os.path.join(self.directory, old_version_file))

        # create the new version file
        new_version_file = self.version_pipe_filepath(self.version)
        with open(new_version_file, "w") as write_file:
            json.dump({"created_by": self.resource.project.cnx.user_name}, write_file, indent=4, sort_keys=True)

        # write data to json
        fu.write_data(self.data_file, {
            "version": self.version,
            "entity": self.resource.entity,
            "resource_type": self.resource.resource_type,
            "outputs": [],
            "work_files": self._get_work_files()
            })

    def read(self):
        """
        read the work data from user work space
        if the work doesn't exists in user work space, raise a pulse error

        :return: the updated work
        """
        if not os.path.exists(self.directory):
            raise PulseError("work does not exists : " + self.directory)
        work_data = fu.read_data(self.data_file)
        self.version = work_data["version"]
        return self

    def commit(self, comment="", trash_unused_products=False):
        """
        commit the work to the repository, and publish it to the database

        :param comment: a user comment string
        :param trash_unused_products: if a work's product is not used anymore, move it to trash
        :return: the created commit object
        """
        self._check_exists_in_user_workspace()
        # check current the user permission
        if self.resource.user_needs_lock():
            raise PulseError("resource is locked by another user : " + self.resource.lock_user)

        # check the work is up to date
        expected_version = self.resource.last_version + 1
        if not self.version == expected_version:
            raise PulseError("Your version is deprecated, it should be " + str(expected_version))

        # check the work status
        if not self.status():
            raise PulseError("no file change to commit")

        # check all inputs are registered
        for product in self.get_inputs():
            if isinstance(product, WorkProduct):
                raise PulseError("Work can't be committed, it uses an unpublished product : " + product.uri)

        products_directory = self.get_products_directory()

        # lock the resource to prevent concurrent commit
        lock_state = self.resource.lock_state
        lock_user = self.resource.lock_user
        self.resource.set_lock(True, self.project.cnx.user_name + "_commit", steal=True)

        # copy work files to a new version in repository
        commit = Commit(self.resource, self.version)
        commit.project.cnx.repositories[self.resource.repository].upload_resource_commit(
            commit, self.directory, self._get_work_files(), products_directory)

        # register changes to database
        commit.comment = comment

        commit.products_inputs = self.get_inputs()
        commit.products = self.list_products()
        products = []
        # if there's no product, delete the products version directory
        if commit.products:
            # register work products to user products list
            for product_type in commit.products:
                work_product = self.get_product(product_type)

                product = CommitProduct(commit, product_type)
                products.append(product)
                product.products_inputs = [x.uri for x in work_product.get_inputs()]
                product.db_create()
                product.register_to_user_products()

                if trash_unused_products and product.get_unused_time() > 0:
                    product.remove_from_user_products()

        commit.db_create()
        self.resource.set_last_version(self.version)

        # increment the work and the products files
        self.version += 1
        self.write()

        # restore the resource lock state
        self.resource.set_lock(lock_state, lock_user, steal=True)

        return commit

    def revert(self):
        """
        revert local changes to the work and its product directory

        :return: True on success
        """
        # trash the current content
        self.trash(no_backup=True)
        # checkout the last work commit version
        self.resource.checkout(index=self.version - 1)
        return True

    def update(self):
        """
        update local work copy to the last resource commit
        fails if there's some local changes

        :return: True on success
        """
        # test there's no changes that could be lost
        if self.status():
            raise PulseError("local changes detected, you should commit or revert your work first")
        # delete the work
        self.trash(no_backup=True)
        # checkout the last resource commit version
        self.resource.checkout()
        return True

    def trash(self, no_backup=False):
        """
        remove the work from user workspace

        :param no_backup: if False, the work folder is moved to trash directory. If True, it is removed from disk
        :return: True on success
        """
        self._check_exists_in_user_workspace()
        # test the work and products folder are movable
        products_directory = self.get_products_directory()
        for path in [self.directory, products_directory]:
            if os.path.exists(path) and not fu.test_path_write_access(path):
                raise PulseError("can't move folder " + path)

        # check workProducts are not in use
        for product_type in self.list_products():
            product = self.get_product(product_type)
            if product.get_product_users():
                raise PulseError("work can't be trashed if its product is used : " + product_type)

        # unregister from products
        for input_product in self.get_inputs():
            if os.path.exists(input_product.directory):
                input_product.remove_product_user(self.directory)

        # create the trash work directory
        trash_directory = self._get_trash_directory()
        if not os.path.exists(trash_directory):
            os.makedirs(trash_directory)

        # move work product directory
        if os.path.exists(products_directory):
            shutil.move(products_directory,  os.path.join(trash_directory, "PRODUCTS"))

        # move work files
        for rel_filepath in self._get_work_files():
            filepath = self.directory + rel_filepath
            fu.move_file(filepath, filepath.replace(self.directory, trash_directory + "/work"))

        if no_backup:
            shutil.rmtree(trash_directory)

        # remove empty work subdirectory
        for subdir in os.listdir(self.directory):
            subdir_path = os.path.join(self.directory, subdir)
            if not os.path.exists(os.path.join(subdir_path, pulse_filename)):
                shutil.rmtree(subdir_path)

        # recursively remove products directories if they are empty
        fu.remove_empty_parents_directory(
            os.path.dirname(products_directory),
            [self.project.cfg.get_product_user_root()]
        )

        # recursively remove work directory if it's empty
        fu.remove_empty_parents_directory(
            self.directory,
            [self.project.cfg.get_work_user_root()]
        )

        return True

    def version_pipe_filepath(self, index):
        """
        get the pipe file path

        :param index:
        :return: filepath
        """
        return os.path.join(
            self.directory,
            self.project.cfg.version_prefix + str(index).zfill(self.project.cfg.version_padding) + ".pipe"
        )

    def status(self):
        """
        return the work files changes since last commit. Based on the files modification date time

        :return: a list a tuple with the filepath and the edit type (edited, removed, added)
        """
        product_directories = []
        for product_name in self.list_products():
            product_directories.append(os.path.join(self.get_products_directory(), product_name))

        diff = fu.compare_directory_content(
            self._get_work_files(),
            fu.read_data(self.data_file)["work_files"]
        )
        for product_name in self.list_products():
            product_directory = os.path.join(self.get_products_directory(), product_name)
            for root, subdirectories, files in os.walk(product_directory):
                for f in files:
                    filepath = os.path.join(root, f)
                    relative_path = filepath[len(product_directory):]
                    diff["product-" + product_name + relative_path] = "added"
        return diff

    def get_products_directory(self):
        """
        return the work products directory

        :return: filepath
        """
        return self.resource.get_products_directory(self.version)


class Resource(PulseDbObject):
    """
        a project's resource. A resource is meant to generate products, and use products from other resources
    """
    def __init__(self, project, entity, resource_type):
        self.lock_state = False
        self.lock_user = ''
        self.last_version = 0
        self.resource_type = resource_type
        self.entity = entity
        self.repository = None
        self.resource_template = ''
        PulseDbObject.__init__(
            self,
            project,
            uri_standards.convert_from_dict({"entity": entity, "resource_type": resource_type})
        )
        self.sandbox_path = os.path.join(
            project.cfg.get_work_user_root(), project.name, resource_type, entity.replace(":", "\\")
        )
        self._storage_vars = [
            'lock_state', 'lock_user', 'last_version', 'resource_type', 'entity', 'repository', 'metas']

    def get_products_directory(self, version_index):
        """
        return products filepath of the given resource version

        :param version_index: integer
        :return: string
        """
        version = str(version_index).zfill(self.project.cfg.version_padding)
        path = os.path.join(
            self.project.cfg.get_product_user_root(),
            self.project.name,
            self.resource_type,
            self.entity.replace(":", "\\"),
            self.project.cfg.version_prefix + version
        )
        return path

    def set_last_version(self, version):
        """
        set resource last version index

        :param version: integer
        """
        self.last_version = version
        self._db_update(["last_version"])

    def user_needs_lock(self, user=None):
        """
        return if the given user needs to get the resource lock to modify it
        if no user is specified, the current connexion user will be used

        :param user: string
        :return: boolean
        """
        if not user:
            user = self.project.cnx.user_name
        return self.lock_state and self.lock_user != user

    def get_index(self, version_name):
        """
        given an index or a tag, return the corresponding version number.
        accepted tag : "last"

        :param version_name: string or integer
        :return: integer
        """
        if isinstance(version_name, basestring):
            if version_name == "last":
                return self.last_version
            else:
                try:
                    return int(version_name)
                except ValueError:
                    raise PulseError("unsupported version name")
        return version_name

    def get_commit(self, version):
        """
        get the commit object from the given version number

        :param version: integer
        :return: Commit
        """
        return Commit(self, self.get_index(version)).db_read()

    def get_work(self):
        """
        get the Work object associated to the resource.
        IF there's no current work in user work space, raise a pulse error

        :return:
        """
        return Work(self).read()

    def checkout(self, index="last", destination_folder=None):
        """
        Download the resource work files in the user work space.
        Download related dependencies if they are not available in user products space
        """
        if not destination_folder:
            destination_folder = self.sandbox_path

        # abort if the work pipe file is already in user sandbox, just rebuild it
        if os.path.exists(os.path.join(destination_folder, "work.pipe")):
            return Work(self).read()

        # create the work object
        work = Work(self)
        work.version = self.last_version + 1

        # if it's an initial checkout, try to get data from source resource or template. Else, create empty folders
        if self.last_version == 0:
            source_resource = None
            # if a source resource is given, get its template
            if self.resource_template != '':
                template_dict = uri_standards.convert_to_dict(self.resource_template)
                source_resource = self.project.get_resource(template_dict['entity'], template_dict['resource_type'])
            else:
                # try to find a template
                try:
                    if self.entity != template_name:
                        source_resource = self.project.get_resource(template_name, self.resource_type)
                except PulseDatabaseMissingObject:
                    pass

            # if no template has been found, just create empty work folder
            if not source_resource:
                os.makedirs(destination_folder)
            else:
                source_commit = source_resource.get_commit("last")
                # initialize work and products data with source
                self.project.cnx.repositories[source_resource.repository].download_work(
                    source_commit,
                    destination_folder
                )
                products = source_commit.get_products()
                for product in products:
                    product_directory = os.path.join(work.get_products_directory(), product.product_type)
                    # os.makedirs(product_directory)
                    self.project.cnx.repositories[source_resource.repository].download_product(
                        product, product_directory)

        # else get the resource commit
        else:
            commit = self.get_commit(index)
            self.project.cnx.repositories[self.repository].download_work(commit, destination_folder)

        # download requested input products if needed
        for product in work.get_inputs():
            product.download()
            product.add_product_user(self.sandbox_path)

        work.write()
        return work

    def set_lock(self, state, user=None, steal=False):
        """
        change the lock state, and the lock user.
        raise a pulse error if the resource is already locked by someonelse, except the steal argement is True.

        :param state: boolean
        :param user: string
        :param steal: boolean
        """
        # abort if the resource is locked by someone else and the user doesn't want to steal the lock
        if not steal:
            self.db_read()
            if self.user_needs_lock(user):
                return

        self.lock_state = state
        if not user:
            self.lock_user = self.project.cnx.user_name
        else:
            self.lock_user = user
        self._db_update(['lock_user', 'lock_state'])

    def set_repository(self, new_repository):
        """
        move the resource to another repository.

        :param new_repository: Repository
        """
        if self.repository == new_repository:
            raise PulseError("the destination repository have to be different as current one :" + new_repository)

        if self.user_needs_lock():
            raise PulseError("you can't move a resource locked by another user :" + self.lock_user)

        # lock the resource to prevent concurrent commit
        lock_state = self.lock_state
        lock_user = self.lock_user
        self.set_lock(True, self.project.cnx.user_name + "_set_repo", steal=True)

        temp_directory = tempfile.mkdtemp()
        if new_repository not in self.project.cnx.repositories:
            raise PulseError("unknown repository : " + new_repository)
        self.project.cnx.repositories[self.repository].download_resource(self, temp_directory)
        self.project.cnx.repositories[new_repository].upload_resource(self, temp_directory)
        self.project.cnx.repositories[self.repository].remove_resource(self)
        self.repository = new_repository
        self.set_lock(lock_state, lock_user, steal=True)
        self._db_update(['repository'])


class Config(PulseDbObject):
    """
        project's configuration stored in database
    """
    def __init__(self, project):
        self.work_user_root = None
        self.product_user_root = None
        self.version_padding = None
        self.version_prefix = None
        self.default_repository = None
        self._storage_vars = vars(self).keys()
        PulseDbObject.__init__(self, project, "config")
        self._storage_vars = [
            "work_user_root",
            "product_user_root",
            "default_repository",
            "version_padding",
            "version_prefix"
        ]

    def get_work_user_root(self):
        return os.path.expandvars(self.work_user_root)

    def get_product_user_root(self):
        return os.path.expandvars(self.product_user_root)

    def get_user_products_list_filepath(self):
        """
        get the user products list filepath

        :return: string
        """
        return os.path.join(self.get_product_user_root(), "products_list.pipe")

    def save(self):
        """
        save the project configuration to database
        """
        self._db_update(self._storage_vars)


class Project:
    """
        a Pulse project, containing resources and a configuration
    """
    def __init__(self, connection, project_name):
        self.cnx = connection
        self.name = project_name
        self.cfg = Config(self)

    def get_product(self, uri_string):
        """
        return the product corresponding of the given uri
        raise a PulseError if the uri is not found in the project

        :param uri_string: a pulse product uri
        :return: Product
        """
        uri_dict = uri_standards.convert_to_dict(uri_string)
        resource = Resource(self, uri_dict['entity'], uri_dict['resource_type'])
        resource.db_read()
        if not uri_dict['version']:
            uri_dict['version'] = "last"
        index = resource.get_index(uri_dict['version'])
        try:
            product_parent = resource.get_commit(index)
        except PulseDatabaseMissingObject:
            product_parent = resource.get_work()
        if product_parent.version != index:
            raise PulseError("Unknown product : " + uri_string)
        return product_parent.get_product(uri_dict["product_type"])

    def list_products(self, uri_pattern):
        """
        return a product objects list matching the uri pattern.
        The pattern should be in the glob search type

        :param uri_pattern: string
        :return: a Products list
        """
        return [self.get_product(uri) for uri in self.cnx.db.find_uris(self.name, "CommitProduct", uri_pattern)]

    def purge_unused_user_products(self, unused_days=0, resource_filter=None):
        """
        remove unused products from the user product space, based on a unused time

        :param unused_days: for how many days this products have not been used by the user
        :param resource_filter: affect only products with the uri starting by the given string
        """
        if not os.path.exists(self.cfg.get_user_products_list_filepath()):
            return
        for uri in fu.read_data(self.cfg.get_user_products_list_filepath()):

            if resource_filter:
                if not uri.startswith(resource_filter.uri):
                    continue

            product = self.get_product(uri)
            if product.get_unused_time() > (unused_days*86400):
                product.remove_from_user_products(recursive_clean=True)

    def load_config(self):
        """
        load the project configuration from database
        """
        self.cfg.db_read()

    def get_resource(self, entity, resource_type):
        """
        return a project resource based on its entity name and its type
        will raise a PulseError on missing resource

        :param entity:
        :param resource_type:
        :return:
        """
        return Resource(self, entity, resource_type).db_read()

    def create_template(self, resource_type, repository=None, source_resource=None):
        return self.create_resource(template_name, resource_type, repository,  source_resource)

    def create_resource(self, entity, resource_type, repository=None, source_resource=None):
        """
        create a new project's resource

        :param entity: entity of this new resource. Entity is like a namespace
        :param resource_type:
        :param repository: a pulse Repository, if None, the project default repository is used
        :param source_resource: if given the resource content will be initialized with the given resource
        :return: the created resource object
        """

        resource = Resource(self, entity, resource_type)

        if not repository:
            repository = self.cfg.default_repository
        resource.repository = repository

        # if a source resource is given keep its uri to db
        if source_resource:
            try:
                source_resource.get_commit("last")
            except PulseDatabaseMissingObject:
                raise PulseError("no commit found for template : " + source_resource.uri)

            resource.resource_template = source_resource.uri

        resource.db_create()

        return resource


class Connection:
    """
        connection instance to a Pulse database
    """
    def __init__(self, adapter, **settings):
        self.db = import_adapter("database", adapter).Database(settings)
        self.user_name = self.db.get_user_name()
        self.repositories = self.get_repositories()

    def get_repositories(self):
        repositories = {}
        db_repositories = self.db.get_repositories()
        for name in db_repositories:
            db_repo = db_repositories[name]
            repositories[name] = import_adapter("repository", db_repo['adapter']).Repository(
                db_repo['login'],
                db_repo['password'],
                db_repo['settings'])
        return repositories

    def create_project(self,
                       project_name,
                       work_user_root,
                       default_repository,
                       product_user_root=None,
                       version_padding=DEFAULT_VERSION_PADDING,
                       version_prefix=DEFAULT_VERSION_PREFIX,
                       ):
        """
        create a new project in the connexion database
        work user root and product user root have to be different

        :param project_name:
        :param work_user_root: user work space path where the project directory will be created
        :param product_user_root: user product space path where the project directory will be created
        :param default_repository: repository name use by default when a resource is created
        :param version_padding: optional, set ehe number of digits used to number version. 3 by default
        :param version_prefix: optional, set the prefix used before version number. "V" by default
        :return: the new pulse Project
        """
        work_user_root = work_user_root.replace("\\", "/")
        if not product_user_root:
            product_user_root = work_user_root
        else:
            product_user_root = product_user_root.replace("\\", "/")

        project = Project(self, project_name)
        self.db.create_project(project_name)
        project.cfg.default_repository = default_repository
        project.cfg.work_user_root = work_user_root
        project.cfg.product_user_root = product_user_root
        project.cfg.version_padding = version_padding
        project.cfg.version_prefix = version_prefix
        project.cfg.db_create()
        project.load_config()
        return project

    def get_project(self, project_name):
        """
        return a pulse project from the database

        :param project_name: the pulse project's name
        :return: Project
        """
        project = Project(self, project_name)
        project.load_config()
        return project

    def delete_project(self, project_name):
        self.db.delete_project(project_name)

    def add_repository(self, name, adapter, login="", password="", **settings):
        """
        add a new repository to the project.

        :param name: the new repository name
        :param adapter: must be an existing module from repository adapters.
        :param settings: dict containing the connection parameters passed to the module
        :param login: the repository login
        :param password: the repository password
        """
        if name in self.repositories:
            raise PulseError("Repository already exists : " + name)
        # test valid settings
        repository = import_adapter("repository", adapter).Repository(settings=settings, login=login, password=password)
        repository.test_settings()
        # write repo settings to db config
        self.repositories[name] = repository
        self.db.create_repository(name, adapter, login, password, settings)

    def edit_repository(self, name, adapter, login="", password="", **settings):
        """
        edit the repository property
        raise a PulseError if the repository is not found
        """
        if name not in self.repositories:
            raise PulseError("Repository does not exists : " + name)
        self.db.update(
            "_Config",
            "Repository",
            name,
            {"adapter": adapter, "settings": settings, "login": login, "password": password}
        )


def import_adapter(adapter_type, adapter_name):
    """
    dynamically import a module adapter from plugins directory

    :param adapter_type: should be "database" or "repository"
    :param adapter_name:
    :return: the adapater module
    """
    pulse_filepath = os.path.dirname(os.path.realpath(__file__))
    return imp.load_source(adapter_type, os.path.join(pulse_filepath, adapter_type + "_adapters", adapter_name + ".py"))
