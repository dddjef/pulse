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
