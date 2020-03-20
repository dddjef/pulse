import project_config as cfg


def build_resource_template_path(resource):
    """custom function to build a template path
    """
    return cfg.TEMPLATE_PATH + "\\" + resource.resource_type


def build_work_filepath(resource):
    """custom function to build a sandbox resource path.
    """
    path = cfg.WORK_USER_ROOT + "\\" + cfg.PROJECT_SHORT_NAME
    path += "\\" + resource.resource_type + "\\" + resource.entity.replace(":", "\\")
    return path


def build_trash_filepath(resource):
    """custom function to build a sandbox trash path.
    """
    path = cfg.WORK_USER_ROOT + "\\" + cfg.PROJECT_SHORT_NAME + "\\" + "TRASH"
    return path


def build_product_filepath(resource, index):
    """custom function to build a user product resource path.
    """
    version = str(index).zfill(cfg.VERSION_PADDING)
    path = cfg.PRODUCT_USER_ROOT + "\\" + resource.resource_type
    path += "\\" + resource.entity.replace(":", "\\")+ "\\" + cfg.VERSION_PREFIX + version
    return path
