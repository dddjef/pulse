import os
import json

def compare_directory_content(current_work_data, past_work_data):
    file_changes = []
    for filepath in current_work_data:
        if filepath in past_work_data:
            if current_work_data[filepath]['date'] != past_work_data[filepath]['date']:
                file_changes.append((filepath, "edited"))
            past_work_data.pop(filepath)
        else:
            file_changes.append((filepath, "added"))

    for filepath in past_work_data:
        file_changes.append((filepath, "removed"))
    return file_changes


def get_directory_content(directory, exclude_list=[]):
    files_dict = {}
    for root, subdirectories, files in os.walk(directory):
        for f in files:
            filepath = os.path.join(root, f)
            if filepath not in exclude_list:
                files_dict[filepath] = {"date": os.path.getmtime(filepath)}
    return files_dict


