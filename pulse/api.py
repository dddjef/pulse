import pulse.uri_tools as uri_tools
import pulse.path_resolver as pr
import pulse.message as msg
import pulse.hooks as hooks
import json
import os
import file_utils as fu
import shutil
import time
from ConfigParser import ConfigParser
import imp
from pulse.database_adapters.interface_class import PulseDatabaseError
import tempfile

TEMPLATE_NAME = "_template"
# TODO : define all hooks
# TODO : add a purge trash function
# TODO : standardize the object.get_ return None or Error if there's nothing to get
# TODO : add a superclass for PulseNode, different from DBnode
# TODO : add "force" option to trash or remove product to avoid dependency check
# TODO : turn the pulse directory to read only on creation
# TODO : move uritools to main module
# TODO : clean the  + "\\" +


def check_is_on_disk(f):
    def deco(*args, **kw):
        if not os.path.exists(args[0].directory):
            raise PulseMissingNode("Missing work space : " + args[0].directory)
        return f(*args, **kw)
    return deco


class PulseError(Exception):
    def __init__(self, reason):
        Exception.__init__(self)
        self._reason = reason

    def reason(self):
        return self._reason

    def __str__(self):
        return self._reason


class PulseMissingNode(Exception):
    def __init__(self, reason):
        Exception.__init__(self)
        self._reason = reason

    def reason(self):
        return self._reason

    def __str__(self):
        return self._reason


class PulseObject:
    def __init__(self, project, uri):
        self.uri = uri
        self.project = project
        self.metas = {}
        self._storage_vars = []

    def write_data(self):
        # write the data to db
        data = dict((name, getattr(self, name)) for name in self._storage_vars)
        self.project.cnx.db.write(self.project.name, self.__class__.__name__, self.uri, data)

    def read_data(self):
        data = self.project.cnx.db.read(self.project.name, self.__class__.__name__, self.uri)
        for k in data:
            if k not in vars(self):
                msg.new('DEBUG', "missing attribute in object : " + k)
                continue
            setattr(self, k, data[k])
        return self


class Product:
    def __init__(self, parent, product_type):
        self.uri = uri_tools.dict_to_string({
            "entity": parent.resource.entity,
            "resource_type": parent.resource.resource_type,
            "product_type": product_type,
            "version": parent.version
        })
        self.parent = parent
        self.product_type = product_type
        self.directory = os.path.join(parent.get_products_directory(), product_type)
        self.product_users_file = self.directory + "\\" + "product_users.pipe"

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


class CommitProduct(PulseObject, Product):
    def __init__(self, parent, product_type):
        Product.__init__(self, parent, product_type)
        PulseObject.__init__(self, parent.project, self.uri)
        self.products_inputs = []
        self._storage_vars = ['product_type', 'products_inputs', 'uri']

    def download(self):
        self.project.repositories[self.parent.resource.repository].download_product(self)
        fu.write_data(self.product_users_file, [])
        self.register_to_user_products()
        for uri in self.products_inputs:
            product = self.project.get_pulse_node(uri)
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
        # unregister from its inputs
        for uri in self.products_inputs:
            product_input = self.project.get_pulse_node(uri)
            product_input.remove_product_user(self.directory)
            if recursive_clean:
                try:
                    product_input.remove_from_user_products(recursive_clean=True)
                except PulseError:
                    pass

        shutil.rmtree(self.directory)
        # remove also the version directory if it's empty now
        fu.remove_empty_parents_directory(os.path.dirname(self.directory), [self.project.cfg.product_user_root])
        msg.new('INFO', "product remove for user path " + self.uri)
        self.unregister_to_user_products()


class Commit(PulseObject):
    def __init__(self, resource, version):
        self.uri = resource.uri + "@" + str(version)
        PulseObject.__init__(self, resource.project, self.uri)
        self.resource = resource
        self.comment = ""
        self.files = []
        self.products_inputs = []
        self.version = int(version)
        self.products = []
        self._storage_vars = ['version', 'uri', 'products', 'files', 'comment']

    def get_product(self, product_type):
        return CommitProduct(self, product_type).read_data()

    def get_products_directory(self):
        return pr.build_products_filepath(self.resource, self.version)


