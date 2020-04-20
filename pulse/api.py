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

TEMPLATE_NAME = "_template"
PRODUCT_INPUTS_FILENAME = "product_inputs.pipe"
# TODO : define all hooks


class PulseError(Exception):
    def __init__(self, reason):
        Exception.__init__(self)
        self._reason = reason

    def reason(self):
        return self._reason

    def __str__(self):
        return self._reason


class PulseObject:
    def __init__(self, project, uri, metas=None):
        self.uri = uri
        self._project = project
        self.metas = metas
        self._storage_vars = []

    def get_project(self):
        return self._project

    def write_data(self):
        # write the data to db
        data = dict((name, getattr(self, name)) for name in self._storage_vars if not name.startswith("_"))
        self._project.cnx.db.write(self._project.name, self.__class__.__name__, self.uri, data)

    def read_data(self):
        data = self._project.cnx.db.read(self._project.name, self.__class__.__name__, self.uri)
        if data:
            for k in data:
                if k not in vars(self):
                    msg.new('DEBUG', "missing attribute in object : " + k)
                    continue
                setattr(self, k, data[k])
            return True
        else:
            return False


class Product(PulseObject):
    def __init__(self, commit, product_type):
        self.uri = uri_tools.dict_to_string({
            "entity": commit.entity,
            "resource_type": commit.resource_type,
            "product_type": product_type,
            "version": commit.version
        })
        PulseObject.__init__(self, commit.get_project(), self.uri)
        self.commit = commit
        self.product_type = product_type
        self.directory = commit.products_directory + "\\" + product_type
        self.products_inputs_file = os.path.join(self.directory, PRODUCT_INPUTS_FILENAME)
        self.products_inputs = []
        self.work_users_file = self.directory + "\\" + "work_users.pipe"
        self.project_products_list = self._project.cfg.get_user_products_list_filepath()
        self._storage_vars = ['product_type', 'products_inputs', 'uri']

    def get_commit(self):
        return self.commit

    # TODO : rename all functions work users" by something for product too
    def add_product_user(self, user_directory):
        if os.path.exists(self.work_users_file):
            product_work_users = self.get_product_users()
        else:
            product_work_users = []

        if user_directory not in product_work_users:
            product_work_users.append(user_directory)
            fu.write_data(self.work_users_file, product_work_users)

    def remove_product_user(self, user_directory):
        product_work_users = self.get_product_users()
        if user_directory in product_work_users:
            product_work_users.remove(user_directory)
            fu.write_data(self.work_users_file, product_work_users)

    def get_product_users(self):
        if not os.path.exists(self.work_users_file):
            return []
        return fu.read_data(self.work_users_file)

    def get_inputs(self):
        if not os.path.exists(self.products_inputs_file):
            return []
        with open(self.products_inputs_file, "r") as read_file:
            return json.load(read_file)

    def get_unused_time(self):
        users = self.get_product_users()
        if users:
            return -1
        if os.path.exists(self.work_users_file):
            return time.time() - os.path.getmtime(self.work_users_file) + 0.01
        else:
            return time.time() - os.path.getctime(self.directory)

    def remove_from_user_products(self, recursive_clean=False):
        if len(self.get_product_users()) > 0:
            raise PulseError("Can't remove a product still in use")

        # unregister from its inputs
        for uri in self.get_inputs():
            product_input = self._project.get_pulse_node(uri)
            product_input.remove_product_user(self.directory)
            if recursive_clean:
                try:
                    product_input.remove_from_user_products(recursive_clean=True)
                except PulseError:
                    pass

        shutil.rmtree(self.directory)
        # remove also the version directory if it's empty now
        fu.remove_empty_parents_directory(os.path.dirname(self.directory), [self._project.cfg.product_user_root])
        msg.new('INFO', "product remove for user path " + self.uri)
        self.unregister_to_user_products()

    def download(self):
        if os.path.exists(self.directory):
            return
        self.commit.get_project().repo.download_product(self)
        fu.write_data(self.work_users_file, [])
        self.register_to_user_products()
        for uri in self.products_inputs:
            product = self._project.get_pulse_node(uri)
            product.download()
            product.add_product_user(self.directory)

    def register_to_user_products(self):
        try:
            products_list = fu.read_data(self.project_products_list)
        except IOError:
            products_list = []
        products_list.append(self.uri)
        fu.write_data(self.project_products_list, products_list)

    def unregister_to_user_products(self):
        products_list = fu.read_data(self.project_products_list)
        products_list.remove(self.uri)
        fu.write_data(self.project_products_list, products_list)


