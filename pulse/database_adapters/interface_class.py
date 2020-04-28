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
