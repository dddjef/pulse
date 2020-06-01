import argparse
import pulse.api as pulse
from ConfigParser import ConfigParser
import os
import json


project_data_filename = "project.pipe"


def get_work(path, project=None):
    if not project:
        project = get_pulse_project(path)
    relative_path = path[len(project.cfg.work_user_root+project.name) + 2:]
    split_path = relative_path.split(os.sep)
    entity_name = ""
    for part in split_path[1:]:
        entity_name += ":" + part
    entity_name = entity_name[1:]
    resource_type = split_path[0]
    return project.get_resource(entity_name, resource_type).get_work()


def get_pulse_project(path):
    connection_data = None

    while not path.endswith(":\\"):
        project_data_filepath = os.path.join(path, project_data_filename)
        if os.path.exists(project_data_filepath):
            with open(project_data_filepath, "r") as read_file:
                connection_data = json.load(read_file)
                break
        path = os.path.dirname(path)

    if not connection_data:
        raise Exception("can't connect to project : " + path)

    cnx = pulse.Connection(url=connection_data["url"], database_adapter=connection_data["db_adapter"])
    return cnx.get_project(os.path.basename(path))


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
    default_repository_adapter = config.get('repository', 'default_adapter')
    if not args.repository_url:
        args.repository_url = config.get('repository', 'default_parameters')
    version_prefix = config.get('version', 'prefix')
    version_padding = int(config.get('version', 'padding'))

    cnx = pulse.Connection(url=args.url, database_adapter=database_type)
    cnx.create_project(
        project_name,
        sandbox_path,
        repository_url=args.repository_url,
        product_user_root=args.user_products,
        version_padding=version_padding,
        version_prefix=version_prefix,
        repository_adapter=default_repository_adapter,
    )

    connexion_data = {
        'url': args.url,
        'db_adapter': database_type
    }
    with open(os.path.join(os.getcwd(), project_data_filename), "w") as write_file:
        json.dump(connexion_data, write_file, indent=4, sort_keys=True)

    print 'project "' + project_name + '" created on "' + args.url + '"'


def create_template(args):
    project = get_pulse_project(os.getcwd())
    resource = project.create_template(args.type)
    work = resource.checkout()
    print 'template check out in "' + work.directory + '"'


def create_output(args):
    work = get_work(os.getcwd())
    product = work.create_product(args.type)
    print 'product created in "' + product.directory + '"'
    # print resource.sandbox_path


def create_resource(args):
    project = get_pulse_project(os.getcwd())
    resource_name = args.uri.split("-")[0]
    resource_type = args.uri.split("-")[1]
    resource = project.create_resource(resource_name, resource_type)
    work = resource.checkout()
    print 'resource check out in "' + work.directory + '"'


def checkout(args):
    project = get_pulse_project(os.getcwd())
    dict_uri = pulse.uri_to_dict(args.uri)
    resource = project.get_resource(dict_uri['entity'], dict_uri['type'])
    work = resource.checkout()
    print 'resource check out in "' + work.directory + '"'


def trash_resource(args):
    project = get_pulse_project(os.getcwd())
    dict_uri = pulse.uri_to_dict(args.uri)
    resource = project.get_resource(dict_uri['entity'], dict_uri['resource_type'])
    resource.get_work().trash()
    project.purge_unused_user_products(resource_filter=resource)
    print 'resource trashed "' + resource.uri + '"'


def commit(args):
    work = get_work(os.getcwd())
    commit_obj = work.commit()
    print 'work commit in version "' + str(commit_obj.version) + '"'
    # print resource.sandbox_path


# create the top-level parser
parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers()

# create project subparser
parser_create_project = subparsers.add_parser('create_project')
parser_create_project.add_argument('url', type=str)
parser_create_project.add_argument('--user_products', type=str)
parser_create_project.add_argument('--repository_url', type=str)
parser_create_project.add_argument('--silent_mode', '-s', action='store_true')

parser_create_project.set_defaults(func=create_project)

# create_resource subparser
parser_create_resource = subparsers.add_parser('create_resource')
parser_create_resource.add_argument('uri', type=str)
parser_create_resource.add_argument('--silent_mode', '-s', action='store_true')
parser_create_resource.set_defaults(func=create_resource)

# create_template subparser
parser_create_template = subparsers.add_parser('create_template')
parser_create_template.add_argument('type', type=str)
parser_create_template.set_defaults(func=create_template)

# create_output subparser
parser_create_output = subparsers.add_parser('create_output')
parser_create_output.add_argument('type', type=str)
parser_create_output.set_defaults(func=create_output)

# checkout subparser
parser_checkout = subparsers.add_parser('checkout')
parser_checkout.add_argument('uri', type=str)
parser_checkout.set_defaults(func=checkout)

# trash resource subparser
parser_trash_resource = subparsers.add_parser('trash')
parser_trash_resource.add_argument('uri', type=str)
parser_trash_resource.set_defaults(func=trash_resource)

# commit subparser
parser_commit = subparsers.add_parser('commit')
parser_commit.set_defaults(func=commit)


cmd_args = parser.parse_args()
if cmd_args.func:
    cmd_args.func(cmd_args)
