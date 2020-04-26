class PulseRepositoryError(Exception):
    def __init__( self, reason):
        Exception.__init__(self)
        self._reason = reason

    def reason(self):
        return self._reason

    def __str__(self):
        return self._reason


class PulseRepository:
    def __init__(self):
        pass

    def upload_resource_commit(self, commit, work_folder, products_folder=None):
        pass

    def download_work(self, commit, work_folder):
        pass

    def download_product(self, product):
        pass
