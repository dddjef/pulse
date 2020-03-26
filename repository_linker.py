import project_config as cfg
import os
import shutil
import message as msg


def build_repository_path(root, resource, version=None):
    """custom function to build a repository path
    """
    if root == "work":
        root = cfg.WORK_REPOSITORY_ROOT
    elif root == "product":
        root = cfg.PRODUCT_REPOSITORY_ROOT
    else:
        msg.new('ERROR', "ABORT : unknown uri type")
        return

    entities = resource.entity.replace(":", "\\")
    path = root + "\\" + resource.resource_type + "\\" + entities
    if version != None:
        path += "\\" + cfg.VERSION_PREFIX + str(version).zfill(cfg.VERSION_PADDING)
    return path


def copy_folder_tree(source_folder, destination_folder):
    """copy a folder tree, and creates subsequents destination folders if needed
    """
    destination_folder = os.path.normpath(destination_folder)
    parent_folder = os.path.dirname(destination_folder.rstrip("\\"))
    if not os.path.exists(parent_folder):
        os.makedirs(parent_folder)

    shutil.copytree(source_folder, destination_folder)
    msg.new('DEBUG', "repo copy " + source_folder + " to " + destination_folder)


def upload_resource_version(resource, version, work_folder, products_folder=None):
    """create a new resource default folders and file from a resource template
    """

    # Copy work folder to repo
    copy_folder_tree(work_folder, build_repository_path("work", resource, version))

    # Copy products folder to repo
    if not products_folder or not os.path.exists(products_folder):
        return True
    products_destination = build_repository_path("product", resource, version)

    ######################
    # This part manage the case a user writes directly to the product repository
    if os.path.exists(products_destination):
        msg.new("INFO", "product already exists in repo : " + products_destination)
        return True
    ######################

    copy_folder_tree(products_folder, products_destination)
    return True


def download_resource_version(resource, version, work_folder):
    """build_work_user_filepath
    """
    repo_work_path = build_repository_path("work", resource, version)
    # copy repo work to sandbox
    copy_folder_tree(repo_work_path, work_folder)


def download_product(entity, resource_type, version, product_type):
    """build_products_user_filepath
    """
    # abort if a product_type already exists in products_user_filepath
    # build_products_repository_path
    # copy repo products type to products_user_filepath

