# If you need to prepare your database, this is the different entity types and their stored attributes:
# Config = ["work_user_root", "product_user_root", "repositories", "version_padding", "version_prefix"]
# Commit = ['version', 'uri', 'products', 'files', 'comment']
# Resource = ['lock', 'lock_user', 'last_version', 'resource_type', 'entity', 'repository', 'metas']
# CommitProduct = ['product_type', 'products_inputs', 'uri']


class PulseDatabaseError(Exception):
    def __init__(self, reason):
        Exception.__init__(self)
        self._reason = reason

    def reason(self):
        return self._reason

    def __str__(self):
        return self._reason


class PulseDatabaseMissingObject(Exception):
    def __init__(self, reason):
        Exception.__init__(self)
        self._reason = reason

    def reason(self):
        return self._reason

    def __str__(self):
        return self._reason


class PulseDatabase:
    def __init__(self):
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
