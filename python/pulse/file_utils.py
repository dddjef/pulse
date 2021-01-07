import os
import json
import ctypes
import hashlib
from sys import platform

def md5(filepath):
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def compare_directory_content(current_work_data, past_work_data):
    file_changes = []
    for filepath in current_work_data:
        if filepath.endswith(".pipe"):
            continue
        if filepath in past_work_data:
            if current_work_data[filepath]['checksum'] != past_work_data[filepath]['checksum']:
                file_changes.append((filepath, "edited"))
            past_work_data.pop(filepath)
        else:
            file_changes.append((filepath, "added"))

    for filepath in past_work_data:
        if not filepath.endswith(".pipe"):
            file_changes.append((filepath, "removed"))
    return file_changes


def get_directory_content(directory):
    files_dict = {}
    for root, subdirectories, files in os.walk(directory):
        for f in files:
            filepath = os.path.join(root, f)
            relative_path = filepath[len(directory):]
            files_dict[relative_path] = {"checksum": md5(filepath)}
    return files_dict


def test_path_write_access(path):
    try:
        os.rename(path, path + 'tmp')
        os.rename(path + 'tmp', path)
    except:
        return False
    return True


def read_data(filepath):
    with open(filepath, "r") as read_file:
        return json.load(read_file)


def write_data(filepath, data):
    if os.path.exists(filepath):
        os.remove(filepath)
    with open(filepath, "w") as write_file:
        json.dump(data, write_file, indent=4, sort_keys=True)
    if platform == "win32":
        ctypes.windll.kernel32.SetFileAttributesW(filepath, 2)


def json_list_remove(json_path, item):
    json_list = read_data(json_path)
    json_list.remove(item)
    write_data(json_path, json_list)


def json_list_append(json_path, item):
    if not os.path.exists(json_path):
        json_list = []
    else:
        json_list = read_data(json_path)
    if item not in json_list:
        json_list.append(item)
        write_data(json_path, json_list)


def json_list_get(json_path):
    if not os.path.exists(json_path):
        return []
    else:
        return read_data(json_path)


def remove_empty_parents_directory(directory, root_dirs):
    if not os.path.exists(directory):
        return
    while not os.listdir(directory):
        os.rmdir(directory)
        directory = os.path.dirname(directory)
        if directory.endswith(":") or directory in root_dirs:
            break
