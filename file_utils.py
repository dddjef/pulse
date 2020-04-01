import os
import json

def compare_directory_content(current_work_data, past_work_data):
    file_changes = []
    for filepath in current_work_data:
        if filepath in past_work_data:
            if current_work_data[filepath]['date'] != past_work_data[filepath]['date']:
                print("date diff", current_work_data[filepath], past_work_data[filepath])
                file_changes.append((filepath, "edited"))
            past_work_data.pop(filepath)
        else:
            file_changes.append((filepath, "added"))

    for filepath in past_work_data:
        file_changes.append((filepath, "removed"))
    return file_changes


def get_directory_content(directory):
    files_dict = {}
    for root, subdirectories, files in os.walk(directory):
        for f in files:
            if f.endswith(".pipe"):
                continue
            filepath = os.path.join(root, f)
            relative_path = filepath[len(directory):]
            files_dict[relative_path] = {"date": os.path.getmtime(filepath)}
    print directory
    print files_dict
    return files_dict


def test_path_write_access(path):
    try:
        os.rename(path, path + 'tmp')
        os.rename(path + 'tmp', path)
    except:
        return False
    return True
