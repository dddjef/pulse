import os
import shutil
from sys import platform
import subprocess

test_data_output_path = os.path.join(os.path.dirname(__file__), "data", "out")
json_db_path = os.path.join(test_data_output_path, "DB")
sandbox_work_path = os.path.join(test_data_output_path, "works")
sandbox_products_path = os.path.join(test_data_output_path, "products")
file_storage_path = os.path.join(test_data_output_path, "repos").replace("\\", "/")


def reset_test_data(root=test_data_output_path):
    if os.path.exists(root):
        # first remove all read only mode from files attributes
        for path, subdirs, files in os.walk(root):
            for name in files:
                filepath = os.path.join(path, name)
                if filepath.endswith(".pipe"):
                    if platform == "win32":
                        os.chmod(filepath, 0o777)

        if platform == "win32":
            subprocess.call('rmdir /s /q "' + root + '"', shell=True)
        else:
            shutil.rmtree(root)
    os.makedirs(root)


def add_file_to_directory(directory, filename="any_file.txt", source_filepath=None):
    if not os.path.isdir(directory):
        os.makedirs(directory)

    if not source_filepath:
        open(os.path.join(directory, filename), 'a').close()
    else:
        shutil.copy(source_filepath, os.path.join(directory, os.path.basename(source_filepath)))
