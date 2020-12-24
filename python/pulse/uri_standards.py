def convert_to_dict(uri_string):
    """
    transform a string uri in a dict uri

    :param uri_string:
    :return uri dict:
    """
    uri_split_main = uri_string.split("@")
    uri_split = uri_split_main[0].split(":")
    entity = uri_split[0]
    category_split = uri_split[1].split("-")
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
    uri = uri_dict["entity"] + ":" + uri_dict['resource_type']
    if 'product_type' in uri_dict:
        uri += "-" + uri_dict['product_type']
    if 'version' in uri_dict:
        uri += "@" + (str(int(uri_dict['version'])))
    return uri
