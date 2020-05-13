from datetime import datetime


def get_date_time():
    now = datetime.now()
    return now.strftime("%d-%m-%Y_%H-%M-%S")


def build_project_trash_filepath(work):
    """custom function to build a sandbox trash path.
    """
    path = work.project.cfg.work_user_root + "\\" + work.project.name + "\\" + "TRASH" + "\\"
    path += work.resource.resource_type + "-" + work.resource.entity.replace(":", "_") + "-" + get_date_time()
    return path


def build_products_filepath(resource, version_index):
    """custom function to build a user product resource path.
    """
    version = str(version_index).zfill(resource.project.cfg.version_padding)
    path = resource.project.cfg.product_user_root + "\\" + resource.resource_type
    path += "\\" + resource.entity.replace(":", "\\") + "\\" + resource.project.cfg.version_prefix + version
    return path
