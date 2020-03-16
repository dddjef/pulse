import pulse.uri_tools as uri_tools
import pulse.file_manager as fm
import project_config as cfg
import path_resolver as pr
import os
import database_linker as db

class Product:
    def __init__(self, version, product_type):
        self.version = version
        self.product_type = product_type


class Version:
    def __init__(self, resource, index, comment=""):
        self.resource = resource
        self.index = index
        #self.uri = resource.uri + "@" + str(index).zfill(cfg.VERSION_PADDING)
        self.comment = comment

    def get_products(self):
        pass

    def checkout(self):
        # abort if the resource is already in user sandbox
        print pr.build_work_filepath(self.resource)
        # checkout the last version

class Resource:
    def __init__(self, uri_dict):
        self.entity = uri_dict['entity']
        self.resource_type = uri_dict['resource_type']
        self.lock = False

    def get_versions(self):
        pass

    def create_version(self):
        pass
        # abort if the resource is locked by someone else
        # build_work_repository_path (v+1)
        # abort if it already exists
        # build_work_user_filepath
        # copy repo work to sandbox
        # build_products_user_filepath
        # build_products_repository_path
        # Copy each product to repository of it doesn't exists yet
        # Make user products read only

    def checkout(self):
        pass
        # abort if the resource is already in user sandbox
        # checkout the last version

    def write_data(self):
        print vars(self)
        #db.write_resource(self)


def message(type, body):
    print(type + ":" + body)


def list_resources(uri_search_string):
    return fm.list_resources(uri_tools.string_to_dict(uri_search_string))


def create_resource(uri_string):
    """Create a new resource for the given entity and type
    """
    uri = uri_tools.string_to_dict(uri_string)

    # abort if the resource already exists
    if list_resources(uri_string):
        message('ERROR', "there's already a resource named : " + uri_string)
        return

    # abort if the template does not exists
    template_path = pr.build_resource_template_path(uri['resource_type'])
    if not os.path.exists(template_path):
        message("ERROR", "No template found for " + template_path)
        return

    # create products templates if they exists
    products_template_path = template_path + "\\PRODUCTS"
    if not os.path.exists(products_template_path):
        products_template_path = None

    if fm.upload_resource_version(uri, template_path + "\\WORK", products_template_path):
        resource = Resource(uri_dict=uri)
        return Version(resource, index=0, comment="template version")


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
    uri_test = "pahhjk-modeling"
    my_version = create_resource(uri_test)
    if not my_version:
        my_version = Version(uri_test + "@0")
    my_version.checkout()
