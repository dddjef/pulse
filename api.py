import pulse.uri_tools as uri_tools
import pulse.repository_linker as fm
import pulse.path_resolver as pr
import pulse.database_linker as db
import pulse.message as msg
import pulse.hooks as hooks
import json
import os
import project_config as cfg
from datetime import datetime
import file_utils as fu

class PulseObject:
    def __init__(self, uri):
        self.uri = uri

    def write_data(self):
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

    def get_resource(self):
        pass

    def get_products(self):
        pass


class Resource(PulseObject):
    # TODO : convert last_version to string attr
    def __init__(self, uri):
        PulseObject.__init__(self, uri)
        self.lock = False
        self.lock_user = ''
        self.last_version = -1
        self.resource_type = "unknown"
        self.entity = ""

    def get_version(self, index):
        pass

    def user_needs_lock(self):
        if self.lock and self.lock_user != get_user_name():
            msg.new('ERROR', "the resource is locked by another user")
            return True
        return False

    def _create_version(self, source_work, source_products, comment):
        index = self.last_version + 1

        # check work directory exist
        if not os.path.exists(source_work):
            msg.new("ERROR", "No source work found at " + source_work)
            return

        # copy work to a new version in repository
        version = Version(self.uri + "@" + str(index))
        fm.upload_resource_version(self, index, source_work, source_products)

        # register changes to database
        version.comment = comment
        version.work_files = fu.get_directory_content(source_work)
        version.write_data()
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

        template_path = pr.build_resource_template_path(self)

        self._create_version(template_path + "\\WORK", template_path + "\\PRODUCTS", "init from " + template_path)

        msg.new('INFO', "resource initialized : " + self.uri)

        return self

    def commit(self, comment=""):
        # check current the user permission
        if self.user_needs_lock():
            return

        # build work and products path
        work_folder = pr.build_work_filepath(self)
        products_folder = pr.build_product_filepath(self, self.last_version + 1)

        # TODO : check the work is up to date

        if not os.path.exists(work_folder):
            msg.new('ERROR', "this resource is not in your sandbox")
            return

        # check the work status
        # TODO : check also there's no new products
        if not self.get_work_files_changes():
            msg.new('ERROR', "no file change to commit")
            return

        # launch the pre commit hook
        hooks.pre_commit(self)

        new_version = self._create_version(work_folder, products_folder, comment)

        # TODO : Make user products read only

        msg.new('INFO', "New version published : " + str(self.last_version))


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
            msg.new('ERROR', "can't check out a resource already in your sandbox")
            return

        # download the version
        fm.download_resource_version(self, index, destination_folder)

        # create the attended products folder
        os.makedirs(pr.build_product_filepath(self, self.last_version + 1))

        msg.new('INFO', "resource check out in : " + destination_folder)

    def trash_work(self):
        work_folder = pr.build_work_filepath(self)
        # abort if the resource is already in user sandbox
        if not os.path.exists(work_folder):
            msg.new('ERROR', "can't check out a resource already in your sandbox")
            return

        trash_directory = pr.build_trash_filepath(self)
        if not os.path.exists(trash_directory):
            os.makedirs(trash_directory)
        trash_work = trash_directory + "\\" + os.path.basename(work_folder) + "_" + get_date_time()

        try:
            os.rename(work_folder, trash_work)
        except:
            msg.new('ERROR', "work folder can't be removed. Close all application using : " + work_folder)
            return False
        msg.new('INFO', "work move to trash " + trash_work)

    def set_lock(self, state, user=None, steal=False):
        # abort if the resource is locked by someone else and the user doesn't want to steal the lock
        if not steal:
            self.read_data()
            if self.user_needs_lock():
                return

        self.lock = state
        if not user:
            self.lock_user = get_user_name()
        else:
            self.lock_user = user
        self.write_data()

    def get_work_files_changes(self):
        # TODO: add also products file if there's some in products folder
        current_work_files = fu.get_directory_content(pr.build_work_filepath(self))

        last_version = Version(self.uri + "@" + str(self.last_version))
        last_version.read_data()

        return fu.compare_directory_content(current_work_files, last_version.work_files)


def get_date_time():
    now = datetime.now()
    return now.strftime("%d-%m-%Y_%H-%M-%S")


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

