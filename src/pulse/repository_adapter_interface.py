# your repository adapter plugin should have a "Repository" class inherited from PulseRepository
from pulse.exception import *
# TODO : update with uri

class PulseRepository:
    def __init__(self, login="", password="", settings=None):
        self.settings = settings
        self.login = login
        self.password = password

    def test_settings(self):
        """
        test the adaptor settings
        :return: True on success
        """
        pass

    def upload_resource_commit(self, project_name, uri, work_folder, work_files, products_files, product_directory):
        """upload a commit content to repository
        """
        pass

    def download_work(self, project_name, commit, work_folder):
        """download a resource work content to a local folder. Creates the folder if needed
        """
        pass

    def download_product(self, project_name, product, destination_folder, subpath=""):
        """download a product content to a local folder. Creates the folder if needed
            raise a PulseRepositoryError if the subpath is unreachable
        """
        pass

    def download_resource(self, project_name, resource, destination):
        """download a resource content  and all its history to a local folder. Creates the folder if needed
         """
        pass

    def upload_resource(self, project_name, resource, source):
        """upload a resource content and all its history to repository from a local source directory
         """
        pass

    def remove_resource(self, project_name, resource):
        """remove a resource and all its history from repository
         """
        pass
