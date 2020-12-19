import json
from pulse.database_adapters.interface_class import *
import mysql.connector as mariadb
# This adapter has been checked with mariadb 5


class Database(PulseDatabase):
    def __init__(self, settings):
        PulseDatabase.__init__(self, settings)
        self.connection = None
        self.config_name = "_Config"
        self.cursor = None
        self.update_connection()

    def update_connection(self):
        self.connection = mariadb.connect(
            host=self.settings['host'],
            port=self.settings['port'],
            user=self.settings['username'],
            password=self.settings['password']
        )
        self.cursor = self.connection.cursor()

    def create_repository(self, name, adapter, login, password, settings):
        data = {
            "name": name,
            "adapter": adapter,
            "login": login,
            "password": password,
            "settings": json.dumps(settings)
        }
        self.cursor.execute("USE " + self.config_name)
        placeholders = ', '.join(['%s'] * len(data))
        columns = ', '.join(data.keys())
        cmd = "INSERT INTO %s ( %s ) VALUES ( %s )" % ("Repository", columns, placeholders)

        try:
            self.cursor.execute(cmd, data.values())
        except mariadb.IntegrityError:
            raise PulseDatabaseError("node already exists:" + name)
        self.connection.commit()

    def get_repositories(self):
        # set config db if does not exists yet
        try:
            self.cursor.execute("USE " + self.config_name)
        except mariadb.errors.DatabaseError:
            self.cursor.execute("CREATE DATABASE " + self.config_name)
            self.cursor.execute("USE " + self.config_name)
            for table in self.config_tables:
                cmd = "CREATE TABLE " + table + " (name VARCHAR(255) PRIMARY KEY"
                for field in self.config_tables[table]:
                    cmd += ", " + field
                cmd += ")"
                self.cursor.execute(cmd)
            self.connection.commit()
            return {}
        self.cursor.execute("SELECT * FROM Repository")
        table = [self.cursor.fetchall()][0]
        repositories_dict = {}
        for row in table:
            repositories_dict[row[0]] = {}
            repositories_dict[row[0]]["adapter"] = row[1]
            repositories_dict[row[0]]["login"] = row[2]
            repositories_dict[row[0]]["password"] = row[3]
            repositories_dict[row[0]]["settings"] = json.loads(row[4])
        return repositories_dict

    def create_project(self, project_name):
        if project_name == self.config_name:
            raise PulseDatabaseError("project name reserved by config : " + project_name)
        # test if the projects table exists
        try:
            self.cursor.execute("CREATE DATABASE " + project_name)
        except mariadb.errors.DatabaseError:
            raise PulseDatabaseError("project already exists : " + project_name)

        self.cursor.execute("USE " + project_name)

        # save the adapter version
        cmd = "CREATE TABLE version (number VARCHAR(255) NOT NULL)"
        self.cursor.execute(cmd)
        self.cursor.execute("INSERT into version (number) VALUE ('" + self.adapter_version + "')")
        self.connection.commit()
        for table in self.project_tables:
            # id int(11) NOT NULL AUTO_INCREMENT,
            cmd = "CREATE TABLE " + table + " (uri VARCHAR(255) PRIMARY KEY"
            for field in self.project_tables[table]:
                cmd += ", " + field
            cmd += ")"
            self.cursor.execute(cmd)

    def delete_project(self, project_name):
        self.cursor.execute("DROP DATABASE IF EXISTS " + project_name)

    def find_uris(self, project_name, entity_type, uri_pattern):
        self.cursor.execute("USE " + project_name)
        param = '{}%'.format(uri_pattern.replace("*", "%").replace("_", "\\_").replace("?", "_"))
        cmd = "SELECT uri FROM " + entity_type + " WHERE uri LIKE %s"
        self.cursor.execute(cmd, (param,))
        return [x[0] for x in self.cursor.fetchall()]

    def get_user_name(self):
        return self.settings["username"]

    def create(self, project_name, entity_type, uri, data):
        self.cursor.execute("USE " + project_name)

        for k in data:
            if isinstance(data[k], dict) or isinstance(data[k], list):
                data[k] = json.dumps(data[k])

        data['uri'] = uri
        placeholders = ', '.join(['%s'] * len(data))
        columns = ', '.join(data.keys())
        cmd = "INSERT INTO %s ( %s ) VALUES ( %s )" % (entity_type, columns, placeholders)
        # valid in Python 2
        try:
            self.cursor.execute(cmd, data.values())
        except mariadb.IntegrityError:
            raise PulseDatabaseError("node already exists:" + uri)
        self.connection.commit()

    def update(self, project_name, entity_type, uri, data):
        self.cursor.execute("USE " + project_name)
        for k in data:
            if isinstance(data[k], dict) or isinstance(data[k], list):
                data[k] = json.dumps(data[k])

        cmd = 'UPDATE ' + entity_type + ' SET {}'.format(', '.join('{}=%s'.format(k) for k in data))
        cmd += " WHERE uri = '" + uri + "'"
        self.cursor.execute(cmd, data.values())
        self.connection.commit()

    def read(self, project_name, entity_type, uri):
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute("USE " + project_name)
        except mariadb.ProgrammingError:
            raise PulseDatabaseMissingObject("missing project :" + project_name)

        cursor.execute("SELECT * FROM " + entity_type + " WHERE uri = '" + uri + "'")
        data = cursor.fetchone()
        if not data:
            raise PulseDatabaseMissingObject("no data for : " + project_name + ", " + entity_type + ", " + uri)

        for k in data:
            for attr in self.project_tables[entity_type]:
                if attr == k + " LONGTEXT":
                    data[k] = json.loads(data[k])
        return data
