import os
from pulse.exception import *


def convert_to_dict(uri_string):
    """
    transform a string uri in a dict uri

    :param uri_string:
    :return uri dict:
    """
    uri_split_main = uri_string.split("@")
    uri_split = uri_split_main[0].split("-")
    entity = uri_split[0]
    category_split = uri_split[1].split(".")
    product_type = ""
    version = None

    if len(category_split) > 1:
        product_type = category_split[1]

    if len(uri_split_main) > 1:
        version = uri_split_main[1]

    return {"entity": entity, "resource_type": category_split[0], "version": version, "product_type": product_type}


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
    import pulse.api as pulse
    path = os.path.normpath(path)
    path_list = path.split(os.sep)
    mode = None
    uri_dict = {}

    # find the pulse_data_dir to determine if it's a product or work URI
    for i in range(1, len(path_list)):
        if os.path.exists(os.path.join(path, pulse.pulse_data_dir, "works")):
            mode = "work"
            break
        if os.path.exists(os.path.join(path, pulse.pulse_data_dir, "work_products")):
            mode = "product"
            break
        path = os.path.dirname(path)
    if not mode:
        raise PulseError("can't convert path to uri, no project found")

    # convert path element to URI dict
    # try:
    split_dir = path_list[-(i - 1)].split("-")
    uri_dict['entity'] = split_dir[0]
    uri_dict['resource_type'] = split_dir[1]
    if mode == "product":
        uri_dict['version'] = int(path_list[-(i - 2)].replace(pulse.DEFAULT_VERSION_PREFIX, ""))
        if i > 3:
            uri_dict['product_type'] = path_list[-(i - 3)]
    # except ValueError:
    #     raise PulseError("can't convert path to uri, malformed path")

    return convert_from_dict(uri_dict)
