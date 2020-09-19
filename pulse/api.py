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
import tempfile
from datetime import datetime
import re

DEFAULT_VERSION_PADDING = 3
DEFAULT_VERSION_PREFIX = "V"

# TODO : add a purge trash function
# TODO : add "force" option to trash or remove product to avoid dependency check
# TODO : support linux user path
# TODO : unify the repo parameters as a single string to path, login and password optionals
# TODO : work.commit should have an option to remove the commit products
# TODO : don't support adding wip product to work (remove unneeded check in the trash function)


def check_is_on_disk(f):
    def deco(*args, **kw):
        if not os.path.exists(args[0].directory):
            raise PulseMissingNode("Missing work space : " + args[0].directory)
        return f(*args, **kw)
    return deco


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
            :return: the PulseDbObject
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

            use all the attributes lists is ._storage.vars and save them to the DB
            the key is the uri
            raise DbError if the object already exists
        """
        data = dict((name, getattr(self, name)) for name in self._storage_vars)
        self.project.cnx.db.create(self.project.name, self.__class__.__name__, self.uri, data)


class Product:
    """
        abstract class for all products (local or comited)
    """
    def __init__(self, parent, product_type):
        self.uri = dict_to_uri({
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
        fu.json_list_append(self.product_users_file, user_directory)

    def remove_product_user(self, user_directory):
        fu.json_list_remove(self.product_users_file, user_directory)

    def get_product_users(self):
        return fu.json_list_get(self.product_users_file)

    def get_unused_time(self):
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
        class for products which has been registered to database
    """
    def __init__(self, parent, product_type):
        Product.__init__(self, parent, product_type)
        PulseDbObject.__init__(self, parent.project, self.uri)
        self.products_inputs = []
        self._storage_vars = ['product_type', 'products_inputs', 'uri']

    def download(self):
        self.project.repositories[self.parent.resource.repository].download_product(self)
        fu.write_data(self.product_users_file, [])
        self.register_to_user_products()
        for uri in self.products_inputs:
            product = self.project.get_product(uri)
            product.download()
            product.add_product_user(self.directory)
        return self.directory

    def register_to_user_products(self):
        fu.json_list_append(self.project.cfg.get_user_products_list_filepath(), self.uri)

    def unregister_to_user_products(self):
        fu.json_list_remove(self.project.cfg.get_user_products_list_filepath(), self.uri)

    def remove_from_user_products(self, recursive_clean=False):
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
        fu.remove_empty_parents_directory(os.path.dirname(self.directory), [self.project.cfg.product_user_root])
        self.unregister_to_user_products()


