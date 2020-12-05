from pulse.api import *
import unittest
import os
import mysql.connector as mariadb
import ftplib
from ConfigParser import ConfigParser

test_dir = os.path.dirname(__file__)
db_root = os.path.join(test_dir, "DB")
user_works = os.path.join(test_dir, "works")
user_products = os.path.join(test_dir, "products")
repos = os.path.join(test_dir, "repos")
test_project_name = "testProject"


"""
CONFIGURATION
# you have to install mysql connector (pip install mysql-connector-python)
# you have to set up tests/custom_adapters_config.ini file according to your own connection parameters
example :
[db]
host = 192.168.1.2
port = 3306
login = pulseAdmin
password = ***
[ftp]
host = 192.168.1.2
port = 21
login = pulseTest
password = ***
root = pulseTest/
"""


config = ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.realpath(__file__)), "custom_adapters_config.ini"))
db_url = "mysql://" + config.get('db', 'login') + ':' + config.get('db', 'password')\
         + '@' + config.get('db', 'host') + ':' + config.get('db', 'port')
ftp_url = 'ftp://' + config.get('ftp', 'login') + ':' + config.get('ftp', 'password')\
          + '@' + config.get('ftp', 'host') + ':' + config.get('ftp', 'port') + '/' + config.get('ftp', 'root')


def remove_ftp_dir(ftp, path):
    for (name, properties) in ftp.nlst(path=path):
        if name in ['.', '..']:
            continue
        elif properties['type'] == 'file':
            ftp.delete(path + "/" + name)
        elif properties['type'] == 'dir':
            remove_ftp_dir(ftp, path + "/" + name)
    ftp.rmd(path)


def ftp_rmtree(ftp, path):
    """Recursively delete a directory tree on a remote server."""
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
            ftp_rmtree(ftp, path + "/" + name)

    try:
        ftp.rmd(path)
    except ftplib.all_errors as e:
        raise e


def reset_files():
    cnx = mariadb.connect(host=config.get('db', 'host'), port=config.get('db', 'port'),
                          user=config.get('db', 'login'), password=config.get('db', 'password'))

    cnx.cursor().execute("DROP DATABASE IF EXISTS " + test_project_name)
    cnx.close()

    for directory in [db_root, user_products, user_works, repos]:
        if not os.path.exists(directory):
            continue
        for path, subdirs, files in os.walk(directory):
            for name in files:
                filepath = os.path.join(path, name)
                if filepath.endswith(".pipe"):
                    os.chmod(filepath, 0o777)
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))

    # clean ftp files
    connection = ftplib.FTP()
    connection.connect(config.get('ftp', 'host'), int(config.get('ftp', 'port')))
    connection.login(config.get('ftp', 'login'), config.get('ftp', 'password'))
    connection.cwd(config.get('ftp', 'root'))
    for project in connection.nlst():
        if project.startswith("test"):
            ftp_rmtree(connection, project)
    connection.quit()

    print "FILES RESET"


def create_test_project(prj_name=test_project_name):
    cnx = Connection(db_root)
    prj = cnx.create_project(
        prj_name,
        user_works,
        repository_adapter="ftp",
        repository_url=ftp_url,
        product_user_root=user_products
    )
    return cnx, prj


