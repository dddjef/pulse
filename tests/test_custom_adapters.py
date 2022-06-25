from pulse.api import *
import unittest
import os
import utils
import utils_custom_adapters as utils_ca
import test as standard_test
test_project_name = "test"

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


class TestResourcesFTP(standard_test.TestResources):
    def setUp(self):
        utils.reset_test_data()
        utils_ca.reset_ftp(test_project_name)
        self.cnx = Connection(adapter="json_db", path=utils.json_db_path)
        self.cnx.add_repository(
            name="main_storage",
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
            default_repository="main_storage",
            product_user_root=utils.sandbox_products_path
        )
        self._initResource()


class TestResourcesSQL(standard_test.TestResources):
    def setUp(self):
        utils.reset_test_data()
        utils_ca.reset_sql_db(test_project_name)
        self.cnx = Connection(
            adapter="mysql",
            path=utils_ca.mysql_settings['host'],
            username=utils_ca.mysql_settings['username'],
            password=utils_ca.mysql_settings['password'],
            port=utils_ca.mysql_settings['port']
        )
        self.cnx.add_repository(name="main_storage", adapter="file_storage", path=utils.file_storage_path)
        self.prj = self.cnx.create_project(
            test_project_name,
            utils.sandbox_work_path,
            default_repository="main_storage",
            product_user_root=utils.sandbox_products_path
        )
        self._initResource()

    def test_get_project_from_path(self):
        project = get_project_from_path(
            self.anna_mdl_work.directory,
            username=utils_ca.mysql_settings['username'],
            password=utils_ca.mysql_settings['password']
        )
        self.assertEqual(project.list_works(), ['anna-mdl'])
        project.cnx.db.connection.close()

    def tearDown(self):
        self.cnx.db.connection.close()


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
            path=os.path.join(utils.file_storage_path, local_repo_name).replace("\\", "/")
        )

        template_resource = self.prj.create_resource("_template", "rig", repository="local_test_storage")
        template_work = template_resource.checkout()
        utils.add_file_to_directory(template_work.directory, "template_work.txt")
        template_work.publish()
        # self.assertTrue(os.path.exists(os.path.join(user_works, "test\\rig\\_template")))
        template_work.trash()
        self.prj.purge_unused_user_products()
        self.assertFalse(os.path.exists(os.path.join(utils.sandbox_work_path, test_project_name, "_template-rig")))
        template_resource.checkout()
        self.assertTrue(os.path.exists(os.path.join(utils.sandbox_work_path, test_project_name, "_template-rig")))

        # test moving resource between repo
        self.assertTrue(os.path.exists(os.path.join(utils.file_storage_path, local_repo_name,
                                                    test_project_name, "work", "rig", "_template")))

        template_resource.set_repository(self.prj.cfg.default_repository)

        self.assertFalse(os.path.exists(os.path.join(utils.file_storage_path, local_repo_name,
                                                     test_project_name, "work", "rig", "_template")))

        # test commit the resource
        utils.add_file_to_directory(template_work.directory)
        template_work.publish()

        # test moving resource between repo when the resource is locked
        template_resource.set_lock(True, "another_user")
        with self.assertRaises(PulseError):
            template_resource.set_repository("serverB")


if __name__ == '__main__':
    unittest.main()
