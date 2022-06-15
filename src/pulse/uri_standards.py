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
    product_split = uri_split[0].split(".")
    resource_split = product_split[0].split("-")
    entity = resource_split[0]
    resource_type = resource_split[1]

    if len(product_split) > 1:
        product_type = product_split[1]
    else:
        product_type = None

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
        "product_type": product_type,
        "subpath": subpath
    }


def convert_from_dict(uri_dict):
    """
    transform a dictionary to an uri.

    :param uri_dict: dictionary with minimum keys "entity" and "resource_type", optionally "product type" and "version"
    :return: uri string
    """
    uri = uri_dict["entity"] + "-" + uri_dict['resource_type']
    if 'product_type' in uri_dict and uri_dict['product_type']:
        uri += "." + uri_dict['product_type']
    if 'version' in uri_dict and uri_dict['version']:
        uri += "@" + (str(int(uri_dict['version'])))
    return uri


def path_to_uri(path):
    path = os.path.normpath(path)
    path_list = path.split(os.sep)
    mode = None
    uri_dict = {}

    # find the pulse_data_dir to determine if it's a product or work URI
    for i in range(1, len(path_list)):
        if os.path.exists(os.path.join(path, cfg.pulse_data_dir, "works")):
            mode = "work"
            break
        if os.path.exists(os.path.join(path, cfg.pulse_data_dir, "work_products")):
            mode = "product"
            break
        path = os.path.dirname(path)
    if not mode:
        raise PulseError("can't convert path to uri, no project found")

    # convert path element to URI dict
    try:
        split_dir = path_list[-(i - 1)].split("-")
        uri_dict['entity'] = split_dir[0]
        uri_dict['resource_type'] = split_dir[1]
        if mode == "product":
            uri_dict['version'] = int(path_list[-(i - 2)].replace(cfg.DEFAULT_VERSION_PREFIX, ""))
            if i > 3:
                uri_dict['product_type'] = path_list[-(i - 3)]
    except ValueError:
        raise PulseError("can't convert path to uri, malformed path")

    return convert_from_dict(uri_dict)


def remove_version_from_uri(uri):
    if not is_valid(uri):
        raise PulseUriError("Uri not valid : " + uri)
    split = uri.split("@")
    return split[0]


def edit(uri_string, edit_dict):
    uri_dict = convert_to_dict(uri_string)
    for k, v in edit_dict.items():
        uri_dict[k] = v
    return convert_from_dict(uri_dict)