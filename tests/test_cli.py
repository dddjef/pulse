import unittest
import subprocess
import os
import shutil
from ConfigParser import ConfigParser
import mysql.connector as mariadb
import ftplib

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

test_dir = os.path.dirname(__file__)
jsonDB_path = os.path.join(test_dir, "DB")
user_work = os.path.join(test_dir, "works")
user_products = os.path.join(test_dir, "products")
local_file_repository = os.path.join(test_dir, "repos")
test_project_name = "cli_project"
cli_project_path = os.path.join(test_dir, "works", test_project_name)

cli_path = r"C:\Users\dddje\PycharmProjects\pulse\cli\pls.py"
python_exe = "c:\\python27\\python.exe"


config = ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.realpath(__file__)), "custom_adapters_config.ini"))
mysql_url = "mysql://" + config.get('db', 'login') + ':' + config.get('db', 'password')\
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


def reset_custom_adapters_data():
    cnx = mariadb.connect(host=config.get('db', 'host'), port=config.get('db', 'port'),
                          user=config.get('db', 'login'), password=config.get('db', 'password'))

    cnx.cursor().execute("DROP DATABASE IF EXISTS " + test_project_name)
    cnx.close()

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
    

def clean_directory(directory):
    if not os.path.exists(directory):
        return
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


def reset_sandbox():
    for directory in [user_products, user_work]:
        clean_directory(directory)


def cli_cmd_list(cmd_list):
    cmd = python_exe + " " + cli_path
    for arg in cmd_list:
        cmd += " " + arg
    return subprocess.call(cmd)


class TestBasic(unittest.TestCase):
    def setUp(self):
        # database and ftp reset
        clean_directory(jsonDB_path)
        clean_directory(local_file_repository)
        clean_directory(user_products)
        clean_directory(user_work)

    def test_create_project(self):
        os.makedirs(cli_project_path)
        os.chdir(cli_project_path)
        repository_url = os.path.join(local_file_repository, 'default')
        cli_cmd_list(['create_project', jsonDB_path, '--repository_url "' + repository_url + '"', '--silent_mode'])
        # check the project exists in db directory
        self.assertTrue(os.path.exists(os.path.join(jsonDB_path, test_project_name)))

        # register to project with user login
        cli_cmd_list(['get_project', jsonDB_path])
        
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


class TestCustomAdapters(unittest.TestCase):
    def setUp(self):
        reset_custom_adapters_data()
        clean_directory(user_products)
        clean_directory(user_work)

    def test_create_project(self):
        os.makedirs(cli_project_path)
        os.chdir(cli_project_path)
        repository_url = os.path.join(local_file_repository, 'default')
        # create the project with db admin login (needs permission to create a new database)
        cli_cmd_list(['create_project', mysql_url, '--repository_url "' + ftp_url + '"', "--database_type mysql", '--silent_mode'])

        cli_cmd_list(['get_project', mysql_url, "--database_type mysql"])

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
    # reset_files()
