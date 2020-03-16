import project_config as cfg
import os
import shutil
import json
import glob

DB_folder = cfg.WORK_REPOSITORY_ROOT + "\\DB"

def build_repository_path(root, uri):
    """custom function to build a work repository path
    """
    entities = uri['entity'].replace(":", "\\")
    version = cfg.VERSION_PREVIX + str(uri['version']).zfill(cfg.VERSION_PADDING)
    return root + "\\" + uri['resource_type'] + "\\" + entities + "\\" + version


def copy_folder_tree(source_folder, destination_folder):
    """copy a folder tree, and creates subsequents destination folders if needed
    """
    destination_folder = os.path.normpath(destination_folder)
    if not os.path.exists(destination_folder):
        os.makedirs(os.path.dirname(destination_folder.rstrip("\\")))

    shutil.copytree(source_folder, destination_folder)


def upload_resource_version(uri, work_folder, products_folder=None):
    """create a new resource default folders and file from a resource template
    """
    # Copy work folder to repo
    copy_folder_tree(work_folder, build_repository_path(cfg.WORK_REPOSITORY_ROOT, uri))

    # Copy products folder to repo if needed
    if not products_folder:
        return True
    copy_folder_tree(products_folder, build_repository_path(cfg.PRODUCT_REPOSITORY_ROOT, uri))

    return True


def list_resources(uri):
    return glob.glob(build_repository_path(cfg.WORK_REPOSITORY_ROOT, uri))

###################################
###################################





def download_work(uri, work_folder):
    """build_work_user_filepath
    """
    # build user work path abort if it already exists
    user_work_path = build_work_user_filepath(uri)
    if os.path.exists(user_work_path):
        print "ABORT download_resource : folder already exists " + user_work_path


    # build repo work path abort if does not exists
    repo_work_path = build_work_repository_path(uri)
    if not os.path.exists(repo_work_path):
        print("ABORT : resource does not exists at " + repo_work_path)
        return

    # copy repo work to sandbox
    shutil.copytree(repo_work_path, user_work_path)

def download_product(entity, resource_type, version, product_type):
    """build_products_user_filepath
    """
    # abort if a product_type already exists in products_user_filepath
    # build_products_repository_path
    # copy repo products type to products_user_filepath



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