class Commit(PulseObject):
    def __init__(self, resource, version, metas=None):
        self.uri = resource.uri + "@" + str(version)
        PulseObject.__init__(self, resource.get_project(), self.uri, metas)
        self._resource = resource
        self.comment = ""
        self.files = []
        self.products_inputs = []
        self.entity = resource.entity
        self.resource_type = resource.resource_type
        self.version = version
        self.products = []
        self.products_directory = pr.build_products_filepath(
            self._project,
            self.entity,
            self.resource_type,
            self.version
        )
        self._storage_vars = ['version', 'uri', 'products', 'files', 'comment']

    def get_product(self, product_type):
        self.read_data()
        if product_type not in self.products:
            raise Exception("Unknown product :" + product_type)
        product = Product(self, product_type)
        return product

    def get_resource(self):
        return self._resource


class Work:
    def __init__(self, resource):
        self.project = resource.get_project()
        self.resource = resource
        self.directory = pr.build_work_filepath(self.project, self.resource)
        self.products_inputs_file = os.path.join(self.directory, PRODUCT_INPUTS_FILENAME)
        self.version = None
        self.data_file = self.directory + "\\work.pipe"

    def get_product_directory(self, product_type):
        return os.path.join(self.get_products_directory(), product_type)

    @staticmethod
    def _get_inputs(products_inputs_file):
        if not os.path.exists(products_inputs_file):
            return []
        with open(products_inputs_file, "r") as read_file:
            return json.load(read_file)

    def initialize_product_directory(self, product_type):
        directory = self.get_product_directory(product_type)
        if not os.path.exists(directory):
            os.makedirs(directory)
        return directory

    def get_work_inputs(self):
        return self._get_inputs(self.products_inputs_file)

    def get_product_inputs(self, product_type):
        inputs_file = os.path.join(self.get_product_directory(product_type), PRODUCT_INPUTS_FILENAME)
        return self._get_inputs(inputs_file)

    def add_work_input(self, uri):
        product = self._add_input(self.products_inputs_file, uri)
        product.add_product_user(self.directory)

    def add_product_input(self, product_type, uri):
        inputs_file = os.path.join(self.get_product_directory(product_type), PRODUCT_INPUTS_FILENAME)
        product = self._add_input(inputs_file, uri)
        product.add_product_user(self.get_product_directory(product_type))

    def _add_input(self, products_inputs_file, uri):
        # add it to the work product inputs
        product_inputs = self._get_inputs(products_inputs_file)
        if uri in product_inputs:
            msg.new("DEBUG", "product already exists in user products")
        else:
            product_inputs.append(uri)
            fu.write_data(products_inputs_file, product_inputs)

        product = self.project.get_pulse_node(uri)

        # download product if needed
        if not os.path.exists(product.directory):
            if not product.read_data():
                raise PulseError("Can't register unknown product " + uri)
            product.download()
            msg.new("INFO", "product added to user products")
        return product

    def remove_work_input(self, uri):
        product = self._remove_product_inputs(uri, self.products_inputs_file)
        product.remove_product_user(self.directory)

    def remove_product_input(self,  product_type, uri):
        inputs_file = os.path.join(self.get_product_directory(product_type), PRODUCT_INPUTS_FILENAME)
        product = self._remove_product_inputs(uri, inputs_file)
        product.remove_product_user(self.get_product_directory(product_type))

    def _remove_product_inputs(self, uri, products_inputs_file):
        # remove it from the work data
        product_inputs = self._get_inputs(products_inputs_file)
        if uri in product_inputs:
            product_inputs.remove(uri)
            fu.write_data(products_inputs_file, product_inputs)
        # remove work from product users
        product = self.project.get_pulse_node(uri)
        return product

    def write(self):
        # remove old version file
        old_version_file = self.version_pipe_filepath(self.resource.last_version)
        if os.path.exists(old_version_file):
            os.remove(os.path.join(self.directory, old_version_file))

        # create the new version file
        new_version_file = self.version_pipe_filepath(self.version)
        with open(new_version_file, "w") as write_file:
            json.dump({"created_by": self.resource.get_project().cnx.user_name}, write_file, indent=4, sort_keys=True)

        # remove the old version file
        old_version_file = self.version_pipe_filepath(self.version-1)
        if os.path.exists(old_version_file):
            os.remove(old_version_file)

        # create a new products folder
        os.makedirs(self.get_products_directory())
        # TODO : add the input_products file
        # TODO : dissociate the create empty product folder to lighten the work consultation behaviour.

        # write data to json
        with open(self.data_file, "w") as write_file:
            json.dump({"version": self.version}, write_file, indent=4, sort_keys=True)

    def read(self):
        with open(self.data_file, "r") as read_file:
            work_data = json.load(read_file)
        self.version = work_data["version"]

    def commit(self, comment=""):
        # check current the user permission
        if self.resource.user_needs_lock():
            return

        # check the work is up to date
        if not self.version == self.resource.last_version + 1:
            last_version_name = self.project.cfg.VERSION_PREFIX
            last_version_name += str(self.resource.last_version).zfill(self.project.cfg.VERSION_PADDING)
            raise PulseError("Your version is deprecated, it should be " + last_version_name)

        # check the work status
        if not self.get_files_changes():
            raise PulseError("no file change to commit")

        # TODO : check all product inputs are registered

        # launch the pre commit hook
        hooks.pre_commit(self)

        products_directory = self.get_products_directory()

        # copy work to a new version in repository
        commit = Commit(self.resource, self.version)
        commit.get_project().repo.upload_resource_commit(commit, self.directory, products_directory)

        # register changes to database
        commit.comment = comment
        commit.files = fu.get_directory_content(
            self.directory,
            ignoreList=[os.path.basename(self.version_pipe_filepath(self.version)), os.path.basename(self.data_file)]
        )
        commit.products_inputs = self.get_work_inputs()
        commit.products = os.listdir(products_directory)
        # if there's no product, delete the products version directory
        if not commit.products:
            os.rmdir(products_directory)
        else:
            # register products to user products list
            for product_type in commit.products:
                product = Product(commit, product_type)
                product.register_to_user_products()
                product.products_inputs = self.get_product_inputs(product_type)
                product.write_data()

        commit.write_data()
        self.resource.last_version = self.version
        self.resource.write_data()

        # increment the work and the products files
        self.version += 1
        self.write()

        msg.new('INFO', "New version published : " + str(self.resource.last_version))
        return commit

    def trash(self):
        # test the work and products folder are movable
        products_directory = self.get_products_directory()
        for path in [self.directory, products_directory]:
            if not fu.test_path_write_access(path):
                raise PulseError("can't move folder " + path)

        # unregister from products
        for product_uri in self.get_work_inputs():
            product = self.resource.get_project().get_pulse_node(product_uri)
            print "unregister from ", product.uri
            if not os.path.exists(product.directory):
                continue
            product.remove_product_user(self.directory)

        # create the trash work directory
        trash_directory = pr.build_project_trash_filepath(self.project, self)
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

    def version_pipe_filepath(self, index):
        return os.path.join(
            self.directory,
            self.project.cfg.version_prefix + str(index).zfill(self.project.cfg.version_padding) + ".pipe"
        )

    def get_files_changes(self):

        current_work_files = fu.get_directory_content(
            self.directory,
            ignoreList=[os.path.basename(self.version_pipe_filepath(self.version)), os.path.basename(self.data_file)]
        )

        last_commit = Commit(self.resource, self.resource.last_version)
        last_commit.read_data()

        diff = fu.compare_directory_content(current_work_files, last_commit.files)

        # add products
        for path in os.listdir(self.get_products_directory()):
            diff.append((path, "added"))

        return diff

    def get_products_directory(self):
        return pr.build_products_filepath(self.project, self.resource.entity, self.resource.resource_type, self.version)