class WorkNode:
    def __init__(self, project, directory):
        self.directory = directory
        self.products_inputs_file = os.path.join(directory, "product_inputs.pipe")
        self.project = project

    def get_inputs(self):
        inputs = []
        for uri in fu.json_list_get(self.products_inputs_file):
            inputs.append(self.project.get_pulse_node(uri))
        return inputs

    def add_input(self, product):
        if not os.path.exists(product.directory):
            # if the product is a WorkProduct try to convert it first
            product = self.project.get_pulse_node(product.uri)
            product.download()
        fu.json_list_append(self.products_inputs_file, product.uri)
        product.add_product_user(self.directory)

    def remove_input(self, local_product):
        fu.json_list_remove(self.products_inputs_file, local_product.uri)
        local_product.remove_product_user(self.directory)


class WorkProduct(Product, WorkNode):
    def __init__(self, work, product_type):
        Product.__init__(self, work, product_type)
        WorkNode.__init__(self, work.project, self.directory)


class Work(WorkNode):
    def __init__(self, resource):
        WorkNode.__init__(self, resource.project, resource.work_directory)
        self.resource = resource
        self.version = None
        self.data_file = self.directory + "\\work.pipe"

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
        trash_directory = pr.build_project_trash_filepath(self)
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

        # remove the old version file
        old_version_file = self.version_pipe_filepath(self.version-1)
        if os.path.exists(old_version_file):
            os.remove(old_version_file)

        # create a new products folder
        os.makedirs(self.get_products_directory())

        # write data to json
        with open(self.data_file, "w") as write_file:
            json.dump({"version": self.version}, write_file, indent=4, sort_keys=True)

    @check_is_on_disk
    def read(self):
        if not os.path.exists(self.directory):
            raise PulseError("work does not exists : " + self.directory)
        with open(self.data_file, "r") as read_file:
            work_data = json.load(read_file)
        self.version = work_data["version"]
        return self

    @check_is_on_disk
    def commit(self, comment=""):
        # check current the user permission
        if self.resource.user_needs_lock():
            return

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

        # launch the pre commit hook
        hooks.pre_commit(self)

        products_directory = self.get_products_directory()

        # copy work to a new version in repository
        commit = Commit(self.resource, self.version)
        commit.project.repositories[self.resource.repository].upload_resource_commit(
            commit, self.directory, products_directory)

        # register changes to database
        commit.comment = comment
        commit.files = fu.get_directory_content(
            self.directory,
            ignoreList=[os.path.basename(self.version_pipe_filepath(self.version)), os.path.basename(self.data_file)]
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
                product.write_data()

                product.register_to_user_products()

        commit.write_data()
        self.resource.last_version = self.version
        self.resource.write_data()

        # increment the work and the products files
        self.version += 1
        self.write()

        msg.new('INFO', "New version published : " + str(self.resource.last_version))
        return commit

    @check_is_on_disk
    def trash(self):
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
        trash_directory = pr.build_project_trash_filepath(self)
        os.makedirs(trash_directory)

        # move folders
        shutil.move(self.directory, trash_directory + "\\WORK")
        shutil.move(products_directory, trash_directory + "\\PRODUCTS")

        # recursively remove works directories if they are empty
        fu.remove_empty_parents_directory(os.path.dirname(self.directory), [self.project.cfg.work_user_root])

        # recursively remove products directories if they are empty
        fu.remove_empty_parents_directory(os.path.dirname(products_directory), [self.project.cfg.product_user_root])

        msg.new('INFO', "work move to trash " + trash_directory)
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
            ignoreList=[os.path.basename(self.version_pipe_filepath(self.version)), os.path.basename(self.data_file)]
        )

        last_commit = Commit(self.resource, self.resource.last_version)
        try:
            last_commit.read_data()
            last_files = last_commit.files
        except PulseDatabaseError:
            last_files = []

        diff = fu.compare_directory_content(current_work_files, last_files)

        # add products
        for path in os.listdir(self.get_products_directory()):
            diff.append((path, "added"))

        return diff

    def get_products_directory(self):
        return pr.build_products_filepath(self.resource, self.version)


