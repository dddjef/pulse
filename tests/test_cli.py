import unittest
import subprocess
import config as cfg
from pulse.api import *

"""
associate .py with the python interpreter.

Use commands ftype and assoc

ftype PythonScript=c:/pathtofolder/python.exe %*

assoc .py=PythonScript
Then add your SCRIPT path to the path command

Setx path "%path%;C:/MyPythonScriptFolder"

Set path="%path%;C:/MyPythonScriptFolder"

Then tell windows command prompt to assume .py files are executable so it will search the path for it.

Set pathext=%pathext%;.py


"""

test_project_name = "cli_project"
cli_project_path = os.path.join(cfg.sandbox_work_path, test_project_name)
cli_path = r"C:\Users\dddje\PycharmProjects\pulse\cli\pls.py"
python_exe = "c:\\python27\\python.exe"


def cli_cmd_list(cmd_list):
    cmd = python_exe + " " + cli_path
    for arg in cmd_list:
        cmd += " " + arg
    return subprocess.call(cmd)


class TestDefaultAdapters(unittest.TestCase):
    def setUp(self):
        cfg.reset_test_data()
        if not os.path.exists(cli_project_path):
            os.makedirs(cli_project_path)
        os.chdir(cli_project_path)

        # project and repository management are not supported via CLI. use api here
        self.cnx = Connection(adapter="json_db", path=cfg.json_db_path)
        self.cnx.add_repository(name="local_test_storage", adapter="file_storage", path=cfg.file_storage_path)
        self.prj = self.cnx.create_project(
            test_project_name,
            cfg.sandbox_work_path,
            default_repository="local_test_storage",
            product_user_root=cfg.sandbox_products_path
        )

    def test_scenario(self):
        # register to project with user login
        cli_cmd_list([
            'get_project',
            test_project_name,
            "--adapter json_db",
            '--settings "' + cfg.json_db_path + '"'
        ])
        
        # create a modeling resource
        cli_cmd_list(['create_resource', 'ch_anna:mdl'])

        anna_mdl_path = os.path.join(cfg.sandbox_work_path, test_project_name, 'mdl', 'ch_anna')
        self.assertTrue(os.path.exists(anna_mdl_path))
        os.chdir(anna_mdl_path)

        cli_cmd_list(['create_output', 'abc'])
        anna_abc_path = os.path.join(cfg.sandbox_products_path, test_project_name, 'mdl', 'ch_anna', 'v001', 'abc')
        self.assertTrue(os.path.exists(anna_abc_path))

        # commit work
        cfg.add_file_to_directory(anna_mdl_path)
        cli_cmd_list(['commit'])

        # create a surface resource
        cli_cmd_list(['create_resource', 'ch_anna:surfacing'])
        anna_surfacing_path = os.path.join(cfg.sandbox_work_path, test_project_name, 'surfacing', 'ch_anna')
        os.chdir(anna_surfacing_path)

        # add mdl as input and commit
        cli_cmd_list(['add_input', 'ch_anna:mdl-abc@1'])
        cfg.add_file_to_directory(anna_surfacing_path)
        cli_cmd_list(['commit'])

        # trash works
        # but first move out from the work directory, unless the directory won't move
        os.chdir(cli_project_path)
        cli_cmd_list(['trash', 'ch_anna:surfacing'])
        self.assertFalse(os.path.exists(anna_surfacing_path))
        cli_cmd_list(['trash', 'ch_anna:mdl'])
        self.assertFalse(os.path.exists(anna_mdl_path))

        # now try to check out the surface and check the mdl is restored too
        cli_cmd_list(['checkout', 'ch_anna:surfacing'])
        self.assertTrue(os.path.exists(anna_abc_path))

        # lock surfacing by another user (easier to simulate with with API)
        anna_surfacing_resource = self.prj.get_resource("ch_anna", "surfacing")
        anna_surfacing_resource.set_lock(True, user="Joe")

        # try to commit changes, and ensure there's a dedicated message for this error
        cfg.add_file_to_directory(anna_surfacing_path, "a_work_file.txt")
        os.chdir(anna_surfacing_path)
        cli_cmd_list(['commit'])


class TestCustomAdapters(unittest.TestCase):
    def setUp(self):
        cfg.reset_test_data()
        cfg.reset_sql_db(test_project_name)
        cfg.reset_ftp(test_project_name)

        if not os.path.exists(cli_project_path):
            os.makedirs(cli_project_path)
        os.chdir(cli_project_path)

        self.cnx = Connection(
            adapter="mysql",
            host=cfg.mysql_settings['host'],
            username=cfg.mysql_settings['username'],
            password=cfg.mysql_settings['password'],
            port=cfg.mysql_settings['port']
        )

        self.cnx.add_repository(
            name="ftp_storage",
            adapter="ftp",
            login=cfg.ftp_login,
            password=cfg.ftp_password,
            host=cfg.ftp_settings["host"],
            port=cfg.ftp_settings["port"],
            root=cfg.ftp_settings["root"]
            )

        self.prj = self.cnx.create_project(
            test_project_name,
            cfg.sandbox_work_path,
            default_repository="ftp_storage",
            product_user_root=cfg.sandbox_products_path
        )

        self.db_url = "mysql://" + cfg.mysql_settings["username"] + ':' + cfg.mysql_settings["password"] +\
                      '@' + cfg.mysql_settings["host"] + ':' + cfg.mysql_settings["port"]

    def test_scenario(self):
        # register to project with user login
        cli_cmd_list(['get_project', test_project_name, "--adapter mysql", '--settings "' + self.db_url + '"'])

        # create a modeling resource
        cli_cmd_list(['create_resource', 'ch_anna:mdl'])

        anna_mdl_path = os.path.join(cfg.sandbox_work_path, test_project_name, 'mdl', 'ch_anna')
        self.assertTrue(os.path.exists(anna_mdl_path))
        os.chdir(anna_mdl_path)

        cli_cmd_list(['create_output', 'abc'])
        anna_abc_path = os.path.join(cfg.sandbox_products_path, test_project_name, 'mdl', 'ch_anna', 'v001', 'abc')
        self.assertTrue(os.path.exists(anna_abc_path))

        # commit work
        cfg.add_file_to_directory(anna_abc_path)
        cli_cmd_list(['commit'])

        # create a surface resource
        cli_cmd_list(['create_resource', 'ch_anna:surfacing'])
        anna_surfacing_path = os.path.join(cfg.sandbox_work_path, test_project_name, 'surfacing', 'ch_anna')
        os.chdir(anna_surfacing_path)

        # add mdl as input and commit
        cli_cmd_list(['add_input', 'ch_anna:mdl-abc@1'])
        cfg.add_file_to_directory(anna_surfacing_path)
        cli_cmd_list(['commit'])

        # trash works
        # but first move out from the work directory, unless the directory won't move
        os.chdir(cli_project_path)
        cli_cmd_list(['trash', 'ch_anna:surfacing'])
        self.assertFalse(os.path.exists(anna_surfacing_path))
        cli_cmd_list(['trash', 'ch_anna:mdl'])
        self.assertFalse(os.path.exists(anna_mdl_path))

        # now try to check out the surface and check the mdl is restored too
        cli_cmd_list(['checkout', 'ch_anna:surfacing'])
        self.assertTrue(os.path.exists(anna_abc_path))




if __name__ == '__main__':
    unittest.main()
