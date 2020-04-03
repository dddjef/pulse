import project_config as cfg
import os
import shutil
import message as msg

work_repository_root = "D:\\pipe\\pulse\\test\\work_repository"
product_repository_root = "D:\\pipe\\pulse\\test\\product_repository"


def build_repository_path(root, commit):
    """custom function to build a repository path
    """
    if root == "work":
        root = work_repository_root
    elif root == "products":
        root = product_repository_root
    else:
        msg.new('ERROR', "ABORT : unknown uri type")
        return

    entities = commit.entity.replace(":", "\\")
    path = root + "\\" + commit.resource_type + "\\" + entities
    path += "\\" + cfg.VERSION_PREFIX + str(commit.version).zfill(cfg.VERSION_PADDING)
    return path


def copy_folder_tree(source_folder, destination_folder):
    """copy a folder tree, and creates subsequents destination folders if needed
    """
    destination_folder = os.path.normpath(destination_folder)
    parent_folder = os.path.dirname(destination_folder.rstrip("\\"))
    if not os.path.exists(parent_folder):
        os.makedirs(parent_folder)
    msg.new('DEBUG', "repo copy " + source_folder + " to " + destination_folder)
    shutil.copytree(source_folder, destination_folder)


def copy_resource_commit(source_commit, target_commit):
    source_repo_work_path = build_repository_path("work", source_commit)
    source_repo_products_path = build_repository_path("products", source_commit)
    target_repo_work_path = build_repository_path("work", target_commit)
    target_repo_products_path = build_repository_path("products", target_commit)
    copy_folder_tree(source_repo_work_path, target_repo_work_path)
    copy_folder_tree(source_repo_products_path, target_repo_products_path)


def upload_resource_commit(commit, work_folder, products_folder=None):
    """create a new resource default folders and file from a resource template
    """

    # Copy work folder to repo
    copy_folder_tree(work_folder, build_repository_path("work", commit))

    # Copy products folder to repo
    if not products_folder or not os.path.exists(products_folder):
        return True
    products_destination = build_repository_path("products", commit)

    ######################
    # This part manage the case a user writes directly to the product repository
    if os.path.exists(products_destination):
        msg.new("INFO", "product already exists in repo : " + products_destination)
        return True
    ######################

    copy_folder_tree(products_folder, products_destination)
    return True


def download_resource_commit(commit, work_folder):
    """build_work_user_filepath
    """
    repo_work_path = build_repository_path("work", commit)
    # copy repo work to sandbox
    copy_folder_tree(repo_work_path, work_folder)


def download_product(entity, resource_type, commit, product_type):
    """build_products_user_filepath
    """
    # abort if a product_type already exists in products_user_filepath
    # build_products_repository_path
    # copy repo products type to products_user_filepath
