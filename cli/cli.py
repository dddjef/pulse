import argparse
import pulse.api as pulse
from ConfigParser import ConfigParser
import os


def create_project(args):
    cli_filepath = os.path.dirname(os.path.realpath(__file__))

    config = ConfigParser()
    config.read(os.path.join(cli_filepath, "config.ini"))
    database_type = config.get('database', 'default_adapter')
    default_repository_type = config.get('repository', 'default_adapter')
    if not args.repository_parameters:
        args.repository_parameters = config.get('repository', 'default_parameters')
    version_prefix = config.get('version', 'prefix')
    version_padding = int(config.get('version', 'padding'))

    cnx = pulse.Connection({"DB_root": args.db_host}, database_type)
    prj = cnx.create_project(
        args.project_name,
        args.user_work,
        args.user_products,
        version_padding=version_padding,
        version_prefix=version_prefix,
        default_repository_type=default_repository_type,
        default_repository_parameters=eval(args.repository_parameters)
    )
    print 'project "' + args.project_name + '" created on "' + args.db_host + '"'


def bar(args):
    print('((%s))' % args.z)


# create the top-level parser
parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers()

# create project subcommand
parser_create_project = subparsers.add_parser('create_project')
parser_create_project.add_argument('project_name', type=str)
parser_create_project.add_argument('db_host', type=str)
parser_create_project.add_argument('user_work', type=str)
parser_create_project.add_argument('user_products', type=str)
parser_create_project.add_argument('--db_login', type=str)
parser_create_project.add_argument('--db_password', type=str)
parser_create_project.add_argument('--repository_parameters', type=str)

parser_create_project.set_defaults(func=create_project)

# create a test subparser
parser_bar = subparsers.add_parser('bar')
parser_bar.add_argument('z')
parser_bar.set_defaults(func=bar)


args = parser.parse_args()
if args.func:
    args.func(args)
