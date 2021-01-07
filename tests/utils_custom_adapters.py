import mysql.connector as mysql
import ftplib
import os
from ConfigParser import ConfigParser


ini = ConfigParser()
ini.read(os.path.join(os.path.dirname(os.path.realpath(__file__)), "custom_adapters_config.ini"))
mysql_settings = {
    "username": ini.get('mysql', 'username'),
    'password': ini.get('mysql', 'password'),
    'host': ini.get('mysql', 'host'),
    'port': ini.get('mysql', 'port')}

ftp_login = ini.get('ftp', 'login')
ftp_password = ini.get('ftp', 'password')
ftp_settings = {
    "host": ini.get('ftp', 'host'),
    "port": int(ini.get('ftp', 'port')),
    "root": ini.get('ftp', 'root')}


def reset_sql_db(project_name):
    cnx = mysql.connect(host=ini.get('mysql', 'host'), port=ini.get('mysql', 'port'),
                        user=ini.get('mysql', 'username'), password=ini.get('mysql', 'password'))

    cnx.cursor().execute("DROP DATABASE IF EXISTS " + project_name)
    cnx.cursor().execute("DROP DATABASE IF EXISTS _Config")
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
