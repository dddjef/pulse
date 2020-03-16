import json
import project_config as cfg

DB_folder = cfg.WORK_REPOSITORY_ROOT + "\\DB"

resource_data_file = "resource.json"

default_resource_data = {
    "lock": False,
    "lock_info": "",
    "versions": [{"index": 0, "comment": "initial version"}]
}


def get_resource_data(uri):
    """get resource data
    :return:dict
    """
    resource_data_path = build_resource_repository_path(uri) + "\\" + resource_data_file
    if os.path.exists(resource_data_path):
        print "No data for : " + resource_data_path

    with open(resource_data_path, "r") as read_file:
        data = json.load(read_file)
        print data

    return data

def writeDB():
    # add default resource data
    with open(build_resource_repository_path(uri) + "\\" + resource_data_file, "w") as write_file:
        json.dump(default_resource_data, write_file)