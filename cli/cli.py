import argparse
import pulse.api as pulse
from ConfigParser import ConfigParser
import os
import json


project_data_filename = "project.pipe"


def get_pulse_project():
    curdir = os.getcwd()
    connection_data = None

    while not curdir.endswith(":\\"):
        project_data_filepath = os.path.join(curdir, project_data_filename)
        if os.path.exists(project_data_filepath):
            with open(project_data_filepath, "r") as read_file:
                connection_data = json.load(read_file)
                break
        curdir = os.path.dirname(curdir)

    if not connection_data:
        return

    cnx = pulse.Connection({"DB_root": connection_data["host"]}, connection_data["db_type"])
    return cnx.get_project(os.path.basename(curdir))


def create_project(args):
    cli_filepath = os.path.dirname(os.path.realpath(__file__))
    config = ConfigParser()
    config.read(os.path.join(cli_filepath, "config.ini"))

    project_path = os.getcwd()
    project_name = os.path.basename(project_path)
    sandbox_path = os.path.dirname(project_path)
    if not args.user_products:
        args.user_products = sandbox_path

    if not args.silent_mode:
        confirmation = raw_input('Are you sure to create the project ' + project_name + '?')
        if confirmation.lower() != 'y':
            return

    database_type = config.get('database', 'default_adapter')
    default_repository_type = config.get('repository', 'default_adapter')
    if not args.repository_parameters:
        args.repository_parameters = config.get('repository', 'default_parameters')
    version_prefix = config.get('version', 'prefix')
    version_padding = int(config.get('version', 'padding'))

    cnx = pulse.Connection({"DB_root": args.host}, database_type)
    cnx.create_project(
        project_name,
        sandbox_path,
        args.user_products,
        version_padding=version_padding,
        version_prefix=version_prefix,
        default_repository_type=default_repository_type,
        default_repository_parameters=eval(args.repository_parameters)
    )

    connexion_data = {
        'host': args.host,
        'login': args.login,
        'password': args.password,
        'db_type': database_type
    }
    with open(os.path.join(os.getcwd(), project_data_filename), "w") as write_file:
        json.dump(connexion_data, write_file, indent=4, sort_keys=True)

    print 'project "' + project_name + '" created on "' + args.host + '"'


def create_template(args):
    project = get_pulse_project()
    resource = project.create_template(args.type)
    work = resource.checkout()
    print 'template check out in "' + work.directory + '"'


def create_resource(args):
    project = get_pulse_project()
    resource_name = args.name.split("-")[0]
    resource_type = args.name.split("-")[1]
    resource = project.create_resource(resource_name, resource_type)
    work = resource.checkout()
    print 'resource check out in "' + work.directory + '"'


# create the top-level parser
parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers()

# create project subparser
parser_create_project = subparsers.add_parser('create_project')
parser_create_project.add_argument('host', type=str)
parser_create_project.add_argument('--user_products', type=str)
parser_create_project.add_argument('--login', type=str)
parser_create_project.add_argument('--password', type=str)
parser_create_project.add_argument('--repository_parameters', type=str)
parser_create_project.add_argument('--silent_mode', '-s', action='store_true')

parser_create_project.set_defaults(func=create_project)

# create_resource subparser
parser_create_resource = subparsers.add_parser('create_resource')
parser_create_resource.add_argument('name', type=str)
parser_create_resource.add_argument('--silent_mode', '-s', action='store_true')
parser_create_resource.set_defaults(func=create_resource)

# create_template subparser
parser_create_template = subparsers.add_parser('create_template')
parser_create_template.add_argument('type', type=str)
parser_create_template.set_defaults(func=create_template)

args = parser.parse_args()
if args.func:
    args.func(args)
