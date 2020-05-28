from pulse.api import *
import unittest
import os
import mysql.connector as mariadb
import ftplib

test_dir = os.path.dirname(__file__)
db = os.path.join(test_dir, "DB")
user_works = os.path.join(test_dir, "works")
user_products = os.path.join(test_dir, "products")
repos = os.path.join(test_dir, "repos")
test_project_name = "testProj"


# you have to set this a mysql database first, pulse user needs rights to create and drop database
db_host = "192.168.1.2"
db_port = "3306"
db_user = "pulse"
db_password = "ijifd_-ygy"

# you have to set this to a ftp server. pulseTest should be able to write to the ftp_root
ftp_host = "192.168.1.2"
ftp_port = 21
ftp_login = "pulseTest"
ftp_password = "okds-ki_se*84877sEE"
ftp_root = "/pulseTest/"


def ftp_rmtree(ftp, path):
    """Recursively delete a directory tree on a remote server."""

    wd = ftp.pwd()

    try:
        names = ftp.nlst(path)
    except ftplib.all_errors as e:
        return

    for name in names:
        if os.path.split(name)[1] in ('.', '..'):
            continue
        try:
            ftp.cwd(name)  # if we can cwd to it, it's a folder
            ftp.cwd(wd)  # don't try a nuke a folder we're in
            ftp_rmtree(ftp, name)
        except ftplib.all_errors:
            ftp.delete(name)
    try:
        ftp.rmd(path)
    except ftplib.all_errors as e:
        print('FtpRmTree: Could not remove {0}: {1}'.format(path, e))


def reset_files():

    cnx = mariadb.connect(host=db_host, port=db_port, user=db_user, password=db_password)
    cnx.cursor().execute("DROP DATABASE IF EXISTS " + test_project_name)
    cnx.close()

    for directory in [db, user_products, user_works, repos]:
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
    connection.connect(ftp_host, ftp_port)
    connection.login(ftp_login, ftp_password)
    connection.cwd(ftp_root)
    for project in connection.nlst():
        if project.startswith("test"):
            ftp_rmtree(connection, project)
    # connection.close()
    connection.quit()

    print "FILES RESET"


def create_test_project(prj_name=test_project_name):
    cnx = Connection({"DB_root": db})
    prj = cnx.create_project(
        prj_name,
        user_works,
        user_products,
        default_repository_type="ftp_repo",
        default_repository_parameters={
            'host': ftp_host,
            'port': ftp_port,
            'login': ftp_login,
            'password': ftp_password,
            'root': ftp_root
        }
    )
    return cnx, prj



class TestBasic(unittest.TestCase):
    def setUp(self):
        reset_files()

    def test_multiple_repository_types(self):
        cnx, prj = create_test_project()
        prj.cfg.add_repository("serverB", "shell_repo", {
            'root': os.path.join(repos, "default")
        })

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
        template_resource.set_repository("default")

        self.assertFalse(os.path.exists(os.path.join(repos, "default", test_project_name, "work\\rig\\_template")))
        # test moving resource between repo when the resource is locked
        template_resource.set_lock(True, "another_user")
        with self.assertRaises(PulseError):
            template_resource.set_repository("serverB")

    def test_sql_db(self):
        cnx = Connection({
            'host': db_host,
            'port': db_port,
            'user': db_user,
            'password': db_password
        }, database_type="mysql_db")
        prj = cnx.create_project(
            test_project_name,
            user_works,
            user_products,
            default_repository_parameters={"root": os.path.join(repos, "default")}
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
        cnx.db.connection.close()

        cnx2 = Connection({
            'host': db_host,
            'port': db_port,
            'user': db_user,
            'password': db_password
        }, database_type="mysql_db")
        prj = cnx2.get_project(test_project_name)
        rig2 = prj.get_resource("ch_anna", "rigging")
        self.assertTrue(rig2.get_commit("last").products[0] == 'actor_anim')
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

if __name__ == '__main__':
    unittest.main()
    reset_files()
