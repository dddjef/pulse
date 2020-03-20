import pulse.uri_tools as uri_tools
import pulse.file_manager as fm
import project_config as cfg
import path_resolver as pr
import os
import database_linker as db
import message as msg
import hooks
import json

class PulseObject:
    def __init__(self, uri):
        self.uri = uri
        self.uri_dict = uri_tools.string_to_dict(uri)

    def write_data(self):
        db.write(entity_type=self.__class__.__name__, uri=self.uri, data_dict=vars(self))

    def read_data(self):
        data = db.read(entity_type=self.__class__.__name__, uri=self.uri)
        if data:
            for k in data:
                setattr(self, k, data[k])
            return True
        else:
            msg.new('ERROR', 'No data found for ' + self.uri)
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

    def get_resource(self):
        pass

    def get_products(self):
        pass


class Resource(PulseObject):
    def __init__(self, uri):
        PulseObject.__init__(self, uri)
        self.lock = False
        self.lock_user = ''
        self.last_version = 0

    def get_version(self, index):
        pass

    def user_needs_lock(self):
        if self.lock and self.lock_user != get_user_name():
            msg.new('ERROR', "the resource is locked by another user")
            return True
        return False
    
    def commit(self, comment="", include_products=True):
        # check current the user permission
        if self.user_needs_lock():
            return

        # build the new version uri
        version_uri = self.uri + "@" + str(self.last_version + 1)
        version = Version(version_uri)
        version.comment = comment

        # get the sandbox folder and test it exists
        work_source_folder = pr.build_work_filepath(version.uri_dict)
        if not os.path.exists(work_source_folder):
            msg.new('ERROR', "this resource is not in your sandbox")
            return

        # TODO : check the sandbox is up to date

        # launch the pre commit hook
        hooks.pre_commit(self)

        # if user wants to export products folder, build path and test it's valid
        if include_products:
            products_source_folder = pr.build_product_filepath(version.uri_dict)
            print "products_source : " + products_source_folder
            if not os.path.exists(products_source_folder):
                products_source_folder = None
        else:
            products_source_folder = None
        # TODO : if products are not included, they should be moved to trash

        fm.upload_resource_version(version.uri_dict, work_source_folder, products_source_folder)

        version.write_data()
        self.last_version += 1
        self.write_data()
        # TODO : Make user products read only
        # TODO : save resource files content and date to the version data
        # TODO : update the sandbox version number

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

        destination_folder = pr.build_work_filepath(self.uri_dict)

        # abort if the resource is already in user sandbox
        if os.path.exists(destination_folder):
            msg.new('ERROR', "can't check out a resource already in your sandbox")
            return

        # download the version
        fm.download_resource_version(self.uri_dict, index, destination_folder)

        # TODO : create the attended products folder?

        msg.new('INFO', "resource check out in : " + destination_folder)

    def trash_work(self):
        work_folder = pr.build_work_filepath(self.uri_dict)
        # abort if the resource is already in user sandbox
        if os.path.exists(work_folder):
            msg.new('ERROR', "can't check out a resource already in your sandbox")
            return
        # TODO : move work to trash
        pass

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

    def get_status(self):
        return vars(self)


def get_user_name():
    return os.environ.get('USERNAME')


def create_resource(uri):
    """Create a new resource for the given entity and type
    """
    # abort if the resource already exists
    if db.read("Resource", uri):
        msg.new('ERROR', "there's already a resource named : " + uri)
        return

    # abort if the template does not exists
    resource = Resource(uri)
    template_path = pr.build_resource_template_path(resource.uri_dict)
    if not os.path.exists(template_path):
        msg.new("ERROR", "No template found for " + template_path)
        return

    # check products templates exists
    products_template_path = template_path + "\\PRODUCTS"
    if not os.path.exists(products_template_path):
        products_template_path = None

    # write the resource to database
    resource.write_data()

    # initialize a first version
    version_uri = uri + "@0"
    fm.upload_resource_version(uri_tools.string_to_dict(version_uri), template_path + "\\WORK", products_template_path)
    version = Version(version_uri)
    version.comment = "init from template"
    version.write_data()

    return resource


def get_directory_content(directory):
    files_dict = {}
    for root, subdirectories, files in os.walk(directory):
        for f in files:
            filepath = os.path.join(root, f)
            files_dict[filepath] = {"mdate": os.path.getmtime(filepath)}
    return files_dict


def write_directory_content(directory, json_filepath=None):
    files_dict = get_directory_content(directory)
    if not json_filepath:
        json_filepath = os.path.join(directory, "content.json")

    with open(json_filepath, "w") as write_file:
        json.dump(files_dict, write_file, indent=4, sort_keys=True)
    return json_filepath




def get_resource(uri):
    resource = Resource(uri)
    if resource.read_data():
        return resource
    else:
        return None


if __name__ == '__main__':

    """
    import string
    import random
    letters = string.ascii_lowercase
    entity_name = ''.join(random.choice(letters) for i in range(10))
    #entity_name = "fixedB"

    uri_test = entity_name + "-modeling"

    create_resource(uri_test)
    resource = get_resource(uri_test)
    resource.checkout()
    resource.set_lock(True)
    resource.commit("very first time")
    print resource.get_status()

    # if not my_version:
    #     my_version = Version(uri_test + "@0")

    """
    print (write_directory_content("D:\maison"))