class Resource(PulseObject):
    def __init__(self, project, entity, resource_type):
        self.lock = False
        self.lock_user = ''
        self.last_version = 0
        self.resource_type = resource_type
        self.entity = entity
        self.repository = None
        PulseObject.__init__(
            self,
            project,
            uri_tools.dict_to_string({"entity": entity, "resource_type": resource_type})
        )
        self.work_directory = pr.build_work_filepath(self)
        self._storage_vars = ['lock', 'lock_user', 'last_version', 'resource_type', 'entity', 'repository', 'metas']

    def user_needs_lock(self, user=None):
        if not user:
            user = self.project.cnx.user_name
        return self.lock and self.lock_user != user

    def get_index(self, version_name):
        if version_name == "last":
            return self.last_version
        return int(version_name)

    def get_commit(self, version):
        try:
            return Commit(self, self.get_index(version)).read_data()
        except PulseDatabaseError:
            return None

    def get_work(self):
        return Work(self).read()

    def checkout(self, index="last", destination_folder=None):
        """Download the resource work files in the user sandbox.
        Download related dependencies if they are not available in products path
        """
        if not destination_folder:
            destination_folder = self.work_directory

        # abort if the resource is already in user sandbox
        if os.path.exists(destination_folder):
            msg.new('INFO', "the resource was already in your sandbox")
            return Work(self).read()

        commit = self.get_commit(index)

        if not commit:
            if self.entity == TEMPLATE_NAME:
                os.makedirs(destination_folder)
            else:
                template_resource = self.project.get_resource(TEMPLATE_NAME, self.resource_type)
                if not template_resource:
                    raise PulseError("no template found for : " + self.resource_type)
                template_commit = template_resource.get_commit("last")
                if not template_commit:
                    raise PulseError("no commit found for template : " + template_resource.uri)

                self.project.repositories[template_resource.repository].download_work(
                    template_commit, destination_folder)
        else:
            self.project.repositories[self.repository].download_work(commit, destination_folder)

        # create the work object
        work = Work(self)
        work.version = self.last_version + 1
        work.write()

        # download requested input products if needed
        for product in work.get_inputs():
            product.download()
            product.add_product_user(self.work_directory)

        msg.new('INFO', "resource check out in : " + destination_folder)
        return work

    def set_lock(self, state, user=None, steal=False):
        # abort if the resource is locked by someone else and the user doesn't want to steal the lock
        if not steal:
            self.read_data()
            if self.user_needs_lock(user):
                return

        self.lock = state
        if not user:
            self.lock_user = self.project.get_user_name()
        else:
            self.lock_user = user
        self.write_data()
        msg.new('INFO', 'resource lock state is now ' + str(state))

    def set_repository(self, new_repository):
        temp_directory = tempfile.mkdtemp()
        if new_repository not in self.project.repositories:
            raise PulseError("unknown repository : " + new_repository)
        self.project.repositories[self.repository].download_resource(self, temp_directory)
        self.project.repositories[new_repository].upload_resource(self, temp_directory)
        self.project.repositories[self.repository].remove_resource(self)
        self.repository = new_repository


class Repository(PulseObject):
    def __init__(self, project, name, repo_type, parameters):
        self.name = name
        self.type = repo_type
        self.parameters = parameters
        PulseObject.__init__(self, project, name)


class Config(PulseObject):
    def __init__(self, project):
        self.work_user_root = None
        self.product_user_root = None
        self.version_padding = 3
        self.version_prefix = "V"
        self.repositories = {}
        self._storage_vars = vars(self).keys()
        PulseObject.__init__(self, project, "config")
        self._storage_vars = [k for k in vars(self).keys() if k != "project"]

    def get_user_products_list_filepath(self):
        return os.path.join(self.product_user_root, "products_list.pipe")

    def add_repository(self, repository_name, repository_type, repository_parameters):
        if repository_name in self.repositories:
            raise PulseError("Repository already exists : " + repository_name)
        self.repositories[repository_name] = {
            "type": repository_type,
            "parameters": repository_parameters
        }
        self.write_data()
        self.project.load_config()

    def remove_repository(self, repository_name):
        del self.repositories[repository_name]
        self.write_data()
        self.project.load_config()

    def edit_repository(self, repository_name, repository_type, repository_parameters):
        if repository_name not in self.repositories:
            raise PulseError("Repository does not exists : " + repository_name)
        self.repositories[repository_name] = {
            "type": repository_type,
            "parameters": repository_parameters
        }
        self.write_data()
        self.project.load_config()