class Commit(PulseDbObject):
    """
        class for a resource version
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
        """ list of product names"""
        self._storage_vars = ['version', 'products', 'files', 'comment']

    def get_product(self, product_type):
        return CommitProduct(self, product_type).db_read()

    def get_products_directory(self):
        return self.resource.get_products_directory(self.version)


class WorkNode:
    """
        abstract class for unpublished data (work or product)
    """
    def __init__(self, project, directory):
        self.directory = directory
        self.products_inputs_file = os.path.join(directory, "product_inputs.pipe")
        self.project = project

    def get_inputs(self):
        return [self.project.get_product(uri) for uri in fu.json_list_get(self.products_inputs_file)]

    # TODO : add input should support a product list
    def add_input(self, product):
        if not os.path.exists(product.directory):
            # if the product is a WorkProduct try to convert it first
            product = self.project.get_product(product.uri)
            product.download()
        fu.json_list_append(self.products_inputs_file, product.uri)
        product.add_product_user(self.directory)

    def remove_input(self, local_product):
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
        class for resource work in progress
    """
    def __init__(self, resource):
        WorkNode.__init__(self, resource.project, resource.sandbox_path)
        self.resource = resource
        self.version = None
        self.data_file = os.path.join(self.directory, "work.pipe")

    def _get_trash_directory(self):
        """custom function to build a sandbox trash path.
        """
        date_time = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        path = self.project.cfg.work_user_root + "\\" + self.project.name + "\\" + "TRASH" + "\\"
        path += self.resource.resource_type + "-" + self.resource.entity.replace(":", "_") + "-" + date_time
        return path

    def _get_work_files(self):
        work_files = []
        version_directory_regex = re.compile(DEFAULT_VERSION_PREFIX + "\\d{" + str(DEFAULT_VERSION_PADDING) + "}$")
        for f in os.listdir(self.directory):
            if not version_directory_regex.match(f):
                work_files.append(os.path.join(self.directory, f))
        return work_files

    @check_is_on_disk
    def get_product(self, product_type):
        return WorkProduct(self, product_type)

    @check_is_on_disk
    def list_products(self):
        return os.listdir(self.get_products_directory())

    @check_is_on_disk
    def create_product(self, product_type):
        if product_type in self.list_products():
            raise PulseError("product already exists : " + product_type)
        work_product = WorkProduct(self, product_type)
        os.makedirs(work_product.directory)
        return work_product

    @check_is_on_disk
    def trash_product(self, product_type):
        if product_type not in self.list_products():
            raise PulseError("product does not exists : " + product_type)
        product = WorkProduct(self, product_type)

        if not fu.test_path_write_access(product.directory):
            raise PulseError("can't move folder " + product.directory)

        if product.get_product_users():
            raise PulseError("work can't be trashed if its product is used : " + product_type)

        # unregister from products
        for input_product in product.get_inputs():
            if os.path.exists(input_product.directory):
                input_product.remove_product_user(self.directory)

        # create the trash work directory
        trash_directory = self._get_trash_directory()
        os.makedirs(trash_directory)

        # move folder
        shutil.move(product.directory, os.path.join(trash_directory, "PRODUCTS", product_type))

    @check_is_on_disk
    def write(self):
        # remove old version file
        old_version_file = self.version_pipe_filepath(self.resource.last_version)
        if os.path.exists(old_version_file):
            os.remove(os.path.join(self.directory, old_version_file))

        # create the new version file
        new_version_file = self.version_pipe_filepath(self.version)
        with open(new_version_file, "w") as write_file:
            json.dump({"created_by": self.resource.project.cnx.user_name}, write_file, indent=4, sort_keys=True)

        # create a new products folder
        os.makedirs(self.get_products_directory())

        # write data to json
        fu.write_data(self.data_file, {"version": self.version})

    @check_is_on_disk
    def read(self):
        if not os.path.exists(self.directory):
            raise PulseError("work does not exists : " + self.directory)
        work_data = fu.read_data(self.data_file)
        self.version = work_data["version"]
        return self

    @check_is_on_disk
    def commit(self, comment="", trash_unused_products=False):
        # check current the user permission
        if self.resource.user_needs_lock():
            raise PulseError("resource is locked by another user : " + self.resource.lock_user)

        # check the work is up to date
        expected_version = self.resource.last_version + 1
        if not self.version == expected_version:
            raise PulseError("Your version is deprecated, it should be " + str(expected_version))

        # check the work status
        if not self.get_files_changes():
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
        commit.project.repositories[self.resource.repository].upload_resource_commit(
            commit, self.directory, self._get_work_files(), products_directory)

        # register changes to database
        commit.comment = comment
        commit.files = fu.get_directory_content(
            self.directory,
            ignore_list=[os.path.basename(self.version_pipe_filepath(self.version)), os.path.basename(self.data_file)]
        )
        commit.products_inputs = self.get_inputs()
        commit.products = self.list_products()
        # if there's no product, delete the products version directory
        if not commit.products:
            os.rmdir(products_directory)
        else:
            # register work products to user products list
            for product_type in commit.products:
                work_product = self.get_product(product_type)

                product = CommitProduct(commit, product_type)
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

    @check_is_on_disk
    def trash(self, no_backup=False):
        # test the work and products folder are movable
        products_directory = self.get_products_directory()
        for path in [self.directory, products_directory]:
            if not fu.test_path_write_access(path):
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

        # move folders
        shutil.move(products_directory,  os.path.join(trash_directory, "PRODUCTS"))
        trashed_work = os.path.join(trash_directory, "WORK")
        os.makedirs(trashed_work)
        for f in self._get_work_files():
            destination = f.replace(self.directory, trashed_work)
            shutil.move(f, destination)

        if no_backup:
            shutil.rmtree(trash_directory)

        # recursively remove works directories if they are empty
        fu.remove_empty_parents_directory(self.directory, [self.project.cfg.work_user_root])

        # recursively remove products directories if they are empty
        fu.remove_empty_parents_directory(os.path.dirname(products_directory), [self.project.cfg.product_user_root])

        return True

    @check_is_on_disk
    def version_pipe_filepath(self, index):
        return os.path.join(
            self.directory,
            self.project.cfg.version_prefix + str(index).zfill(self.project.cfg.version_padding) + ".pipe"
        )

    @check_is_on_disk
    def get_files_changes(self):
        current_work_files = fu.get_directory_content(
            self.directory,
            ignore_list=[os.path.basename(self.version_pipe_filepath(self.version)), os.path.basename(self.data_file)]
        )

        last_commit = Commit(self.resource, self.resource.last_version)
        try:
            last_commit.db_read()
            last_files = last_commit.files
        except PulseDatabaseMissingObject:
            last_files = []

        diff = fu.compare_directory_content(current_work_files, last_files)

        # add products
        for path in os.listdir(self.get_products_directory()):
            diff.append((path, "added"))

        return diff

    def get_products_directory(self):
        return self.resource.get_products_directory(self.version)


