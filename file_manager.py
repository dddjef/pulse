import project_config as cfg
import os
import shutil

def build_resource_template_path(resource_type):
    """custom function to build a template path
    """
    return cfg.TEMPLATE_PATH + "\\" + resource_type


def build_work_repository_path(uri):
    """custom function to build a work path.
    ie : can use an external database to define the server
    """
    path = cfg.WORK_REPOSITORY_ROOT + "\\" + uri['resource_type']
    entities = uri['entity'].split(":")
    for entity in entities:
        path += "\\" + entity
    return path + "\\V" + uri['version'].zfill(cfg.VERSION_PADDING)


def build_products_repository_path(uri):
    """custom function to build products path.
    """
    path = cfg.PRODUCT_REPOSITORY_ROOT + "\\" + uri['resource_type']
    entities = uri['entity'].split(":")
    for entity in entities:
        path += "\\" + entity
    return path

def build_work_user_filepath(entity, resource_type):
    """custom function to build a sandbox resource path.
    """


def build_products_user_filepath(entity, resource_type,version):
    """custom function to build a user product resource path.
    """


def create_resource(uri):
    """build_work_repository_path
    """
    # build repo work path for initial version and abort if it already exists
    repo_work_path = build_work_repository_path(uri)
    if os.path.exists(repo_work_path):
        print("ABORT : resource already exists at " + repo_work_path)
        return

    # build_resource_template_path
    template_path = build_resource_template_path(uri['resource_type'])
    if not os.path.exists(template_path):
        print("DEFAULT MODE : No template found for " + uri['resource_type'])
        template_path = ""

    # Copy the template work to repo work initial version or create an empty folder if there's no template
    if template_path == "":
        os.makedirs(repo_work_path)
    else:
        shutil.copytree(template_path + "\\WORK", repo_work_path)

    # build_products_repository_path(version = 0)


    # copy the template products to products repo


def download_resource(entity, resource_type, version):
    """build_work_user_filepath
    """
    # abort if it already exists
    # build_work_repository_path
    # copy repo work to sandbox


def download_product(entity, resource_type, version, product_type):
    """build_products_user_filepath
    """
    # abort if a product_type already exists in products_user_filepath
    # build_products_repository_path
    # copy repo products type to products_user_filepath


def upload_resource(entity, resource_type):
    """
    upload to repositories a sandbox work and its products
    :param entity:
    :param resource_type:
    :return:
    """
    # abort if the resource is locked by someone else
    # build_work_repository_path (v+1)
    # abort if it already exists
    # build_work_user_filepath
    # copy repo work to sandbox
    # build_products_user_filepath
    # build_products_repository_path
    # Copy each product to repository of it doesn't exists yet
    # Make user products read only


def lock(entity, resource_type):
    """store a lock information for the given resource.
    """
    # Save the current user name, the date, the workstation


def unlock(entity, resource_type):
    """remove the lock from the resource
    """


def get_lock_info(entity, resource_type):
    """return lock information for the given resource.
    return None if there is no current lock
    """
