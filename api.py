import pulse.uri_tools as uri_tools
import pulse.repository_linker as repo
import pulse.path_resolver as pr
import pulse.database_linker as db
import pulse.message as msg
import pulse.hooks as hooks
import json
import os
import project_config as cfg
import file_utils as fu
import shutil
import time

TEMPLATE_NAME = "_template"


class PulseObject:
    def __init__(self, uri):
        self.uri = uri

    def write_data(self):
        # get the storage data
        # data = dict((name, getattr(self, name)) for name in dir(self) if not name.startswith('_'))
        db.write(entity_type=self.__class__.__name__, uri=self.uri, data_dict=vars(self))

    def read_data(self):
        data = db.read(entity_type=self.__class__.__name__, uri=self.uri)
        if data:
            for k in data:
                if k not in vars(self):
                    msg.new('DEBUG', "missing attribute in object : " + k)
                    continue
                setattr(self, k, data[k])
            return True
        else:
            return False


class Product:
    def __init__(self, commit, product_type):
        self.commit = commit
        self.product_type = product_type
        self.directory = pr.build_products_filepath(commit.entity, commit.resource_type, commit.version) + "\\" + product_type
        self._work_users_file = self.directory + "\\" + "work_users.pipe"
        self.uri = uri_tools.dict_to_string({
            "entity": commit.entity,
            "resource_type": commit.resource_type,
            "product_type": product_type,
            "version": commit.version
        })

    def add_work_user(self, work_directory):
        if os.path.exists(self._work_users_file):
            product_work_users = self.get_work_users()
        else:
            product_work_users = []

        if work_directory not in product_work_users:
            product_work_users.append(work_directory)
            fu.write_data(self._work_users_file, product_work_users)

    def remove_work_user(self, work_directory):
        product_work_users = self.get_work_users()
        if work_directory in product_work_users:
            product_work_users.remove(work_directory)
            fu.write_data(self._work_users_file, product_work_users)

    def init_work_users(self):
        fu.write_data(self._work_users_file, [])

    def get_work_users(self):
        if not os.path.exists(self._work_users_file):
            return []
        return fu.read_data(self._work_users_file)

    def get_unused_time(self):
        users = self.get_work_users()
        if users:
            return -1
        if os.path.exists(self._work_users_file):
            return time.time() - os.path.getmtime(self._work_users_file)
        else:
            return time.time() - os.path.getctime(self.directory)


class Commit(PulseObject):
    def __init__(self, resource, version):
        self.uri = resource.uri + "@" + str(version)
        PulseObject.__init__(self, self.uri)
        self.comment = ""
        self.files = []
        self.products_inputs = []
        self.entity = resource.entity
        self.resource_type = resource.resource_type
        self.version = version

    def get_product(self, product_type):
        product = Product(self, product_type)
        if not os.path.exists(product.directory):
            raise Exception("Unknown product :" + product.uri)
        return product


class Work:
    # TODO : add methods to work with work inputs list (add, remove)
    def __init__(self, resource):
        self.directory = pr.build_work_filepath(resource)
        self.resource = resource
        self.version = None
        self.entity = resource.entity
        self.resource_type = resource.resource_type
        self.data_file = self.directory + "\\work.pipe"
        self.products_inputs_file = self.directory + "\\products_inputs.pipe"
        self.products_inputs = []

    def add_product_input(self, resource, version, product_type):
        product = Commit(resource, version).get_product(product_type)

        # add it to the work data
        if product.uri in self.products_inputs:
            msg.new("DEBUG", "product already exists in user products")
        else:
            self.products_inputs.append(product.uri)
            fu.write_data(self.products_inputs_file, self.products_inputs)

        # download product if needed
        if not os.path.exists(product.directory):
            repo.download_product(product)
            product.init_work_users()
            msg.new("INFO", "product added to user products")
        # else register work to product
        else:
            product.add_work_user(self.directory)

    def remove_product_inputs(self, resource, version, product_type):
        product = Commit(resource, version).get_product(product_type)

        # remove it from the work data
        if product.uri in self.products_inputs:
            self.products_inputs.remove(product.uri)
            fu.write_data(self.products_inputs_file, self.products_inputs)
        # remove work from product users
            product.remove_work_user(self.directory)

    def write(self):
        new_version_file = self.version_pipe_filepath(self.version)
        for work_file in os.listdir(self.directory):
            if work_file.endswith('.pipe'):
                os.remove(os.path.join(self.directory, work_file))

        # create the new version file
        with open(new_version_file, "w") as write_file:
            json.dump({"created_by": get_user_name()}, write_file, indent=4, sort_keys=True)

        # remove the old version file
        old_version_file = self.version_pipe_filepath(self.version-1)
        if os.path.exists(old_version_file):
            os.remove(old_version_file)

        # create a new products folder
        os.makedirs(self.get_products_directory())

        # write data to json
        with open(self.data_file, "w") as write_file:
            json.dump({"version": self.version}, write_file, indent=4, sort_keys=True)

        with open(self.products_inputs_file, "w") as write_file:
            json.dump(self.products_inputs, write_file, indent=4, sort_keys=True)

    def read(self):
        with open(self.data_file, "r") as read_file:
            work_data = json.load(read_file)
        self.version = work_data["version"]

        with open(self.products_inputs_file, "r") as read_file:
            self.products_inputs = json.load(read_file)

    def commit(self, comment=""):
        # check current the user permission
        if self.resource.user_needs_lock():
            return

        # check the work is up to date
        if not self.version == self.resource.last_version + 1:
            last_version_name = cfg.VERSION_PREFIX + str(self.resource.last_version).zfill(cfg.VERSION_PADDING)
            msg.new('ERROR', "Your version is deprecated, it should be " + last_version_name)
            return

        # check the work status
        if not self.get_files_changes():
            msg.new('ERROR', "no file change to commit")
            return

        # launch the pre commit hook
        hooks.pre_commit(self)

        products_directory = self.get_products_directory()

        # copy work to a new version in repository
        commit = Commit(self.resource, self.version)
        repo.upload_resource_commit(commit, self.directory, products_directory)

        # register changes to database
        commit.comment = comment
        commit.files = fu.get_directory_content(self.directory)
        commit.products_inputs = self.products_inputs
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
                msg.new('ERROR', "can't move folder " + path)
                return

        # create the trash work directory
        trash_directory = pr.build_project_trash_filepath(self)
        os.makedirs(trash_directory)

        # move folders
        shutil.move(self.directory, trash_directory + "\\WORK")
        shutil.move(products_directory, trash_directory + "\\PRODUCTS")

        # unregister from products
        for product_uri in self.products_inputs:
            product_dict = uri_tools.string_to_dict(product_uri)
            product = Commit(Resource(product_uri), product_dict['version']).get_product(product_dict["product_type"])
            if not os.path.exists(product.directory):
                continue
            product.remove_work_user(self.directory)

        msg.new('INFO', "work move to trash " + trash_directory)
        return True

    def version_pipe_filepath(self, index):
        return self.directory + "\\" + cfg.VERSION_PREFIX + str(index).zfill(cfg.VERSION_PADDING) + ".pipe"

    def get_files_changes(self):

        current_work_files = fu.get_directory_content(self.directory)
    
        last_commit = Commit(self.resource, self.resource.last_version)
        last_commit.read_data()

        diff = fu.compare_directory_content(current_work_files, last_commit.files)

        # add products
        for path in os.listdir(self.get_products_directory()):
            diff.append((path, "added"))

        return diff

    def get_products_directory(self):
        return pr.build_products_filepath(self.entity, self.resource_type, self.version)


