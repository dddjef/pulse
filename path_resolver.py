import project_config as cfg
import os
from datetime import datetime

def get_date_time():
    now = datetime.now()
    return now.strftime("%d-%m-%Y_%H-%M-%S")

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


def build_project_trash_filepath(work):
    """custom function to build a sandbox trash path.
    """
    path = cfg.WORK_USER_ROOT + "\\" + cfg.PROJECT_SHORT_NAME + "\\" + "TRASH" + "\\"
    path += work.resource.resource_type + "-" + work.resource.entity.replace(":", "_") + "-" + get_date_time()
    return path


def build_products_filepath(entity, resource_type, version_index):
    """custom function to build a user product resource path.
    """
    version = str(version_index).zfill(cfg.VERSION_PADDING)
    path = cfg.PRODUCT_USER_ROOT + "\\" + resource_type
    path += "\\" + entity.replace(":", "\\")+ "\\" + cfg.VERSION_PREFIX + version
    return path
