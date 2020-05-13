import json
from pulse.database_adapters.interface_class import *
import mysql.connector as mariadb
# This adapter has been checked with mariadb 5


class Database(PulseDatabase):
    def __init__(self, connexion_data):
        self.host = connexion_data['host']
        self.port = connexion_data['port']
        self.user = connexion_data['user']
        self.password = connexion_data['password']
        self.db = None
        self.cursor = None
        self.update_connection()
        PulseDatabase.__init__(self)

    def update_connection(self):
        self.db = mariadb.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
        )
        self.cursor = self.db.cursor()

    def create_project(self, project_name):
        # test if the projects table exists
        try:
            self.cursor.execute("CREATE DATABASE " + project_name)
        except mariadb.errors.DatabaseError:
            raise PulseDatabaseError("project already exists")

        # TODO : save the adapter version
        self.cursor.execute("USE " + project_name)

        for table in self.tables_definition:
            # id int(11) NOT NULL AUTO_INCREMENT,
            cmd = "CREATE TABLE " + table + " (uri VARCHAR(255) PRIMARY KEY"
            for field in self.tables_definition[table]:
                cmd += ", " + field
            cmd += ")"
            self.cursor.execute(cmd)

    # TODO : adapt this
    def find_uris(self, project_name, entity_type, uri_pattern):
        pass
        # uris = []
        # for path in glob.glob(self._get_json_filepath(project_name, entity_type, uri_pattern)):
        #     uris.append(os.path.splitext(os.path.basename(path))[0])
        # return uris

    def get_user_name(self):
        return self.user

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
        self.db.commit()

    def update(self, project_name, entity_type, uri, data):
        self.cursor.execute("USE " + project_name)
        for k in data:
            if isinstance(data[k], dict) or isinstance(data[k], list):
                data[k] = json.dumps(data[k])

        cmd = 'UPDATE ' + entity_type + ' SET {}'.format(', '.join('{}=%s'.format(k) for k in data))
        cmd += " WHERE uri = '" + uri + "'"
        self.cursor.execute(cmd, data.values())
        self.db.commit()

    def read(self, project_name, entity_type, uri):
        cursor = self.db.cursor(dictionary=True)
        cursor.execute("USE " + project_name)
        cursor.execute("SELECT * FROM " + entity_type + " WHERE uri = '" + uri + "'")
        data = cursor.fetchone()
        if not data:
            raise PulseDatabaseMissingObject("no data for : " + project_name + ", " + entity_type + ", " + uri)

        for k in data:
            for attr in self.tables_definition[entity_type]:
                if attr == k + " LONGTEXT":
                    data[k] = json.loads(data[k])
        return data
