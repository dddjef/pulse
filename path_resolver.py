import project_config as cfg


def build_resource_template_path(resource_type):
    """custom function to build a template path
    """
    return cfg.TEMPLATE_PATH + "\\" + resource_type


def build_work_filepath(uri_dict):
    """custom function to build a sandbox resource path.
    """
    path = cfg.WORK_USER_ROOT + "\\" + cfg.PROJECT_SHORT_NAME
    path += "\\" + uri_dict['resource_type'] + "\\" + uri_dict['entity'].replace(":", "\\")
    return path


def build_product_filepath(uri_dict):
    """custom function to build a user product resource path.
    """
    path = cfg.PRODUCT_USER_ROOT
    path += "\\" + uri_dict['resource_type'] + "\\" + uri_dict['entity'].replace(":", "\\")
    return path