class Project:
    def __init__(self, connection, project_name):
        self.cnx = connection
        self.name = project_name
        self.cfg = Config(self)
        self.repositories = {}

    def get_pulse_node(self, uri_string):
        uri_dict = uri_tools.string_to_dict(uri_string)
        resource = Resource(self, uri_dict['entity'], uri_dict['resource_type'])
        resource.read_data()
        if not uri_dict['version']:
            return resource
        index = resource.get_index(uri_dict['version'])
        if uri_dict['product_type'] == "":
            return resource.get_commit(index)
        else:
            product_parent = resource.get_commit(index)
            if not product_parent:
                product_parent = resource.get_work()
            if product_parent.version != index:
                raise PulseError("Unknown product : " + uri_string)

            return product_parent.get_product(uri_dict["product_type"])

    def list_nodes(self, entity_type, uri_pattern):
        return [self.get_pulse_node(uri) for uri in self.cnx.db.find_uris(self.name, entity_type, uri_pattern)]

    def purge_unused_user_products(self, unused_days=0):
        if not os.path.exists(self.cfg.get_user_products_list_filepath()):
            return
        for uri in fu.read_data(self.cfg.get_user_products_list_filepath()):
            product = self.get_pulse_node(uri)
            if product.get_unused_time() > (unused_days*86400):
                product.remove_from_user_products(recursive_clean=True)

    def save_config(
            self,
            work_user_root,
            product_user_root,
            version_padding,
            version_prefix,
            ):
        self.cfg.work_user_root = work_user_root
        self.cfg.product_user_root = product_user_root
        self.cfg.version_padding = version_padding
        self.cfg.version_prefix = version_prefix
        self.cfg.write_data()

    def load_config(self):
        self.cfg.read_data()
        for repo_name in self.cfg.repositories:
            repo = self.cfg.repositories[repo_name]
            self.repositories[repo_name] = import_adapter("repository", repo['type']).Repository(repo['parameters'])

    def get_resource(self, entity, resource_type):
        try:
            return Resource(self, entity, resource_type).read_data()
        except PulseDatabaseError:
            return None

    def duplicate_resource(
            self, entity, resource_type, source_resource=None, source_version="last", repository="default"):
        pass

    def _create_resource_item(self, entity, resource_type, repository):
        if self.get_resource(entity, resource_type):
            raise PulseError("Resource already exists " + entity + ", " + resource_type)

        resource = Resource(self, entity, resource_type)
        resource.repository = repository
        resource.write_data()
        return resource

    def create_resource(self, entity, resource_type, repository="default"):
        if entity == TEMPLATE_NAME:
            raise PulseError("entity name reserved for template : " + entity)
        return self._create_resource_item(entity, resource_type, repository)

    def create_template(self, resource_type, repository="default"):
        return self._create_resource_item(TEMPLATE_NAME, resource_type, repository)


class Connection:
    def __init__(self, connexion_data, database_type=None):
        pulse_filepath = os.path.dirname(os.path.realpath(__file__))
        if not database_type:
            config = ConfigParser()
            config.read(os.path.join(pulse_filepath, "config.ini"))
            database_type = config.get('database', 'default_adapter')
        self.db = import_adapter("database", database_type).Database(connexion_data)
        self.user_name = self.db.get_user_name()

    def create_project(self,
                       project_name,
                       work_user_root,
                       product_user_root,
                       version_padding=3,
                       version_prefix="V",
                       default_repository_type=None,
                       default_repository_parameters=None
                       ):
        project = Project(self, project_name)

        pulse_filepath = os.path.dirname(os.path.realpath(__file__))

        config = ConfigParser()
        config.read(os.path.join(pulse_filepath, "config.ini"))
        if not default_repository_type:
            default_repository_type = config.get('repository', 'default_adapter')
        if not default_repository_parameters:
            default_repository_parameters = config.get('repository', 'default_parameters')
        # TODO : get version padding and prefix from cfg

        self.db.create_project(project_name)
        project.save_config(work_user_root, product_user_root, version_padding, version_prefix)
        project.cfg.add_repository("default", default_repository_type, default_repository_parameters)
        project.load_config()
        return project

    def get_project(self, project_name):
        project = Project(self, project_name)
        project.load_config()
        return project


def import_adapter(adapter_type, adapter_name):
    pulse_filepath = os.path.dirname(os.path.realpath(__file__))
    return imp.load_source(adapter_type, os.path.join(pulse_filepath, adapter_type + "_adapters", adapter_name + ".py"))
