import os
from pulse.repository_adapters.interface_class import PulseRepository
import ftplib


def ftp_copytree(source, ftp_connection):
    files = os.listdir(source)
    for f in files:
        fp = os.path.join(source, f)
        if os.path.isfile(fp):
            fh = open(fp, 'rb')
            ftp_connection.storbinary('STOR %s' % f, fh)
            fh.close()
        elif os.path.isdir(fp):
            ftp_connection.mkd(f)
            ftp_connection.cwd(f)
            ftp_copytree(fp, ftp_connection)
    ftp_connection.cwd('..')


def ftp_cwd_makedirs(directory, ftp_connection):
    """
    change current ftp path to directory
    creates subsequent directories if needed
    :param directory:
    :param ftp_connection:
    :return:
    """
    ftp_connection.cwd('/')
    try:
        ftp_connection.cwd(directory)
    except:
        splitted_path = os.path.normpath(directory).split(os.sep)
        try:
            for item in splitted_path:
                try:
                    ftp_connection.cwd(item)
                except:
                    ftp_connection.mkd(item)
                    ftp_connection.cwd(item)
        except Exception, e:
            print e


def ftp_rmtree(path, ftp):
    """path should be the absolute path to the root FOLDER of the file tree to remove"""
    try:
        names = ftp.nlst(path)
    except ftplib.all_errors as e:
        print ('FtpRmTree: Could not list {0}: {1}'.format(path, e))
        return

    for name in names:
        # some ftp return the full path on nlst command,ensure you get only the file or folder name here
        name = name.split("/")[-1]

        if os.path.split(name)[1] in ('.', '..'):
            continue

        try:
            ftp.delete(path + "/" + name)
        except ftplib.all_errors:
            ftp_rmtree(path + "/" + name, ftp)

    try:
        ftp.rmd(path)
    except ftplib.all_errors as e:
        raise e


def ftp_download(source, destination, ftp_connection):
    """path & destination are str of the form "/dir/folder/something/"
    #path should be the abs path to the root FOLDER of the file tree to download
    """
    source = source.replace("\\", "/")
    destination = destination.replace("\\", "/")
    for filename in ftp_connection.nlst():
        if filename == "." or filename == "..":
            continue
        ftp_path = source + "/" + filename
        disk_path = (os.path.join(destination, filename))
        try:
            ftp_connection.cwd(ftp_path)
            if not os.path.exists(disk_path):
                os.makedirs(disk_path)
            ftp_download(ftp_path, disk_path, ftp_connection)
            ftp_connection.cwd(source)
        except ftplib.error_perm:
            ftp_connection.retrbinary("RETR " + filename, open(disk_path, "wb").write)


class Repository(PulseRepository):
    def __init__(self, login, password, settings):
        PulseRepository.__init__(self, login, password, settings)
        self.root = self.settings["root"]
        if not self.root.endswith('/'):
            self.root += '/'
        self.version_prefix = "V"
        self.version_padding = 3
        self.connection = None
        self._refresh_connection()

    def test_settings(self):
        self._refresh_connection()
        return True

    def _refresh_connection(self):
        try:
            self.connection.voidcmd("NOOP")
        except:
            self.connection = ftplib.FTP()
            self.connection.connect(self.settings["host"], self.settings["port"])
            self.connection.login(self.login, self.password)
        self.connection.cwd(self.root)

    def _upload_folder(self, source, destination):
        if not os.path.exists(source):
            return
        source = source.replace("\\", "/")
        destination = destination.replace("\\", "/")
        self._refresh_connection()
        ftp_cwd_makedirs(self.root + destination, self.connection)
        self.connection.cwd(self.root + destination)
        ftp_copytree(source, self.connection)

    def _download_folder(self, source, destination):
        source = source.replace("\\", "/")
        destination = destination.replace("\\", "/")
        if not os.path.exists(destination):
            os.makedirs(destination)
        self._refresh_connection()
        self.connection.cwd(self.root + source)
        ftp_download(self.root + source, destination, self.connection)

    def _build_commit_path(self, path_type, commit):
        """custom function to build a repository path
        """
        return os.path.join(
            self._build_resource_path(path_type, commit.resource),
            self.version_prefix + str(commit.version).zfill(self.version_padding)
        ).replace("\\", "/")

    @staticmethod
    def _build_resource_path(path_type, resource):
        return os.path.join(
            resource.project.name,
            path_type,
            resource.resource_type,
            resource.entity.replace(":", "/")
        ).replace("\\", "/")

    def upload_resource_commit(self, commit, work_folder, work_files, products_folder=None):
        """create a new resource default folders and file from a resource template
        """

        # create the version folder
        work_destination = self._build_commit_path("work", commit)
        self._refresh_connection()
        version_folder = self.root + work_destination
        ftp_cwd_makedirs(version_folder, self.connection)
        self.connection.cwd(version_folder)

        # Copy work files to repo
        current_directory = version_folder
        for rel_filepath in work_files:
            file_dir = os.path.dirname(version_folder + rel_filepath)
            if file_dir != current_directory:
                ftp_cwd_makedirs(file_dir, self.connection)
                current_directory = file_dir
            filename = os.path.basename(rel_filepath)
            fp = work_folder + rel_filepath
            fh = open(fp, 'rb')
            self.connection.storbinary('STOR %s' % filename, fh)
            fh.close()

        # Copy products folder to repo
        if not products_folder or not os.path.exists(products_folder):
            return True
        products_destination = self._build_commit_path("products", commit)

        self._upload_folder(products_folder, products_destination)
        return True

    def download_work(self, commit, work_folder):
        """build_work_user_filepath
        """
        repo_work_path = self._build_commit_path("work", commit)
        self._download_folder(repo_work_path, work_folder)

    def download_product(self, product, product_folder=None):
        # build_products_repository_path
        product_repo_path = self._build_commit_path("products", product.parent) + os.sep + product.product_type
        if not product_folder:
            product_folder = product.directory
        self._download_folder(product_repo_path, product_folder)

    def download_resource(self, resource, destination):
        resource_product_repo_path = self._build_resource_path("products", resource)
        resource_work_repo_path = self._build_resource_path("work", resource)
        self._download_folder(resource_product_repo_path, os.path.join(destination, "products"))
        self._download_folder(resource_work_repo_path, os.path.join(destination, "work"))

    def upload_resource(self, resource, source):
        resource_product_repo_path = self._build_resource_path("products", resource)
        resource_work_repo_path = self._build_resource_path("work", resource)
        self._upload_folder(os.path.join(source, "products"), resource_product_repo_path)
        self._upload_folder(os.path.join(source, "work"), resource_work_repo_path)

    def remove_resource(self, resource):
        self._refresh_connection()
        ftp_rmtree(self.root + self._build_resource_path("products", resource), self.connection)
        ftp_rmtree(self.root + self._build_resource_path("work", resource), self.connection)

    def reset_project(self, project):
        self._refresh_connection()
        self.connection.cwd(project.name)
        for directory in self.connection.nlst():
            ftp_rmtree(self.root + "/" + project.name + "/" + directory, self.connection)
