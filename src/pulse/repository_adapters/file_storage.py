import os
import shutil
from pulse.repository_adapter_interface import *
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
            fu.copytree(source_filepath, destination_filepath)
        else:
            if not os.path.exists(destination_filepath):
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

    def _build_commit_path(self, project_name, path_type, uri):
        #TODO : simplify here, too much fuctions
        """custom function to build a repository path
        """
        return os.path.join(
            self._build_resource_path(project_name, path_type, uri)
        )

    def _build_resource_path(self, project_name, path_type, uri):
        return os.path.join(
            os.path.expandvars(self.root),
            project_name,
            path_type,
            uri.replace("/", "~")
        )

    @staticmethod
    def _copy_files(relative_filepath_list, source_root, destination_root):
        os.makedirs(destination_root)
        for filepath_rel in relative_filepath_list:
            destination = destination_root + filepath_rel
            destination_dir = os.path.split(destination)[0]
            if not os.path.isdir(destination_dir):
                os.makedirs(destination_dir)
            shutil.copyfile(source_root + filepath_rel, destination)

    def upload_resource_commit(self, project_name, uri, work_folder, work_files, products_files, product_directory):
        self._copy_files(work_files, work_folder, self._build_commit_path( project_name, "work", uri))
        self._copy_files(products_files, product_directory, self._build_commit_path( project_name, "products", uri))
        return True

    def download_work(self, project_name, uri, work_folder):
        repo_work_path = self._build_commit_path(project_name, "work", uri)
        # copy repo work to sandbox
        copy_folder_content(repo_work_path, work_folder)

    def download_product(self, project_name, uri, destination_folder, subpath=""):
        # build_products_repository_path
        product_repo_path = os.path.join(self._build_commit_path(project_name, "products", uri), subpath)
        if not os.path.exists(product_repo_path):
            raise PulseRepositoryError("path does not exists : " + product_repo_path)
        # copy repo products type to products_user_filepath
        copy_folder_content(product_repo_path, destination_folder)

    def download_resource(self, project_name, uri, destination):
        resource_product_repo_path = self._build_resource_path(project_name, "products", uri)
        resource_work_repo_path = self._build_resource_path(project_name, "work", uri)
        copy_folder_content(resource_product_repo_path, os.path.join(destination, "products"))
        copy_folder_content(resource_work_repo_path, os.path.join(destination, "work"))

    def upload_resource(self, project_name, uri, source):
        resource_product_repo_path = self._build_resource_path(project_name, "products", uri)
        resource_work_repo_path = self._build_resource_path(project_name, "work", uri)

        copy_folder_content(os.path.join(source, "products"), resource_product_repo_path)
        copy_folder_content(os.path.join(source, "work"), resource_work_repo_path)

    def remove_resource(self, project_name, resource):
        product_path = self._build_resource_path(project_name, "products", resource)
        if os.path.exists(product_path):
            shutil.rmtree(self._build_resource_path(project_name, "products", resource))
        shutil.rmtree(self._build_resource_path(project_name, "work", resource))
