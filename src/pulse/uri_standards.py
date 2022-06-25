import os
from pulse.exception import *
import pulse.config as cfg
import re


def is_valid(uri):
    if re.match(r'[A-Za-z0-9._]+-[A-Za-z0-9._]+@*[A-Za-z0-9._]*', uri):
        return True
    return False


def is_mutable(uri):
    uri_dict = convert_to_dict(uri)
    if not uri_dict["version"]:
        return True
    return uri_dict["version"].isalpha()


def convert_to_dict(uri_string):
    """
    transform a string uri in a dict uri

    :param uri_string:
    :return uri dict:
    """
    if not is_valid(uri_string):
        raise PulseUriError("Uri not valid : " + uri_string)

    subpath_split = uri_string.split("/", 1)
    uri_split = subpath_split[0].split("@")
    resource_split = uri_split[0].split("-")
    entity = resource_split[0]
    resource_type = resource_split[1]

    if len(uri_split) > 1:
        version = uri_split[1]
    else:
        version = None

    if len(subpath_split) > 1:
        subpath = subpath_split[1]
    else:
        subpath = ""

    return {
        "entity": entity,
        "resource_type": resource_type,
        "version": version,
        "subpath": subpath
    }


def convert_from_dict(uri_dict):
    """
    transform a dictionary to an uri.

    :param uri_dict: dictionary with minimum keys "entity" and "resource_type", optionally "product type" and "version"
    :return: uri string
    """
    uri = uri_dict["entity"] + "-" + uri_dict['resource_type']
    if 'version' in uri_dict and uri_dict['version']:
        uri += "@" + str(uri_dict['version'])
    if 'subpath' in uri_dict and uri_dict['subpath']:
        if uri_dict['subpath'].startswith("/"):
            uri_dict['subpath'] = uri_dict['subpath'][1:]
        subpath = uri_dict['subpath']
        if subpath != "":
            uri += "/" + subpath
    return uri


def path_to_uri(path):
    path = os.path.normpath(path)
    path_list = path.split(os.sep)
    mode = None
    uri_dict = {}

    # find the pulse_data_dir to determine pulse root and if it's a product or work context
    pulse_root = ""
    for item in path_list:
        if item.endswith(":"):
            item += "\\"
        pulse_root = os.path.join(pulse_root, item)
        if os.path.exists(os.path.join(pulse_root, cfg.pulse_data_dir, "works")):
            mode = "work"
            break
        if os.path.exists(os.path.join(pulse_root, cfg.pulse_data_dir, "work_products")):
            mode = "product"
            break
    if not mode:
        raise PulseError("can't convert path to uri, no pulse root found : " + path)

    # convert pulse path to URI dict
    pulse_path_split = path[len(pulse_root)+1:].split(os.sep)
    try:
        split_dir = pulse_path_split[0].split("-")
        uri_dict['entity'] = split_dir[0]
        uri_dict['resource_type'] = split_dir[1]
        if mode == "product":
            uri_dict['version'] = int(pulse_path_split[1].replace(cfg.DEFAULT_VERSION_PREFIX, ""))
            if len(pulse_path_split) > 2:
                subpath = ""
                for item in pulse_path_split[2:]:
                    subpath += "/" + item
                uri_dict['subpath'] = subpath
    except ValueError:
        raise PulseError("can't convert path to uri, malformed path")

    return convert_from_dict(uri_dict)


def edit(uri_string, edit_dict):
    uri_dict = convert_to_dict(uri_string)
    for k, v in edit_dict.items():
        uri_dict[k] = v
    return convert_from_dict(uri_dict)


def uri_to_filename(uri):
    return uri.replace("/", "~")


def filename_to_uri(filename):
    return filename.replace("~", "/")