class Resource(PulseObject):
    def __init__(self, project, entity, resource_type, metas=None):
        self.lock = False
        self.lock_user = ''
        self.last_version = -1
        self.resource_type = resource_type
        self.entity = entity
        self.work_directory = pr.build_work_filepath(project, self)
        PulseObject.__init__(
            self,
            project,
            uri_tools.dict_to_string({"entity": entity, "resource_type": resource_type}),
            metas
        )
        self._storage_vars = ['lock', 'lock_user', 'last_version', 'resource_type', 'entity']

    def user_needs_lock(self, user=None):
        if not user:
            user = self._project.cnx.user_name
        return self.lock and self.lock_user != user

    def initialize_data(self, template_resource=None):
        # test the resource does not already exists
        if self.read_data():
            raise Exception("resource already exists : " + self.uri)

        if self.entity == TEMPLATE_NAME:
            msg.new('INFO', "new template created for type : " + self.resource_type)
            # create the initial commit from an empty directory
            commit = Commit(self, 0)
            self._project.repo.create_resource_empty_commit(commit)
            commit.products_inputs = []
            commit.files = []

        else:
            if not template_resource:
                template_resource = Resource(self._project, TEMPLATE_NAME, self.resource_type)

            if not template_resource.read_data():
                raise Exception("no resource found for " + template_resource.uri)

            template_commit = template_resource.get_commit("last")
            # copy work to a new version in repository

            commit = Commit(self, 0)
            self._project.repo.duplicate_commit(template_commit, commit)
            commit.files = template_commit.files
            commit.products_inputs = template_commit.products_inputs

        commit.write_data()
        self.last_version = 0
        self.write_data()

        msg.new('INFO', "resource initialized : " + self.uri)
        return self

    def get_commit(self, index):
        if index == "last":
            index = self.last_version
        commit = Commit(self, index)
        if not commit.read_data():
            return None
        return commit

    def checkout(self, index="last"):
        """Download the resource work files in the user sandbox.
        Download related dependencies if they are not available in products path
        """
        commit = self.get_commit(index)
        if not commit:
            raise PulseError("resource has no commit named " + commit.uri)

        destination_folder = self.work_directory

        # abort if the resource is already in user sandbox
        if os.path.exists(destination_folder):
            msg.new('INFO', "the resource was already in your sandbox")
            work = Work(self)
            work.read()
            return work

        # download the commit
        self._project.repo.download_work(commit, destination_folder)

        # create the work object
        work = Work(self)
        work.version = self.last_version + 1
        work.write()

        # download requested input products if needed
        for uri in work.get_work_inputs():
            product = self._project.get_pulse_node(uri)
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
            self.lock_user = self._project.get_user_name()
        else:
            self.lock_user = user
        self.write_data()
        msg.new('INFO', 'resource lock state is now ' + str(state))


