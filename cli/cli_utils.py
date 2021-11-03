import pulse.api as pulse
import pulse.uri_standards as uri_standards
import pulse.file_utils as fu
try:
    # legacy python 2.7 module
    from ConfigParser import ConfigParser
except ModuleNotFoundError:
    from configparser import ConfigParser as ConfigParser
import os
import json
import sys
try:
    # legacy python 2.7 module
    import urlparse
except ModuleNotFoundError:
    import urllib.parse as urlparse

project_data_filename = "project.pipe"
work_data_filename = "work.pipe"


class PulseCliError(Exception):
    def __init__(self, reason):
        Exception.__init__(self)
        self._reason = reason

    def reason(self):
        return self._reason

    def __str__(self):
        return self._reason


def failure_message(message):
    raise PulseCliError(message)
    #sys.exit()


def get_work(path, project=None):

    if not project:
        project = get_pulse_project(path)
    uri = (os.path.split(path.replace(project.work_directory, ""))[0])[1:]
    work_data_filepath = os.path.join(project.work_data_directory, fu.uri_to_json_filename(uri))
    if not os.path.exists(work_data_filepath):
        failure_message("Not in a work folder. Can't find " + work_data_filepath)
    with open(work_data_filepath, "r") as read_file:
        work_data = json.load(read_file)
    return project.get_resource(work_data['entity'], work_data['resource_type']).get_work()


def get_mysql_connection(adapter, url):
    db_settings = urlparse.urlparse(url)
    return pulse.Connection(
        adapter,
        username=db_settings.username,
        password=db_settings.password,
        host=db_settings.hostname,
        port=db_settings.port
    )


def get_pulse_project(path):
    connection_data = None
    while not len(path) < 4:
        project_data_filepath = os.path.join(path, project_data_filename)
        if os.path.exists(project_data_filepath):
            with open(project_data_filepath, "r") as read_file:
                connection_data = json.load(read_file)
                break
        path = os.path.dirname(path)
    if not connection_data:
        raise PulseCliError("can't connect to project : " + path)

    cnx = None
    if connection_data["adapter"] == "json_db":
        cnx = pulse.Connection(connection_data["adapter"], path=connection_data["settings"])
    elif connection_data["adapter"] == "mysql":
        cnx = get_mysql_connection(connection_data["adapter"], connection_data["settings"])
    return cnx.get_project(os.path.basename(path))


def get_project(args):
    # get config settings
    cli_filepath = os.path.dirname(os.path.realpath(__file__))
    config = ConfigParser()
    config.read(os.path.join(cli_filepath, "config.ini"))

    # if no adapter specified, get setting from config
    if not args.adapter:
        adapter = config.get('database', 'default_adapter')
    else:
        adapter = args.adapter

    # create a connexion to database
    if adapter == "json_db":
        cnx = pulse.Connection(adapter, path=args.settings)
    elif adapter == "mysql":
        cnx = get_mysql_connection(adapter, args.settings)
    else:
        print("database adapter not supported by CLI")
        return

    # create work and product path
    prj = cnx.get_project(args.name)
    project_work_root = os.path.expandvars(os.path.join(prj.cfg.work_user_root, args.name))
    project_product_root = os.path.expandvars(os.path.join(prj.cfg.product_user_root, args.name))

    if not os.path.exists(project_work_root):
        os.makedirs(project_work_root)
    if prj.cfg.product_user_root and not os.path.exists(project_product_root):
        os.makedirs(project_product_root)

    # save settings to json pipe file
    connexion_data = {
        'settings': args.settings,
        'adapter': args.adapter
    }

    with open(os.path.join(project_work_root, project_data_filename), "w") as write_file:
        json.dump(connexion_data, write_file, indent=4, sort_keys=True)
    print("project registered to ", os.path.normpath(os.path.expandvars(project_work_root)))


def create_template(args):
    project = get_pulse_project(os.getcwd())
    resource = project.create_template(args.type)
    work = resource.checkout()
    print('template check out in "' + os.path.normpath(os.path.expandvars(work.directory)) + '"')


def create_output(args):
    work = get_work(os.getcwd())
    product = work.create_product(args.type)
    print('product created in "' + os.path.normpath(os.path.expandvars(product.directory)) + '"')


def add_input(args):
    project = get_pulse_project(os.getcwd())
    product = project.get_product(args.uri)
    if not product:
        print('no product found for ' + args.uri)
        return
    work = get_work(os.getcwd(), project)
    work.add_input(product)
    print('product registered "' + args.uri + '"')


def create_resource(args):
    project = get_pulse_project(os.getcwd())
    uri_dict = uri_standards.convert_to_dict(args.uri)
    resource = project.create_resource(uri_dict['entity'], uri_dict['resource_type'])
    work = resource.checkout()
    print('resource check out in "' + os.path.normpath(os.path.expandvars(work.directory)) + '"')


def checkout(args):
    project = get_pulse_project(os.getcwd())
    dict_uri = uri_standards.convert_to_dict(args.uri)
    resource = project.get_resource(dict_uri['entity'], dict_uri['resource_type'])
    work = resource.checkout()
    try:
        last_commit = resource.get_commit("last")
        for product in last_commit.get_products():
            work.create_product(product.product_type)
    except pulse.PulseError:
        pass
    print('resource check out in "' + os.path.expandvars(work.directory) + '"')


def trash_resource(args):
    project = get_pulse_project(os.getcwd())
    dict_uri = uri_standards.convert_to_dict(args.uri)
    resource = project.get_resource(dict_uri['entity'], dict_uri['resource_type'])
    resource.get_work().trash()
    project.purge_unused_user_products(resource_filter=resource)
    print('resource trashed "' + resource.uri + '"')


def commit(args, path=os.getcwd()):
    work = get_work(path)
    try:
        commit_obj = work.commit(comment=args.comment)
        # cli creates creates empty products directory for the new version after the commit
        for product in commit_obj.get_products():
            work.create_product(product.product_type)
        print('work commit in version "' + str(commit_obj.version) + '"')
    except pulse.PulseError as e:
        print('work commit failed: ' + str(e))


def status(args):
    work = get_work(os.getcwd())
    diffs = work.status()
    if not diffs:
        print('no local changes detected')
    else:
        for elem in diffs:
            print(elem + ":" + diffs[elem])


def lock(args):
    resource = get_work(os.getcwd()).resource
    resource.set_lock(state=True, steal=True)
    print('resource locked "' + str(resource.uri) + '"')


def unlock(args):
    resource = get_work(os.getcwd()).resource
    resource.set_lock(state=False, steal=True)
    print('resource unlocked "' + str(resource.uri) + '"')


def revert(args):
    project = get_pulse_project(os.getcwd())
    dict_uri = uri_standards.convert_to_dict(args.uri)
    resource = project.get_resource(dict_uri['entity'], dict_uri['resource_type'])
    work = resource.get_work()
    work.revert()
    print("work reverted")


def update(args):
    project = get_pulse_project(os.getcwd())
    dict_uri = uri_standards.convert_to_dict(args.uri)
    resource = project.get_resource(dict_uri['entity'], dict_uri['resource_type'])
    work = resource.get_work()
    try:
        work.update()
        print("work updated to version: " + str(work.version))
    except pulse.PulseError as msg:
        print(msg)