class Resource(PulseDbObject):
    """
        class for project's resource
    """
    def __init__(self, project, entity, resource_type):
        self.lock_state = False
        self.lock_user = ''
        self.last_version = 0
        self.resource_type = resource_type
        self.entity = entity
        self.repository = None
        PulseDbObject.__init__(
            self,
            project,
            dict_to_uri({"entity": entity, "resource_type": resource_type})
        )
        self.sandbox_path = os.path.join(
            project.cfg.work_user_root, project.name, resource_type, entity.replace(":", "\\")
        )
        self._storage_vars = [
            'lock_state', 'lock_user', 'last_version', 'resource_type', 'entity', 'repository', 'metas']

    def get_products_directory(self, version_index):
        version = str(version_index).zfill(self.project.cfg.version_padding)
        path = os.path.join(
            self.project.cfg.product_user_root,
            self.project.name,
            self.resource_type,
            self.entity.replace(":", "\\"),
            self.project.cfg.version_prefix + version
        )
        return path

    def set_last_version(self, version):
        self.last_version = version
        self._db_update(["last_version"])

    def user_needs_lock(self, user=None):
        if not user:
            user = self.project.cnx.user_name
        return self.lock_state and self.lock_user != user

    def get_index(self, version_name):
        if version_name == "last":
            return self.last_version
        return int(version_name)

    def get_commit(self, version):
        return Commit(self, self.get_index(version)).db_read()

    def get_work(self):
        return Work(self).read()

    def checkout(self, index="last", destination_folder=None, template_resource=None):
        """
        Download the resource work files in the user sandbox.
        Download related dependencies if they are not available in products path
        """
        if not destination_folder:
            destination_folder = self.sandbox_path

        # abort if the resource is already in user sandbox
        if os.path.exists(destination_folder):
            return Work(self).read()

        if not template_resource:
            # if there's no template, and there's not version yet, just create a sandbox empty folder
            if self.last_version == 0:
                os.makedirs(destination_folder)

            # else get the resource version
            else:
                commit = self.get_commit(index)
                self.project.repositories[self.repository].download_work(commit, destination_folder)

        # if there's a template resource, get the commit from it
        else:
            commit = template_resource.get_commit(index)
            self.project.repositories[self.repository].download_work(commit, destination_folder)

        # create the work object
        work = Work(self)
        work.version = self.last_version + 1
        work.write()

        # download requested input products if needed
        for product in work.get_inputs():
            product.download()
            product.add_product_user(self.sandbox_path)

        return work

    def set_lock(self, state, user=None, steal=False):
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
        if self.repository == new_repository:
            raise PulseError("the destination repository have to be different as current one :" + new_repository)

        if self.user_needs_lock():
            raise PulseError("you can't move a resource locked by another user :" + self.lock_user)

        # lock the resource to prevent concurrent commit
        lock_state = self.lock_state
        lock_user = self.lock_user
        self.set_lock(True, self.project.cnx.user_name + "_set_repo", steal=True)

        temp_directory = tempfile.mkdtemp()
        if new_repository not in self.project.repositories:
            raise PulseError("unknown repository : " + new_repository)
        self.project.repositories[self.repository].download_resource(self, temp_directory)
        self.project.repositories[new_repository].upload_resource(self, temp_directory)
        self.project.repositories[self.repository].remove_resource(self)
        self.repository = new_repository
        self.set_lock(lock_state, lock_user, steal=True)
        self._db_update(['repository'])


class Config(PulseDbObject):
    """
        class for project's configuration
    """
    def __init__(self, project):
        self.work_user_root = None
        self.product_user_root = None
        self.version_padding = None
        self.version_prefix = None
        self.repositories = {}
        self._storage_vars = vars(self).keys()
        PulseDbObject.__init__(self, project, "config")
        self._storage_vars = [
            "work_user_root",
            "product_user_root",
            "repositories",
            "version_padding",
            "version_prefix"
        ]

    def get_user_products_list_filepath(self):
        return os.path.join(self.product_user_root, "products_list.pipe")

    def add_repository(self, name, adapter, url):
        if name in self.repositories:
            raise PulseError("Repository already exists : " + name)
        self.repositories[name] = {
            "adapter": adapter,
            "url": url
        }
        self._db_update(["repositories"])
        self.project.load_config()

    def remove_repository(self, repository_name):
        del self.repositories[repository_name]
        self._db_update(["repositories"])
        self.project.load_config()

    # TODO : Should write a test for edit and remove
    def edit_repository(self, repository_name, repository_type, repository_parameters):
        if repository_name not in self.repositories:
            raise PulseError("Repository does not exists : " + repository_name)
        self.repositories[repository_name] = {
            "type": repository_type,
            "parameters": repository_parameters
        }
        self._db_update(["repositories"])
        self.project.load_config()

    def save(self):
        self._db_update(self._storage_vars)


