import os
import shutil
import mysql.connector as mysql
import ftplib
from ConfigParser import ConfigParser

test_dir = os.path.dirname(__file__)
json_db_path = os.path.join(test_dir, "DB")
sandbox_work_path = os.path.join(test_dir, "works")
sandbox_products_path = os.path.join(test_dir, "products")
file_repository_path = os.path.join(test_dir, "repos")


ini = ConfigParser()
ini.read(os.path.join(os.path.dirname(os.path.realpath(__file__)), "custom_adapters_config.ini"))
db_url = "mysql://" + ini.get('db', 'login') + ':' + ini.get('db', 'password') \
         + '@' + ini.get('db', 'host') + ':' + ini.get('db', 'port')
ftp_url = 'ftp://' + ini.get('ftp', 'login') + ':' + ini.get('ftp', 'password') \
          + '@' + ini.get('ftp', 'host') + ':' + ini.get('ftp', 'port') + '/' + ini.get('ftp', 'root')


def reset_test_data():
    for directory in [json_db_path, sandbox_work_path, sandbox_products_path, file_repository_path]:
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


def reset_sql_db(project_name):
    cnx = mysql.connect(host=ini.get('db', 'host'), port=ini.get('db', 'port'),
                        user=ini.get('db', 'login'), password=ini.get('db', 'password'))

    cnx.cursor().execute("DROP DATABASE IF EXISTS " + project_name)
    cnx.close()


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


def reset_ftp(project_name):
    connection = ftplib.FTP()
    connection.connect(ini.get('ftp', 'host'), int(ini.get('ftp', 'port')))
    connection.login(ini.get('ftp', 'login'), ini.get('ftp', 'password'))
    connection.cwd(ini.get('ftp', 'root'))
    for project in connection.nlst():
        if project.startswith(project_name):
            ftp_rmtree(connection, project)
    connection.quit()


def add_file_to_directory(directory, filename, source_filepath=None):
    if not source_filepath:
        open(os.path.join(directory, filename), 'a').close()
