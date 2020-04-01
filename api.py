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
import tempfile
import copy

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
            # msg.new('INFO', 'No data found for ' + self.uri)
            return False


class Product(PulseObject):
    def __init__(self, commit, product_type, uri):
        PulseObject.__init__(self, uri)
        self.commit = commit
        self.product_type = product_type


class Commit(PulseObject):
    def __init__(self, resource, version):
        self.uri = resource.uri + "@" + str(version)
        PulseObject.__init__(self, self.uri)
        self.comment = ""
        self.files = []
        self.work_inputs = []
        self.entity = resource.entity
        self.resource_type = resource.resource_type
        self.version = version

    def get_products(self):
        pass




class Work():
    # TODO : add methods to work with work inputs list (add, remove)
    def __init__(self, resource):
        self.directory = pr.build_work_filepath(resource)
        self.resource = resource
        self.version = None
        self.entity = resource.entity
        self.resource_type = resource.resource_type
        self.data_file = self.directory + "\\work.pipe"

    def write(self):
        new_version_file = self.version_pipe_filepath(self.version)
        for file in os.listdir(self.directory):
            if file.endswith('.pipe'):
                os.remove(os.path.join(self.directory, file))

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

    def read(self):
        work_data_file = self.directory + "\\work.pipe"
        with open(work_data_file, "r") as read_file:
            work_data = json.load(read_file)
        self.version = work_data["version"]

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

        # create new version in resource repository
        self.resource.create_commit(self.directory, self.get_products_directory(), comment)

        # increment the work
        self.version += 1
        self.write()

        msg.new('INFO', "New version published : " + str(self.resource.last_version))


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

        msg.new('INFO', "work move to trash " + trash_directory)
        return True

    def version_pipe_filepath(self, index):
        return self.directory + "\\" + cfg.VERSION_PREFIX + str(index).zfill(cfg.VERSION_PADDING) + ".pipe"

    def get_files_changes(self):

        current_work_files = fu.get_directory_content(self.directory)
    
        last_commit = Commit(self.resource, self.resource.last_version)
        last_commit.read_data()
    
        print "last files", last_commit.files
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
        self.lock = False
        self.lock_user = ''
        self.last_version = -1
        self.resource_type = "unknown"
        self.entity = ""

    def get_work(self):
        work_folder = pr.build_work_filepath(self)
        if os.path.exists(work_folder):
            return Work(self, 0)
        else:
            return None


    def user_needs_lock(self, user=None):
        if not user:
            user = get_user_name()
        if self.lock and self.lock_user != user:
            msg.new('ERROR', "the resource is locked by another user")
            return True
        return False

    def create_commit(self, source_work, source_products, comment):
        index = self.last_version + 1

        # check work directory exist
        if not os.path.exists(source_work):
            msg.new("ERROR", "No source work found at " + source_work)
            return

        # copy work to a new version in repository
        commit = Commit(self, index)
        repo.upload_resource_commit(commit, source_work, source_products)

        # register changes to database
        commit.comment = comment
        # FIXME the files should include the products too
        commit.files = fu.get_directory_content(source_work)
        commit.work_inputs = get_inputs(source_work)
        commit.write_data()
        self.last_version = index
        self.write_data()
        return commit

    def initialize_data(self, template_resource_uri=None):
        # TODO : init from nothing create a new template, init from something can be a template or another resource
        # abort if the resource already exists
        if get_resource(self.uri):
            msg.new('ERROR', "there's already a resource named : " + self.uri)
            return

        # set resource attributes based on the parsed uri
        for k, v in uri_tools.string_to_dict(self.uri).items():
            setattr(self, k, v)

        # if the user wants to create a template, start from an empty directory
        if self.entity == TEMPLATE_NAME:
            msg.new('INFO', "new template created for type : " + self.resource_type)
            # create the initial commit from an empty directory
            tmp_folder = tempfile.mkdtemp()
            self.create_commit(tmp_folder, tmp_folder, "")
            os.rmdir(tmp_folder)

            commit = Commit(self, 0)
            commit.files = []
        else:
            if not template_resource_uri:
                uri_dict = {"entity": TEMPLATE_NAME, "resource_type": self.resource_type}
                template_resource_uri = uri_tools.dict_to_string(uri_dict)

            template_resource = get_resource(template_resource_uri)
            if not template_resource:
                msg.new('ERROR', "no resource found for " + template_resource_uri)
                return

            template_commit = template_resource.get_commit("last")
            # copy work to a new version in repository

            commit = Commit(self, 0)
            repo.copy_resource_commit(template_commit, commit)
            commit.files = template_commit.files

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


def get_inputs(folder):
    json_filepath = folder + "inputs.json"
    if not os.path.exists(json_filepath):
        return []

    with open(json_filepath, "r") as read_file:
        data = json.load(read_file)    
    return data


def get_user_name():
    return os.environ.get('USERNAME')


def create_resource(uri):
    """Create a new resource for the given entity and type
    """
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
