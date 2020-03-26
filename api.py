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
    def __init__(self, version, product_type, uri):
        PulseObject.__init__(self, uri)
        self.version = version
        self.product_type = product_type


class Version(PulseObject):
    def __init__(self, uri):
        PulseObject.__init__(self, uri)
        self.uri = uri
        self.comment = ""
        self.work_files = []
        self.work_inputs = []

    def get_resource(self):
        pass

    def get_products(self):
        pass


class Work:
    def __init__(self, folder, resource):
        self.folder = folder
        self.resource = resource
        self.version = 0
        self.products_folder = ""
        self.set_version(resource.last_version + 1)

    def set_version(self, index):
        self.version = index
        self.products_folder = pr.build_products_filepath(self.resource.entity, self.resource.resource_type, self.version)

        # if the version file already exists, abort file creation
        new_version_file = self.version_pipe_filepath(self.version)
        if os.path.exists(new_version_file):
            return

        # create the new version file
        with open(new_version_file, "w") as write_file:
            json.dump({"created_by": get_user_name()}, write_file, indent=4, sort_keys=True)

        # remove the old version file
        old_version_file = self.version_pipe_filepath(self.version-1)
        if os.path.exists(old_version_file):
            os.remove(old_version_file)

        # create a new products folder
        print "create dir " + self.products_folder
        os.makedirs(self.products_folder)

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
        self.resource.create_version(self.folder, self.products_folder, comment)

        # increment the work
        self.set_version(self.version + 1)

        msg.new('INFO', "New version published : " + str(self.resource.last_version))

    def trash(self):
        # test the work and products folder are movable
        for path in [self.folder, self.products_folder]:
            if not fu.test_path_write_access(path):
                msg.new('ERROR', "can't move folder " + path)
                return

        # create the trash work directory
        trash_directory = pr.build_project_trash_filepath(self)
        os.makedirs(trash_directory)

        # move folders
        shutil.move(self.folder, trash_directory + "\\WORK")
        shutil.move(self.products_folder, trash_directory + "\\PRODUCTS")

        msg.new('INFO', "work move to trash " + trash_directory)
        return True

    def version_pipe_filepath(self, index):
        return self.folder + "\\" + cfg.VERSION_PREFIX + str(index).zfill(cfg.VERSION_PADDING) + ".pipe"

    def get_files_changes(self):

        current_work_files = fu.get_directory_content(self.folder)
    
        last_version = Version(self.resource.uri + "@" + str(self.resource.last_version))
        last_version.read_data()
    
        diff = fu.compare_directory_content(current_work_files, last_version.work_files)

        # add products
        print "path : ", self.products_folder
        for path in os.listdir(self.products_folder):
            diff.append((path, "added"))

        return diff

        
class Resource(PulseObject):
    # TODO : add a last version name attribute
    # TODO : add methods to work with work inputs list
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
            return Work(work_folder, self)
        else:
            return None

    def user_needs_lock(self, user=None):
        if not user:
            user = get_user_name()
        if self.lock and self.lock_user != user:
            msg.new('ERROR', "the resource is locked by another user")
            return True
        return False

    def create_version(self, source_work, source_products, comment):
        index = self.last_version + 1

        # check work directory exist
        if not os.path.exists(source_work):
            msg.new("ERROR", "No source work found at " + source_work)
            return

        # copy work to a new version in repository
        version = Version(self.uri + "@" + str(index))
        repo.upload_resource_version(self, index, source_work, source_products)

        # register changes to database
        version.comment = comment
        version.work_files = fu.get_directory_content(source_work)
        version.write_data()
        version.work_inputs = get_inputs(source_work)
        self.last_version = index
        self.write_data()
        return version

    def initialize_data(self):
        # abort if the resource already exists
        if get_resource(self.uri):
            msg.new('ERROR', "there's already a resource named : " + self.uri)
            return

        # set resource attributes based on the parsed uri
        for k, v in uri_tools.string_to_dict(self.uri).items():
            setattr(self, k, v)

        # create an initial version based on templates
        template_path = pr.build_resource_template_path(self)
        self.create_version(template_path + "\\WORK", template_path + "\\PRODUCTS", "init from " + template_path)

        msg.new('INFO', "resource initialized : " + self.uri)

        return self

    def checkout(self, index="last"):
        """Download the resource work files in the user sandbox.
         TODO : read related dependencies in the version data
         TODO : Download related dependencies if they are not available in products path
         """
        if index == "last":
            index = self.last_version
        else:
            index = int(index)

        destination_folder = pr.build_work_filepath(self)

        # abort if the resource is already in user sandbox
        if os.path.exists(destination_folder):
            msg.new('INFO', "the resource was already in your sandbox")
            work = Work(destination_folder, self)
            return work

        # download the version
        repo.download_resource_version(self, index, destination_folder)

        # create the work object
        work = Work(destination_folder, self)

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
    resource = Resource(uri)
    if not resource.read_data():
        return None
    work = resource.get_work()
    if not work:
        return None
    return work