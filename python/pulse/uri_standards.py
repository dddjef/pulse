import os
from pulse.exception import *
import pulse.config as cfg

def convert_to_dict(uri_string):
    """
    transform a string uri in a dict uri

    :param uri_string:
    :return uri dict:
    """

    # REGEX alternative but it fails when version is not present
    # pat = re.compile("(?P<entity>.+)\-(?P<resource_type>.+)\.(?P<product_type>.+)\@(?P<version>.+)")
    # return pat.match(text).groupdict()

    uri_split = uri_string.split("@")
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

    return {"entity": entity, "resource_type": resource_type, "version": version, "product_type": product_type}


def convert_from_dict(uri_dict):
    """
    transform a dictionary to an uri.

    :param uri_dict: dictionary with minimum keys "entity" and "resource_type", optionally "product type" and "version"
    :return: uri string
    """
    uri = uri_dict["entity"] + "-" + uri_dict['resource_type']
    if 'product_type' in uri_dict:
        uri += "." + uri_dict['product_type']
    if 'version' in uri_dict:
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
    split = uri.split("@")
    return split[0]