import os
import shutil
import message as msg

repository_root = "D:\\pipe\\pulse\\test\\repo"
repository_version_prefix = "V"
repository_version_padding = 3


def build_repository_path(path_type, commit):
    """custom function to build a repository path
    """
    return os.path.join(
        repository_root,
        commit.get_project().name,
        path_type,
        commit.resource_type,
        commit.entity.replace(":", "\\"),
        repository_version_prefix + str(commit.version).zfill(repository_version_padding)
    )


def copy_folder_tree(source_folder, destination_folder):
    """copy a folder tree, and creates subsequents destination folders if needed
    """
    destination_folder = os.path.normpath(destination_folder)
    parent_folder = os.path.dirname(destination_folder.rstrip("\\"))
    if not os.path.exists(parent_folder):
        os.makedirs(parent_folder)
    msg.new('DEBUG', "repo copy " + source_folder + " to " + destination_folder)
    shutil.copytree(source_folder, destination_folder) 


class PulseRepositoryError(Exception):
    def __init__( self, reason ):
        Exception.__init__(self)
        self._reason = reason

    def reason(self):
        return self._reason

    def __str__(self):
        return self._reason


class PulseRepository:
    def __init__(self):
        pass
    
    def copy_resource_commit(self, source_commit, target_commit):
        source_repo_work_path = build_repository_path("work", source_commit)
        source_repo_products_path = build_repository_path("products", source_commit)
        target_repo_work_path = build_repository_path("work", target_commit)
        target_repo_products_path = build_repository_path("products", target_commit)
        copy_folder_tree(source_repo_work_path, target_repo_work_path)
        copy_folder_tree(source_repo_products_path, target_repo_products_path)    
    
    def create_resource_empty_commit(self, commit):
        os.makedirs(build_repository_path("work", commit))
        os.makedirs(build_repository_path("products", commit))
        
    def upload_resource_commit(self, commit, work_folder, products_folder=None):
        """create a new resource default folders and file from a resource template
        """
    
        # Copy work folder to repo
        copy_folder_tree(work_folder, build_repository_path("work", commit))
    
        # Copy products folder to repo
        if not products_folder or not os.path.exists(products_folder):
            return True
        products_destination = build_repository_path("products", commit)
    
        ######################
        # This part manage the case where a user writes directly to the product repository
        if os.path.exists(products_destination):
            msg.new("INFO", "product already exists in repo : " + products_destination)
            return True
        ######################
    
        copy_folder_tree(products_folder, products_destination)
        return True
        
    def download_resource_commit(self, commit, work_folder):
        """build_work_user_filepath
        """
        repo_work_path = build_repository_path("work", commit)
        # copy repo work to sandbox
        copy_folder_tree(repo_work_path, work_folder)
        
    def download_product(self, product):
        """build_products_user_filepath
        """
        # build_products_repository_path
        product_repo_path = build_repository_path("products", product.commit) + "\\" + product.product_type
        # copy repo products type to products_user_filepath
        copy_folder_tree(product_repo_path, product.directory)
