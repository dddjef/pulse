import pulse.uri_tools as uri_tools
import pulse.file_manager as fm
import project_config as cfg
import path_resolver as pr
import os
import database_linker as db
import message as msg



class Product:
    def __init__(self, version, product_type):
        self.version = version
        self.product_type = product_type


class Version:
    def __init__(self, uri):
        self.uri = uri
        self.resource = None
        self.comment = ""

    def get_products(self):
        pass

    def checkout(self):
        # abort if the resource is already in user sandbox
        print pr.build_work_filepath(self.resource)
        # checkout the last version

    def write_data(self):
        db.write("Version", self.uri, vars(self))

    def read_data(self):
        resource_data = db.read("Version", self.uri)
        if resource_data:
            self.comment = resource_data['comment']
        else:
            msg.new('ERROR', 'No data found for ' + self.uri)


class Resource:
    def __init__(self, uri):
        self.uri = uri
        self.lock = False
        self.lock_user = ''
        self.last_version = 0

    def get_version(self, index):
        pass

    def create_version(self, include_products=True, comments=""):
        # abort if the resource is locked by someone else
        if self.lock:
            msg.new('ERROR', "resource is locked by " + self.lock_user)
            return

        # build the new version uri
        version_uri = self.uri + "@" + str(self.versions_count + 1)

        # build_work_user_filepath
        work_source_folder = pr.build_work_filepath(version_uri)
        # TO DO : check the sandbox is up to date

        # build_product_user_filepath
        if include_products:
            products_source_folder = pr.build_product_filepath(version_uri)

        fm.upload_resource_version(version_uri, work_source_folder, products_source_folder)

        new_version = Version(version_uri, comments)

        self.last_version += 1
        self.write_data()
        # TO DO : Make user products read only

    def checkout(self):
        pass
        # abort if the resource is already in user sandbox
        # checkout the last version

    def write_data(self):
        db.write("Resource", self.uri, vars(self))

    def read_data(self):
        resource_data = db.read("Resource", self.uri)
        if resource_data:
            for k in resource_data:
                setattr(self, k, resource_data[k])
        else:
            msg.new('ERROR', 'No data found for ' + self.uri)


def list_resources(uri_search_string):
    return fm.list_resources(uri_tools.string_to_dict(uri_search_string))


def create_resource(uri):
    """Create a new resource for the given entity and type
    """
    uri_dict = uri_tools.string_to_dict(uri)

    # abort if the resource already exists
    if db.read("Resource", uri):
        msg.new('ERROR', "there's already a resource named : " + uri)
        return

    # abort if the template does not exists
    template_path = pr.build_resource_template_path(uri_dict['resource_type'])
    if not os.path.exists(template_path):
        msg.new("ERROR", "No template found for " + template_path)
        return

    # check products templates exists
    products_template_path = template_path + "\\PRODUCTS"
    if not os.path.exists(products_template_path):
        products_template_path = None

    resource = Resource(uri)
    resource.write_data()

    version_uri = uri + "@0"
    fm.upload_resource_version(version_uri, template_path + "\\WORK", products_template_path)
    version = Version(version_uri)
    version.write_data()
    print version

    #resource.create_version(work_source_folder=template_path + "\\WORK", products_source_folder=products_template_path)


def checkout(uri_string):
    """Download the resource work files in the user sandbox.
    TO DO : If no version is specified, the last version will be downloaded
    TO DO : read related dependencies in the json file
    TO DO : Download related dependencies if they are not available in products path
    """
    uri = uri_tools.string_to_dict(uri_string)
    fm.download_resource(uri)
    print uri


if __name__ == '__main__':
    import string
    import random
    letters = string.ascii_lowercase
    entity_name = ''.join(random.choice(letters) for i in range(10))

    uri_test = entity_name + "-modeling"

    my_version = create_resource(uri_test)
    # if not my_version:
    #     my_version = Version(uri_test + "@0")
    #my_version.checkout()