class Project:
    """
        class for a Pulse project
    """
    def __init__(self, connection, project_name):
        self.cnx = connection
        self.name = project_name
        self.cfg = Config(self)
        self.repositories = {}

    # TODO : get product should return last product of no version specified
    # TODO : get product should return all resource products if no product specified
    def get_product(self, uri_string):
        uri_dict = uri_to_dict(uri_string)
        resource = Resource(self, uri_dict['entity'], uri_dict['resource_type'])
        resource.db_read()
        if not uri_dict['version']:
            return None
        index = resource.get_index(uri_dict['version'])
        try:
            product_parent = resource.get_commit(index)
        except PulseDatabaseMissingObject:
            product_parent = resource.get_work()
        if product_parent.version != index:
            raise PulseError("Unknown product : " + uri_string)
        return product_parent.get_product(uri_dict["product_type"])

    def list_products(self, uri_pattern):
        return [self.get_product(uri) for uri in self.cnx.db.find_uris(self.name, "CommitProduct", uri_pattern)]

    def purge_unused_user_products(self, unused_days=0, resource_filter=None):
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
        self.cfg.db_read()
        for repo_name in self.cfg.repositories:
            repo = self.cfg.repositories[repo_name]
            self.repositories[repo_name] = import_adapter("repository", repo['adapter']).Repository(repo['url'])

    def get_resource(self, entity, resource_type):
        return Resource(self, entity, resource_type).db_read()

    def create_resource(self, entity, resource_type, repository='default', template_resource=None):
        resource = Resource(self, entity, resource_type)
        resource.repository = repository
        resource.db_create()
        if template_resource:
            try:
                template_commit = template_resource.get_commit("last")
            except PulseDatabaseMissingObject:
                raise PulseError("no commit found for template : " + template_resource.uri)

            # checkout from last template commit
            work = resource.checkout(template_resource=template_resource)

            # download template products in work products
            for product_name in template_commit.products:
                product_directory = os.path.join(work.get_products_directory(), product_name)
                product = template_commit.get_product(product_name)
                self.repositories[template_resource.repository].download_product(product, product_directory)

            # commit a first version
            commit = work.commit()

            # clean the sandbox
            work.trash(no_backup=True)

            # trash the V01 product
            products_v1 = [commit.get_product(product_name) for product_name in commit.products]
            for product in products_v1:
                product.remove_from_user_products()

        return resource


class Connection:
    """
        class for a connection to a Pulse database
    """
    def __init__(self, url, database_adapter=None):
        if not database_adapter:
            database_adapter = "json_db"
        self.db = import_adapter("database", database_adapter).Database(url)
        self.user_name = self.db.get_user_name()

    def create_project(self,
                       project_name,
                       work_user_root,
                       repository_url,
                       product_user_root=None,
                       version_padding=DEFAULT_VERSION_PADDING,
                       version_prefix=DEFAULT_VERSION_PREFIX,
                       repository_adapter="shell_repo",
                       ):
        # TODO : test admin rights in db and repo before registering anything else
        project = Project(self, project_name)
        if not product_user_root:
            product_user_root = work_user_root
        self.db.create_project(project_name)
        project.cfg.work_user_root = work_user_root
        project.cfg.product_user_root = product_user_root
        project.cfg.version_padding = version_padding
        project.cfg.version_prefix = version_prefix
        project.cfg.db_create()
        project.cfg.add_repository("default", repository_adapter, repository_url)
        project.load_config()
        return project

    def get_project(self, project_name):
        project = Project(self, project_name)
        project.load_config()
        return project


def import_adapter(adapter_type, adapter_name):
    pulse_filepath = os.path.dirname(os.path.realpath(__file__))
    return imp.load_source(adapter_type, os.path.join(pulse_filepath, adapter_type + "_adapters", adapter_name + ".py"))


def uri_to_dict(uri_string):
    """
    transform a string uri in a dict uri
    :param uri_string:
    :return uri dict:
    """
    uri_split_main = uri_string.split("@")
    uri_split = uri_split_main[0].split("-")
    entity = uri_split[0]
    resource_type = uri_split[1]
    product_type = ""
    version = None

    if len(uri_split) > 2:
        product_type = uri_split[2]

    if len(uri_split_main) > 1:
        version = uri_split_main[1]

    return {"entity": entity, "resource_type": resource_type, "version": version, "product_type": product_type}


def dict_to_uri(uri_dict):
    uri = uri_dict["entity"] + "-" + uri_dict['resource_type']
    if 'product_type' in uri_dict:
        uri += "-" + uri_dict['product_type']
    if 'version' in uri_dict:
        uri += "@" + (str(int(uri_dict['version'])))
    return uri
