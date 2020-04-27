import os
import shutil
import pulse.message as msg
from pulse.repository_adapters.interface_class import *


# TODO : define the "products" and "work" wording in the interface class


def copy_folder_tree(source_folder, destination_folder):
    """copy a folder tree, and creates subsequents destination folders if needed
    """
    destination_folder = os.path.normpath(destination_folder)
    parent_folder = os.path.dirname(destination_folder.rstrip("\\"))
    if not os.path.exists(parent_folder):
        os.makedirs(parent_folder)
    msg.new('DEBUG', "repo copy " + source_folder + " to " + destination_folder)
    shutil.copytree(source_folder, destination_folder) 


class Repository(PulseRepository):
    def __init__(self, parameters):
        self.root = parameters["root"]
        self.version_prefix = "V"
        self.version_padding = 3
        PulseRepository.__init__(self)

    def _build_commit_path(self, path_type, commit):
        """custom function to build a repository path
        """
        return os.path.join(
            self._build_resource_path(path_type, commit.resource),
            self.version_prefix + str(commit.version).zfill(self.version_padding)
        )

    def _build_resource_path(self, path_type, resource):
        return os.path.join(
            self.root,
            resource.project.name,
            path_type,
            resource.resource_type,
            resource.entity.replace(":", "\\")
        )
        
    def upload_resource_commit(self, commit, work_folder, products_folder=None):
        """create a new resource default folders and file from a resource template
        """
    
        # Copy work folder to repo
        copy_folder_tree(work_folder, self._build_commit_path("work", commit))
    
        # Copy products folder to repo
        if not products_folder or not os.path.exists(products_folder):
            return True
        products_destination = self._build_commit_path("products", commit)
    
        ######################
        # This part manage the case where a user writes directly to the product repository
        if os.path.exists(products_destination):
            msg.new("INFO", "product already exists in repo : " + products_destination)
            return True
        ######################
    
        copy_folder_tree(products_folder, products_destination)
        return True
        
    def download_work(self, commit, work_folder):
        """build_work_user_filepath
        """
        repo_work_path = self._build_commit_path("work", commit)
        # copy repo work to sandbox
        copy_folder_tree(repo_work_path, work_folder)

    def download_product(self, product):
        """build_products_user_filepath
        """
        # build_products_repository_path
        product_repo_path = os.path.join(self._build_commit_path("products", product.parent), product.product_type)
        # copy repo products type to products_user_filepath
        copy_folder_tree(product_repo_path, product.directory)

    def download_resource(self, resource, destination):
        resource_product_repo_path = self._build_resource_path("products", resource)
        resource_work_repo_path = self._build_resource_path("work", resource)

        copy_folder_tree(resource_product_repo_path, os.path.join(destination, "products"))
        copy_folder_tree(resource_work_repo_path, os.path.join(destination, "work"))

    def upload_resource(self, resource, source):
        resource_product_repo_path = self._build_resource_path("products", resource)
        resource_work_repo_path = self._build_resource_path("work", resource)

        copy_folder_tree(os.path.join(source, "products"), resource_product_repo_path)
        copy_folder_tree(os.path.join(source, "work"), resource_work_repo_path)

    def remove_resource(self, resource):
        shutil.rmtree(self._build_resource_path("products", resource))
        shutil.rmtree(self._build_resource_path("work", resource))
