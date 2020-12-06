import unittest
import subprocess
import os
import config as cfg

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


class TestBasic(unittest.TestCase):
    def setUp(self):
        cfg.reset_test_data()

    def test_create_project(self):
        if not os.path.exists(cli_project_path):
            os.makedirs(cli_project_path)
        os.chdir(cli_project_path)
        repository_url = os.path.join(cfg.file_repository_path, 'default')
        cli_cmd_list(['create_project', cfg.json_db_path, '--repository_url "' + repository_url + '"', '--silent_mode'])
        # check the project exists in db directory
        self.assertTrue(os.path.exists(os.path.join(cfg.json_db_path, test_project_name)))

        # register to project with user login
        cli_cmd_list(['get_project', cfg.json_db_path])
        
        # create a modeling resource
        cli_cmd_list(['create_resource', 'ch_anna-mdl'])

        anna_mdl_path = os.path.join(cfg.sandbox_work_path, test_project_name, 'mdl', 'ch_anna')
        self.assertTrue(os.path.exists(anna_mdl_path))
        os.chdir(anna_mdl_path)

        cli_cmd_list(['create_output', 'abc'])
        anna_abc_path = os.path.join(cfg.sandbox_work_path, test_project_name, 'mdl', 'ch_anna', 'v001', 'abc')
        self.assertTrue(os.path.exists(anna_abc_path))

        # commit work
        cli_cmd_list(['commit'])

        # create a surface resource
        cli_cmd_list(['create_resource', 'ch_anna-surfacing'])
        anna_surfacing_path = os.path.join(cfg.sandbox_work_path, test_project_name, 'surfacing', 'ch_anna')
        os.chdir(anna_surfacing_path)

        # add mdl as input and commit
        cli_cmd_list(['add_input', 'ch_anna-mdl-abc@1'])
        cli_cmd_list(['commit'])

        # trash works
        # but first move out from the work directory, unless the directory won't move
        os.chdir(cli_project_path)
        cli_cmd_list(['trash', 'ch_anna-surfacing'])
        self.assertFalse(os.path.exists(anna_surfacing_path))
        cli_cmd_list(['trash', 'ch_anna-mdl'])
        self.assertFalse(os.path.exists(anna_mdl_path))

        # now try to check out the surface and check the mdl is restored too
        cli_cmd_list(['checkout', 'ch_anna-surfacing'])
        self.assertTrue(os.path.exists(anna_mdl_path))


class TestCustomAdapters(unittest.TestCase):
    def setUp(self):
        cfg.reset_test_data()
        cfg.reset_sql_db(test_project_name)
        cfg.reset_ftp(test_project_name)

    def test_create_project(self):
        if not os.path.exists(cli_project_path):
            os.makedirs(cli_project_path)
        os.chdir(cli_project_path)
        # create the project with db admin login (needs permission to create a new database)
        cli_cmd_list(['create_project', cfg.db_url, '--repository_url "' + cfg.ftp_url + '"',
                      "--repository_type ftp",  "--database_type mysql", '--silent_mode'])

        cli_cmd_list(['get_project', cfg.db_url, "--database_type mysql"])

        # create a modeling resource
        cli_cmd_list(['create_resource', 'ch_anna-mdl'])

        anna_mdl_path = os.path.join(cfg.sandbox_work_path, test_project_name, 'mdl', 'ch_anna')
        self.assertTrue(os.path.exists(anna_mdl_path))
        os.chdir(anna_mdl_path)

        cli_cmd_list(['create_output', 'abc'])
        anna_abc_path = os.path.join(cfg.sandbox_work_path, test_project_name, 'mdl', 'ch_anna', 'v001', 'abc')
        self.assertTrue(os.path.exists(anna_abc_path))

        # commit work
        cli_cmd_list(['commit'])

        # create a surface resource
        cli_cmd_list(['create_resource', 'ch_anna-surfacing'])
        anna_surfacing_path = os.path.join(cfg.sandbox_work_path, test_project_name, 'surfacing', 'ch_anna')
        os.chdir(anna_surfacing_path)

        # add mdl as input and commit
        cli_cmd_list(['add_input', 'ch_anna-mdl-abc@1'])
        cli_cmd_list(['commit'])

        # trash works
        # but first move out from the work directory, unless the directory won't move
        os.chdir(cli_project_path)
        cli_cmd_list(['trash', 'ch_anna-surfacing'])
        self.assertFalse(os.path.exists(anna_surfacing_path))
        cli_cmd_list(['trash', 'ch_anna-mdl'])
        self.assertFalse(os.path.exists(anna_mdl_path))

        # now try to check out the surface and check the mdl is restored too
        cli_cmd_list(['checkout', 'ch_anna-surfacing'])
        self.assertTrue(os.path.exists(anna_mdl_path))


if __name__ == '__main__':
    unittest.main()
    # reset_files()
