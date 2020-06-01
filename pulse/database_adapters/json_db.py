import json
import os
import glob
from pulse.database_adapters.interface_class import *


class Database(PulseDatabase):
    def __init__(self, url):
        PulseDatabase.__init__(self, url)
        if not os.path.exists(self.url.path):
            raise PulseDatabaseError("can't find json database :" + self.url.path)
        self._root = self.url.path


    def create_project(self, project_name):
        project_directory = os.path.join(self._root, project_name)
        if os.path.exists(project_directory):
            raise PulseDatabaseError("project already exists")
        os.makedirs(project_directory)

    def find_uris(self, project_name, entity_type, uri_pattern):
        uris = []
        for path in glob.glob(self._get_json_filepath(project_name, entity_type, uri_pattern)):
            uris.append(os.path.splitext(os.path.basename(path))[0])
        return uris

    def get_user_name(self):
        return os.environ.get('USERNAME')

    def create(self, project_name, entity_type, uri, data):
        json_filepath = self._get_json_filepath(project_name, entity_type, uri)
        if os.path.exists(json_filepath):
            raise PulseDatabaseError("node already exists:" + uri)

        json_folder = os.path.dirname(json_filepath)
        if not os.path.exists(json_folder):
            os.makedirs(json_folder)

        with open(json_filepath, "w") as write_file:
            json.dump(data, write_file, indent=4, sort_keys=True)

    def update(self, project_name, entity_type, uri, data_dict):
        json_filepath = self._get_json_filepath(project_name, entity_type, uri)
        if not os.path.exists(json_filepath):
            raise PulseDatabaseMissingObject(uri)

        with open(json_filepath, "r") as read_file:
            data = json.load(read_file)
        for k in data_dict:
            data[k] = data_dict[k]
        with open(json_filepath, "w") as write_file:
            json.dump(data, write_file, indent=4, sort_keys=True)

    def read(self, project_name, entity_type, uri):
        json_filepath = self._get_json_filepath(project_name, entity_type, uri)
        if not os.path.exists(json_filepath):
            raise PulseDatabaseMissingObject("no data for : " + project_name + ", " + entity_type + ", " + uri)
        with open(json_filepath, "r") as read_file:
            data = json.load(read_file)
        return data

    def _get_json_filepath(self, project_name, entity_type, uri):
        return os.path.join(self._root, project_name, entity_type,  uri + ".json")
