import json
import project_config as cfg
import file_manager as fm
import os
import message as msg

DB_folder = cfg.WORK_REPOSITORY_ROOT + "\\DB"



def get_json_filepath(entity_type, uri):
    if entity_type == 'Resource':
        return DB_folder + "\\resources\\" + uri + "\\resource.json"
    elif entity_type == 'Version':
        filename = cfg.VERSION_PREFIX + uri.split("@")[1].zfill(cfg.VERSION_PADDING) + ".json"
        return DB_folder + "\\resources\\" + uri.split("@")[0] + "\\" + filename
    else:
        raise Exception('unknown database entity type')


def write(entity_type, uri, data_dict):
    json_filepath = get_json_filepath(entity_type, uri)
    json_folder = os.path.dirname(json_filepath)
    if not os.path.exists(json_folder):
        os.makedirs(json_folder)
    with open(json_filepath, "w") as write_file:
        json.dump(data_dict, write_file, indent=4, sort_keys=True)


def read(entity_type, uri):
    json_filepath = get_json_filepath(entity_type, uri)
    if not os.path.exists(json_filepath):
        print "No data for : " + uri
        return None

    with open(json_filepath, "r") as read_file:
        data = json.load(read_file)

    return data
