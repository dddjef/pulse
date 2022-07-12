from pulse.exception import *


class PulseDatabase:
    def __init__(self, path="", username="", password="", settings=None):
        self.settings = settings
        self.path = path
        self.username = username
        self.password = password

    config_tables = {
        'Repository': [
            "adapter VARCHAR(255)",
            "login VARCHAR(255)",
            "password VARCHAR(255)",
            "settings LONGTEXT"
        ],
        'Project': [
            "created_by VARCHAR(255)"
        ]
    }

    project_tables = {
        'Config': [
            "work_user_root VARCHAR(255)",
            "product_user_root VARCHAR(255)",
            "default_repository VARCHAR(255)",
            "version_padding SMALLINT",
            "version_prefix VARCHAR(255)"
        ],
        'Commit': [
            "version INT",
            "products LONGTEXT",
            "files LONGTEXT",
            "comment VARCHAR(255)",
            "products_inputs LONGTEXT"
        ],
        'Resource': [
            "lock_state BOOLEAN",
            "lock_user VARCHAR(255)",
            "resource_type VARCHAR(255)",
            "entity VARCHAR(255)",
            "repository VARCHAR(255)",
            "metas LONGTEXT"
        ],
        'CommitProduct': [
            "product_type VARCHAR(255)",
            "products_inputs LONGTEXT"
        ]
    }
    adapter_version = '0.0.1'

    def create_repository(self, name, adapter, login, password, settings):
        pass

    def get_repositories(self):
        pass

    def get_projects(self):
        pass

    def create_project(self, project_name):
        pass

    def find_uris(self, project_name, entity_type, uri_pattern):
        pass

    def get_user_name(self):
        pass

    def write(self, project_name, entity_type, uri, data_dict):
        pass

    def read(self, project_name, entity_type, uri):
        pass