class Config(PulseObject):
    def __init__(self, project, metas=None):
        self.work_user_root = None
        self.product_user_root = None
        self.version_padding = 3
        self.version_prefix = "V"
        self.repository_type = None
        self.repository_parameters = {}
        PulseObject.__init__(self, project, "config", metas)
        self._storage_vars = vars(self)

    def get_user_products_list_filepath(self):
        return os.path.join(self.product_user_root, "products_list.pipe")


class Project:
    def __init__(self, connection, project_name):
        self.cnx = connection
        self.name = project_name
        self.cfg = Config(self)
        self.repo = None

    def get_pulse_node(self, uri_string):
        uri_dict = uri_tools.string_to_dict(uri_string)
        resource = Resource(self, uri_dict['entity'], uri_dict['resource_type'])
        if uri_dict['version'] == -1:
            return resource
        commit = Commit(resource, uri_dict['version'])
        if uri_dict['product_type'] == "":
            return commit
        return commit.get_product(uri_dict["product_type"])

    def list_nodes(self, entity_type, uri_pattern):
        return [self.get_pulse_node(uri) for uri in self.cnx.db.find_uris(self.name, entity_type, uri_pattern)]

    def purge_unused_user_products(self, unused_days=0):
        # TODO : should ignore the error of an used product if the product is in the purged list
        purged_products = []
        for uri in fu.read_data(self.cfg.get_user_products_list_filepath()):
            product = self.get_pulse_node(uri)
            # convert unused days in seconds to compare with unused time
            print uri, product.get_unused_time()
            if product.get_unused_time() > (unused_days*86400):
                product.remove_from_user_products(recursive_clean=True)

    def save_config(
            self,
            work_user_root,
            product_user_root,
            version_padding,
            version_prefix,
            repository_type,
            repository_parameters
            ):
        self.cfg.work_user_root = work_user_root
        self.cfg.product_user_root = product_user_root
        self.cfg.version_padding = version_padding
        self.cfg.version_prefix = version_prefix
        self.cfg.repository_type = repository_type
        self.cfg.repository_parameters = repository_parameters
        self.cfg.write_data()

    def load_config(self):
        if not self.cfg.read_data():
            raise PulseError("No configuration found for project" + self.name)
        self.repo = import_adapter("repository", self.cfg.repository_type).Repository(self.cfg.repository_parameters)


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
                       repository_type=None,
                       repository_parameters=None
                       ):
        project = Project(self, project_name)

        pulse_filepath = os.path.dirname(os.path.realpath(__file__))
        if not repository_type:
            config = ConfigParser()
            config.read(os.path.join(pulse_filepath, "config.ini"))
            repository_type = config.get('repository', 'default_adapter')

        self.db.create_project(project_name)
        project.save_config(
                            work_user_root,
                            product_user_root,
                            version_padding,
                            version_prefix,
                            repository_type,
                            repository_parameters
                            )
        project.load_config()
        return project

    def get_project(self, project_name):
        project = Project(self, project_name)
        project.load_config()
        return project


def import_adapter(adapter_type, adapter_name):
    pulse_filepath = os.path.dirname(os.path.realpath(__file__))
    return imp.load_source(adapter_type, os.path.join(pulse_filepath, adapter_type + "_adapters", adapter_name + ".py"))