class TestBasic(unittest.TestCase):
    def setUp(self):
        reset_files()

    def test_multiple_repository_types(self):
        cnx, prj = create_test_project()
        prj.cfg.add_repository("serverB",
                               "file_storage", "file:///" + os.path.join(repos, "default").replace("\\", "/"))

        template_resource = prj.create_resource("_template", "rig", repository="serverB")
        template_work = template_resource.checkout()
        open(template_work.directory + "\\template_work.txt", 'a').close()
        template_work.commit()
        # self.assertTrue(os.path.exists(os.path.join(user_works, "test\\rig\\_template")))
        template_work.trash()
        prj.purge_unused_user_products()
        self.assertFalse(os.path.exists(os.path.join(user_works, test_project_name, "rig\\_template")))
        template_resource.checkout()
        self.assertTrue(os.path.exists(os.path.join(user_works, test_project_name, "rig\\_template")))

        # test moving resource between repo
        self.assertTrue(os.path.exists(os.path.join(repos, "default", test_project_name, "work\\rig\\_template")))
        # TODO : the set_repository method should call a commit from ftp. Check why it does not happen
        template_resource.set_repository("default")

        self.assertFalse(os.path.exists(os.path.join(repos, "default", test_project_name, "work\\rig\\_template")))

        # test commit the resource
        template_resource.set_repository("default")

        # test moving resource between repo when the resource is locked
        template_resource.set_lock(True, "another_user")
        with self.assertRaises(PulseError):
            template_resource.set_repository("serverB")

    def test_sql_db(self):
        cnx = Connection(db_url, "mysql")
        prj = cnx.create_project(
            test_project_name,
            user_works,
            repository_url=os.path.join(repos, "default"),
            product_user_root=user_products
        )

        anna_surf_resource = prj.create_resource("ch_anna", "surfacing")
        anna_surf_work = anna_surf_resource.checkout()
        anna_surf_textures = anna_surf_work.create_product("textures")
        open(anna_surf_textures.directory + "\\product_file.txt", 'a').close()
        anna_surf_work.commit(comment="test generated product")
        anna_rig_resource = prj.create_resource("ch_anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_actor = anna_rig_work.create_product("actor_anim")
        anna_rig_actor.add_input(anna_surf_textures)
        anna_rig_work.commit()
        anna_rig_work.trash()
        anna_surf_work.trash()
        prj.purge_unused_user_products()
        self.assertFalse(os.path.exists(anna_surf_textures.directory))
        anim_resource = prj.create_resource("sh003", "anim")
        anim_work = anim_resource.checkout()
        anim_work.add_input(anna_rig_actor)
        self.assertTrue(os.path.exists(anna_surf_textures.directory))

        self.assertTrue(len(prj.list_products("ch_anna*")) == 2)
        self.assertTrue(len(prj.list_products("ch_an?a*")) == 2)

        # you have to close the connection to allow the database reset by the test
        cnx.db.connection.close()

        cnx2 = Connection(db_url, "mysql")
        prj = cnx2.get_project(test_project_name)
        rig2 = prj.get_resource("ch_anna", "rigging")
        self.assertTrue(rig2.get_commit("last").products[0] == 'actor_anim')

        # you have to close the connection to allow the database reset by the test
        cnx2.db.connection.close()

    def test_work_subdirectories_are_commit(self):
        subdirectory_name = "subdirtest"
        # create a connection
        cnx, prj = create_test_project()
        # create a resource based on this template
        anna_mdl_resource = prj.create_resource("ch_anna", "modeling")
        self.assertEqual(anna_mdl_resource.last_version, 0)

        # checkout, and check directories are created
        anna_mdl_work = anna_mdl_resource.checkout()
        work_subdir_path = os.path.join(anna_mdl_work.directory, subdirectory_name)
        os.makedirs(work_subdir_path)
        open(work_subdir_path + "\\subdir_file.txt", 'a').close()
        anna_mdl_work.commit()
        anna_mdl_work.trash()
        self.assertFalse(os.path.exists(anna_mdl_work.directory))
        anna_mdl_resource.checkout()
        self.assertTrue(os.path.exists(work_subdir_path + "\\subdir_file.txt"))

    def test_delete_project_sql_db(self):
        print db_url
        cnx = Connection(db_url, "mysql")
        prj = cnx.create_project(
            test_project_name,
            user_works,
            repository_url=os.path.join(repos, "default"),
            product_user_root=user_products
        )
        anna_mdl = prj.create_resource("anna", "mdl")
        anna_mdl_work = anna_mdl.checkout()
        anna_mdl_work.create_product("abc")
        anna_mdl_work.commit()
        cnx.delete_project(test_project_name)
        with self.assertRaises(PulseDatabaseMissingObject):
            cnx.get_project(test_project_name)


if __name__ == '__main__':
    unittest.main()
