import os
import shutil
from pulse.repository_adapters.interface_class import *
import pulse.file_utils as fu


def copy_folder_content(source_folder, destination_folder):
    """copy a folder tree, and creates subsequents destination folders if needed
    """
    destination_folder = os.path.normpath(destination_folder)
    source_folder = os.path.normpath(source_folder)
    if not os.path.exists(source_folder):
        return
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)
    for node in os.listdir(source_folder):
        source_filepath = os.path.join(source_folder, node)
        destination_filepath = os.path.join(destination_folder, node)
        if os.path.isdir(source_filepath):
            if os.path.exists(destination_filepath):
                shutil.rmtree(destination_filepath)
            fu.copytree(source_filepath, destination_filepath)
        else:
            shutil.copyfile(source_filepath, destination_filepath)


class Repository(PulseRepository):
    def __init__(self, login="", password="", settings=None):
        PulseRepository.__init__(self, login, password, settings)
        self.root = self.settings["path"]

        self.version_prefix = "V"
        self.version_padding = 3

    def test_settings(self):
        if "\\" in self.root:
            raise PulseRepositoryError("the root path should use slash separator only")
        if not os.path.exists(self.root):
            os.makedirs(self.root)
        return True

    def _build_commit_path(self, path_type, commit):
        """custom function to build a repository path
        """
        return os.path.join(
            self._build_resource_path(path_type, commit.resource),
            self.version_prefix + str(commit.version).zfill(self.version_padding)
        )

    def _build_resource_path(self, path_type, resource):
        return os.path.join(
            os.path.expandvars(self.root),
            resource.project.name,
            path_type,
            resource.resource_type,
            resource.entity.replace(":", os.sep)
        )
        
    def upload_resource_commit(self, commit, work_folder, work_files, products_folder=None):
        version_directory = self._build_commit_path("work", commit)
        os.makedirs(version_directory)
        # Copy work files to repo
        for filepath_rel in work_files:
            dest = version_directory + filepath_rel
            dest_dir = os.path.split(dest)[0]
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir)
            shutil.copyfile(work_folder + filepath_rel, dest)

        # Copy products folder to repo
        if not products_folder or not os.path.exists(products_folder):
            return True
        products_destination = self._build_commit_path("products", commit)
    
        ######################
        # This part manage the case where a user writes directly to the product repository
        if os.path.exists(products_destination):
            return True
        ######################
    
        copy_folder_content(products_folder, products_destination)
        return True
        
    def download_work(self, commit, work_folder):
        repo_work_path = self._build_commit_path("work", commit)
        # copy repo work to sandbox
        copy_folder_content(repo_work_path, work_folder)

    def download_product(self, product, product_folder=None):
        # build_products_repository_path
        product_repo_path = os.path.join(self._build_commit_path("products", product.parent), product.product_type)
        # copy repo products type to products_user_filepath
        if not product_folder:
            product_folder = product.directory
        copy_folder_content(product_repo_path, product_folder)

    def download_resource(self, resource, destination):
        resource_product_repo_path = self._build_resource_path("products", resource)
        resource_work_repo_path = self._build_resource_path("work", resource)
        copy_folder_content(resource_product_repo_path, os.path.join(destination, "products"))
        copy_folder_content(resource_work_repo_path, os.path.join(destination, "work"))

    def upload_resource(self, resource, source):
        resource_product_repo_path = self._build_resource_path("products", resource)
        resource_work_repo_path = self._build_resource_path("work", resource)

        copy_folder_content(os.path.join(source, "products"), resource_product_repo_path)
        copy_folder_content(os.path.join(source, "work"), resource_work_repo_path)

    def remove_resource(self, resource):
        product_path = self._build_resource_path("products", resource)
        if os.path.exists(product_path):
            shutil.rmtree(self._build_resource_path("products", resource))
        shutil.rmtree(self._build_resource_path("work", resource))
