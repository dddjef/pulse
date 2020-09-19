from pulse.api import *
import unittest
import subprocess


"""
associate .py with the python interpreter.

Use commands ftype and assoc

ftype PythonScript=c:\pathtofolder\python.exe %*

assoc .py=PythonScript
Then add your SCRIPT path to the path command

Setx path "%path%;C:\MyPythonScriptFolder"

Set path="%path%;C:\MyPythonScriptFolder"

Then tell windows command prompt to assume .py files are executable so it will search the path for it.

Set pathext=%pathext%;.py


"""
# TODO : test trashing an open file

test_dir = os.path.dirname(__file__)
db_path = os.path.join(test_dir, "DB")
user_work = os.path.join(test_dir, "works")
user_products = os.path.join(test_dir, "products")
repos = os.path.join(test_dir, "repos")
test_project_name = "cli_project"
cli_project_path = os.path.join(test_dir, "works", test_project_name)

cli_path = r"C:\Users\dddje\PycharmProjects\pulse\cli\cli.py"
python_exe = "c:\\python27\\python.exe"


def reset_files():
    for directory in [db_path, user_products, user_work, repos]:
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
    print "FILES RESET"


def cli_cmd_list(cmd_list):
    cmd = python_exe + " " + cli_path
    for arg in cmd_list:
        cmd += " " + arg
    return subprocess.call(cmd)


class TestBasic(unittest.TestCase):
    def setUp(self):
        reset_files()

    # def tearDown(self):
    #     reset_files()

    def test_create_project(self):
        os.makedirs(cli_project_path)
        os.chdir(cli_project_path)
        repository_url = os.path.join(repos, 'default')
        cli_cmd_list(['create_project', db_path, '--repository_url "' + repository_url + '"', '--silent_mode'])
        # check the project exists in db directory
        self.assertTrue(os.path.exists(os.path.join(db_path, test_project_name)))

        # create a modeling resource
        cli_cmd_list(['create_resource', 'ch_anna-mdl'])

        anna_mdl_path = os.path.join(user_work, test_project_name, 'mdl', 'ch_anna')
        self.assertTrue(os.path.exists(anna_mdl_path))
        os.chdir(anna_mdl_path)

        cli_cmd_list(['create_output', 'abc'])
        anna_abc_path = os.path.join(user_work, test_project_name, 'mdl', 'ch_anna', 'v001', 'abc')
        self.assertTrue(os.path.exists(anna_abc_path))

        # commit work
        cli_cmd_list(['commit'])

        # create a surface resource
        cli_cmd_list(['create_resource', 'ch_anna-surfacing'])
        anna_surfacing_path = os.path.join(user_work, test_project_name, 'surfacing', 'ch_anna')
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
    reset_files()
