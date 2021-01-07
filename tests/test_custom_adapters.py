from pulse.api import *
import unittest
import os
import utils
import utils_custom_adapters as utils_ca
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


class TestFTP(unittest.TestCase):
    def setUp(self):
        utils.reset_test_data()
        utils_ca.reset_ftp(test_project_name)
        self.cnx = Connection(adapter="json_db", path=utils.json_db_path)
        self.cnx.add_repository(
            name="ftp_storage",
            adapter="ftp",
            login=utils_ca.ftp_login,
            password=utils_ca.ftp_password,
            host=utils_ca.ftp_settings["host"],
            port=utils_ca.ftp_settings["port"],
            root=utils_ca.ftp_settings["root"]
            )
        self.prj = self.cnx.create_project(
            test_project_name,
            utils.sandbox_work_path,
            default_repository="ftp_storage",
            product_user_root=utils.sandbox_products_path
        )

    def test_multiple_repository_types(self):
        local_repo_name = "local_test_storage"
        self.cnx.add_repository(
            name=local_repo_name,
            adapter="file_storage",
            path=os.path.join(utils.file_storage_path, local_repo_name)
        )

        template_resource = self.prj.create_resource("_template", "rig", repository="local_test_storage")
        template_work = template_resource.checkout()
        utils.add_file_to_directory(template_work.directory, "template_work.txt")
        template_work.commit()
        # self.assertTrue(os.path.exists(os.path.join(user_works, "test\\rig\\_template")))
        template_work.trash()
        self.prj.purge_unused_user_products()
        self.assertFalse(os.path.exists( os.path.join(utils.sandbox_work_path, test_project_name, "rig", "_template")))
        template_resource.checkout()
        self.assertTrue(os.path.exists(os.path.join(utils.sandbox_work_path, test_project_name, "rig", "_template")))

        # test moving resource between repo
        self.assertTrue(os.path.exists(os.path.join(utils.file_storage_path, local_repo_name,
                                                    test_project_name, "work", "rig", "_template")))

        template_resource.set_repository(self.prj.cfg.default_repository)

        self.assertFalse(os.path.exists(os.path.join(utils.file_storage_path, local_repo_name,
                                                     test_project_name, "work", "rig","_template")))

        # test commit the resource
        utils.add_file_to_directory(template_work.directory)
        template_work.commit()

        # test moving resource between repo when the resource is locked
        template_resource.set_lock(True, "another_user")
        with self.assertRaises(PulseError):
            template_resource.set_repository("serverB")

    def test_work_subdirectories_are_commit(self):
        subdirectory_name = "subdirtest"
        # create a resource based on this template
        anna_mdl_resource = self.prj.create_resource("ch_anna", "modeling")
        self.assertEqual(anna_mdl_resource.last_version, 0)

        # checkout, and check directories are created
        anna_mdl_work = anna_mdl_resource.checkout()
        work_subdir_path = os.path.join(anna_mdl_work.directory, subdirectory_name)
        os.makedirs(work_subdir_path)
        utils.add_file_to_directory(work_subdir_path, "subdir_file.txt")
        anna_mdl_work.commit()
        anna_mdl_work.trash()
        self.assertFalse(os.path.exists(anna_mdl_work.directory))
        anna_mdl_resource.checkout()
        self.assertTrue(os.path.exists(os.path.join(work_subdir_path, "subdir_file.txt")))


class TestSQL(unittest.TestCase):
    def setUp(self):
        utils.reset_test_data()
        utils_ca.reset_sql_db(test_project_name)
        self.cnx = Connection(
            adapter="mysql",
            host=utils_ca.mysql_settings['host'],
            username=utils_ca.mysql_settings['username'],
            password=utils_ca.mysql_settings['password'],
            port=utils_ca.mysql_settings['port']
        )

        local_repo_name = "local_test_storage"
        self.cnx.add_repository(
            name=local_repo_name,
            adapter="file_storage",
            path=os.path.join(utils.file_storage_path, local_repo_name)
        )

        self.prj = self.cnx.create_project(
            test_project_name,
            utils.sandbox_work_path,
            default_repository="local_test_storage",
            product_user_root=utils.sandbox_products_path
        )

    def test_sql_db(self):
        anna_surf_resource = self.prj.create_resource("ch_anna", "surfacing")
        anna_surf_work = anna_surf_resource.checkout()
        anna_surf_textures = anna_surf_work.create_product("textures")
        utils.add_file_to_directory(anna_surf_textures.directory, "product_file.txt")
        anna_surf_work.commit(comment="test generated product")
        anna_rig_resource = self.prj.create_resource("ch_anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_actor = anna_rig_work.create_product("actor_anim")
        anna_rig_actor.add_input(anna_surf_textures)
        anna_rig_work.commit()
        anna_rig_work.trash()
        anna_surf_work.trash()
        self.prj.purge_unused_user_products()
        self.assertFalse(os.path.exists(anna_surf_textures.directory))
        anim_resource = self.prj.create_resource("sh003", "anim")
        anim_work = anim_resource.checkout()
        anim_work.add_input(anna_rig_actor)
        self.assertTrue(os.path.exists(anna_surf_textures.directory))

        self.assertTrue(len(self.prj.list_products("ch_anna*")) == 2)
        self.assertTrue(len(self.prj.list_products("ch_an?a*")) == 2)

        # you have to close the connection to allow the database reset by the test
        self.cnx.db.connection.close()

        cnx2 = Connection(
            adapter="mysql",
            host=utils_ca.mysql_settings['host'],
            username=utils_ca.mysql_settings['username'],
            password=utils_ca.mysql_settings['password'],
            port=utils_ca.mysql_settings['port']
        )
        prj = cnx2.get_project(test_project_name)
        rig2 = prj.get_resource("ch_anna", "rigging")
        self.assertTrue(rig2.get_commit("last").products[0] == 'actor_anim')

        # you have to close the connection to allow the database reset by the test
        cnx2.db.connection.close()

    def test_delete_project_sql_db(self):
        anna_mdl = self.prj.create_resource("anna", "mdl")
        anna_mdl_work = anna_mdl.checkout()
        anna_mdl_work.create_product("abc")
        utils.add_file_to_directory(anna_mdl_work.directory)
        anna_mdl_work.commit()
        self.cnx.delete_project(test_project_name)
        with self.assertRaises(PulseDatabaseMissingObject):
            self.cnx.get_project(test_project_name)


if __name__ == '__main__':
    unittest.main()
