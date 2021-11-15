import os
import json
import hashlib
import shutil
import sys
import subprocess


def md5(filepath):
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def compare_directory_content(current_work_data, past_work_data):
    file_changes = {}
    for filepath in current_work_data:
        if filepath.endswith(".pipe"):
            continue
        if filepath in past_work_data:
            if current_work_data[filepath]['checksum'] != past_work_data[filepath]['checksum']:
                file_changes[filepath] = "edited"
            past_work_data.pop(filepath)
        else:
            file_changes[filepath] = "added"

    for filepath in past_work_data:
        if not filepath.endswith(".pipe"):
            file_changes[filepath] = "removed"
    return file_changes


def get_directory_content(directory, ignore_list=None):
    files_dict = {}
    if ignore_list:
        ignore_list = [p.replace(os.sep, '/') for p in ignore_list]
    else:
        ignore_list = []
    for root, dirs, files in os.walk(directory, topdown=True):
        dirs[:] = [d for d in dirs if os.path.join(root, d).replace(os.sep, '/') not in ignore_list]
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
    directory = os.path.dirname(filepath)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    with open(filepath, "w") as write_file:
        json.dump(data, write_file, indent=4, sort_keys=True)


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


def json_list_init(json_path):
    write_data(json_path, [])


def json_filename_to_uri(filename):
    return os.path.basename(filename).replace(".json", "")


def uri_to_json_filename(uri):
    return uri + ".json"


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


def copytree(src, dst, ignore=None):
    """
    based on shutil.copytree but using the copyfile function to avoid permission error on linux
    could be removed on python 3 since there's the copy_function argument with shutil.copytree
    """
    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    os.makedirs(dst)
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)

        if os.path.isdir(srcname):
            copytree(srcname, dstname, ignore)
        else:
            shutil.copyfile(srcname, dstname)


def move_file(src_path, dst_path):
    dst_path = dst_path.replace("\\", "/")
    new_dir = os.path.split(dst_path)[0]
    if not os.path.isdir(new_dir):
        os.makedirs(new_dir)
    shutil.move(src_path, dst_path)


def make_directory_link(source, destination):
    # remove old source directory if needed
    if os.path.exists(source):
        os.remove(source)
    # if system is windows make a junction (symlink requires admin privileges)
    if sys.platform == "win32":
        cmd = ('mklink /j "' + source + '" "' + destination + '"')
        with open(os.devnull, 'wb') as none_file:
            subprocess.call(cmd.replace("\\", "/"), shell=True, stdout=none_file, stderr=none_file)