class Resource(PulseObject):
    # TODO : add a last version name attribute
    # TODO : support for products inputs
    def __init__(self, uri):
        PulseObject.__init__(self, uri)
        uri_dict = uri_tools.string_to_dict(self.uri)
        self.lock = False
        self.lock_user = ''
        self.last_version = -1
        self.resource_type = uri_dict["resource_type"]
        self.entity = uri_dict["entity"]

    def get_work(self):
        work_folder = pr.build_work_filepath(self)
        if os.path.exists(work_folder):
            return Work(self)
        else:
            return None

    def user_needs_lock(self, user=None):
        if not user:
            user = get_user_name()
        if self.lock and self.lock_user != user:
            msg.new('ERROR', "the resource is locked by another user")
            return True
        return False

    def initialize_data(self, template_resource_uri=None):
        # TODO : init from nothing create a new template, init from something can be a template or another resource

        # if the user wants to create a template, start from an empty directory
        if self.entity == TEMPLATE_NAME:
            msg.new('INFO', "new template created for type : " + self.resource_type)
            # create the initial commit from an empty directory
            commit = Commit(self, 0)
            repo.create_resource_empty_commit(commit)
            commit.products_inputs = []
            commit.files = []

        else:
            if not template_resource_uri:
                uri_dict = {"entity": TEMPLATE_NAME, "resource_type": self.resource_type}
                template_resource_uri = uri_tools.dict_to_string(uri_dict)

            template_resource = get_resource(template_resource_uri)
            if not template_resource:
                raise Exception("no resource found for " + template_resource_uri)

            template_commit = template_resource.get_commit("last")
            # copy work to a new version in repository

            commit = Commit(self, 0)
            repo.copy_resource_commit(template_commit, commit)
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
         TODO : read related dependencies in the commit data
         TODO : Download related dependencies if they are not available in products path
         TODO : check the function works also to check out an old commit
         """
        commit = self.get_commit(index)
        if not commit:
            msg.new('ERROR', "resource has no commit named " + str(index))
            return

        destination_folder = pr.build_work_filepath(self)
        print ("destination_folder", destination_folder)

        # abort if the resource is already in user sandbox
        if os.path.exists(destination_folder):
            msg.new('INFO', "the resource was already in your sandbox")
            work = Work(self)
            work.read()
            return work

        # download the commit
        repo.download_resource_commit(commit, destination_folder)

        # create the work object
        work = Work(self)
        work.version = self.last_version + 1
        work.products_inputs = commit.products_inputs
        work.write()

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
            self.lock_user = get_user_name()
        else:
            self.lock_user = user
        self.write_data()
        msg.new('INFO', 'resource lock state is now ' + str(state))


def get_user_name():
    return os.environ.get('USERNAME')


def create_resource(uri):
    """Create a new resource for the given entity and type
    """
    # TODO : add a regex testing the URI
    if get_resource(uri):
        raise Exception ("resource already exists : " + uri)
    resource = Resource(uri)
    return resource.initialize_data()


def get_resource(uri):
    resource = Resource(uri)
    if resource.read_data():
        return resource
    else:
        return None


def get_work(uri):
    resource = get_resource(uri)
    if not resource:
        return None
    work = resource.get_work()
    if not work:
        return None
    return work
