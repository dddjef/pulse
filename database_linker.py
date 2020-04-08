import json
import os
import glob
# = "D:\\pipe\\pulse\\test\\DB"


class PulseDatabaseError(Exception):
    def __init__( self, reason ):
        Exception.__init__(self)
        self._reason = reason

    def reason(self):
        return self._reason

    def __str__(self):
        return self._reason


class DB:
    def __init__(self, connexion_data=None):
        if not os.path.exists(connexion_data["DB_root"]):
            raise PulseDatabaseError("can't find the database :" + connexion_data["DB_root"])
        self._root = connexion_data["DB_root"]
        self.data_filename = "data.json"

    def create_project(self, project_name):
        project_directory = os.path.join(self._root, project_name)
        if os.path.exists(project_directory):
            raise PulseDatabaseError("project already exists")
        os.makedirs(project_directory)

    def find_uris(self, project_name, entity_type, uri_pattern):
        uris =[]
        for path in glob.glob(os.path.dirname(self._get_json_filepath(project_name, entity_type, uri_pattern))):
            uris.append(path.split(os.pathsep)[-1])
        return uris

    def get_user_name(self):
        return os.environ.get('USERNAME')

    def _get_json_filepath(self, project_name, entity_type, uri):
        return os.path.join(self._root, project_name, entity_type,  uri, self.data_filename)

    def write(self, project_name, entity_type, uri, data_dict):
        json_filepath = self._get_json_filepath(project_name, entity_type, uri)
        json_folder = os.path.dirname(json_filepath)
        if not os.path.exists(json_folder):
            os.makedirs(json_folder)
        with open(json_filepath, "w") as write_file:
            json.dump(data_dict, write_file, indent=4, sort_keys=True)

    def read(self, project_name, entity_type, uri):
        json_filepath = self._get_json_filepath(project_name, entity_type, uri)
        if not os.path.exists(json_filepath):
            return None
        with open(json_filepath, "r") as read_file:
            data = json.load(read_file)
        return data
