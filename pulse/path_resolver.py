from datetime import datetime


def get_date_time():
    now = datetime.now()
    return now.strftime("%d-%m-%Y_%H-%M-%S")


def build_work_filepath(project, resource):
    """custom function to build a sandbox resource path.
    """
    path = project.cfg.work_user_root + "\\" + project.name
    path += "\\" + resource.resource_type + "\\" + resource.entity.replace(":", "\\")
    return path


def build_project_trash_filepath(project, work):
    """custom function to build a sandbox trash path.
    """
    path = project.cfg.work_user_root + "\\" + project.name + "\\" + "TRASH" + "\\"
    path += work.resource.resource_type + "-" + work.resource.entity.replace(":", "_") + "-" + get_date_time()
    return path


def build_products_filepath(project, entity, resource_type, version_index):
    """custom function to build a user product resource path.
    """
    # TODO standardize access with resource entity
    version = str(version_index).zfill(project.cfg.version_padding)
    path = project.cfg.product_user_root + "\\" + resource_type
    path += "\\" + entity.replace(":", "\\") + "\\" + project.cfg.version_prefix + version
    return path
