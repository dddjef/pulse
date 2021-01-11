#!/usr/bin/env python2
import argparse
import pulse.api as pulse
import pulse.uri_standards as uri_standards
from ConfigParser import ConfigParser
import os
import json
import sys
import urlparse

project_data_filename = "project.pipe"
work_data_filename = "work.pipe"


def failure_message(message):
    print(message)
    sys.exit()


def get_work(path, project=None):
    if not project:
        project = get_pulse_project(path)
    work_data_filepath = os.path.join(path, work_data_filename)
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

    while not path.endswith(":\\"):
        project_data_filepath = os.path.join(path, project_data_filename)
        if os.path.exists(project_data_filepath):
            with open(project_data_filepath, "r") as read_file:
                connection_data = json.load(read_file)
                break
        path = os.path.dirname(path)
    if not connection_data:
        raise Exception("can't connect to project : " + path)

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
        print "database adapter not supported by CLI"
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
    print "project registered to ", project_work_root


def create_template(args):
    project = get_pulse_project(os.getcwd())
    resource = project.create_template(args.type)
    work = resource.checkout()
    print 'template check out in "' + work.directory + '"'


def create_output(args):
    work = get_work(os.getcwd())
    product = work.create_product(args.type)
    print 'product created in "' + product.directory + '"'


def add_input(args):
    project = get_pulse_project(os.getcwd())
    product = project.get_product(args.uri)
    if not product:
        print ('no product found for ' + args.uri)
        return
    work = get_work(os.getcwd(), project)
    work.add_input(product)
    print 'product registered "' + args.uri + '"'


def create_resource(args):
    project = get_pulse_project(os.getcwd())
    uri_dict = uri_standards.convert_to_dict(args.uri)
    resource = project.create_resource(uri_dict['entity'], uri_dict['resource_type'])
    work = resource.checkout()
    print 'resource check out in "' + work.directory + '"'


def checkout(args):
    project = get_pulse_project(os.getcwd())
    dict_uri = uri_standards.convert_to_dict(args.uri)
    resource = project.get_resource(dict_uri['entity'], dict_uri['resource_type'])
    work = resource.checkout()
    print 'resource check out in "' + work.directory + '"'


def trash_resource(args):
    project = get_pulse_project(os.getcwd())
    dict_uri = uri_standards.convert_to_dict(args.uri)
    resource = project.get_resource(dict_uri['entity'], dict_uri['resource_type'])
    resource.get_work().trash()
    project.purge_unused_user_products(resource_filter=resource)
    print 'resource trashed "' + resource.uri + '"'


def commit(args):
    work = get_work(os.getcwd())
    try:
        commit_obj = work.commit(comment=args.comment)
        print('work commit in version "' + str(commit_obj.version) + '"')
    except pulse.PulseError, e:
        print('work commit failed: ' + str(e))


def status(args):
    work = get_work(os.getcwd())
    diffs = work.status()
    if not diffs:
        print 'no local changes detected'
    else :
        for elem in diffs:
            print elem[0] + ":" + elem[1]


def lock(args):
    resource = get_work(os.getcwd()).resource
    resource.set_lock(state=True, steal=True)
    print 'resource locked "' + str(resource.uri) + '"'


def unlock(args):
    resource = get_work(os.getcwd()).resource
    resource.set_lock(state=False, steal=True)
    print 'resource unlocked "' + str(resource.uri) + '"'


def revert(args):
    project = get_pulse_project(os.getcwd())
    dict_uri = uri_standards.convert_to_dict(args.uri)
    resource = project.get_resource(dict_uri['entity'], dict_uri['resource_type'])
    work = resource.get_work()
    work.revert()
    print "work reverted"


def update(args):
    project = get_pulse_project(os.getcwd())
    dict_uri = uri_standards.convert_to_dict(args.uri)
    resource = project.get_resource(dict_uri['entity'], dict_uri['resource_type'])
    work = resource.get_work()
    work.update()
    print "work updated to version: " + str(work.version)


# create the top-level parser
parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers()

# get project subparser
parser_get_project = subparsers.add_parser('get_project')
parser_get_project.add_argument('name', type=str)
parser_get_project.add_argument('--settings', type=str)
parser_get_project.add_argument('--adapter', type=str)
parser_get_project.set_defaults(func=get_project)

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
parser_commit.add_argument('--comment', type=str)
parser_commit.set_defaults(func=commit)

# unlock subparser
parser_unlock = subparsers.add_parser('unlock')
parser_unlock.set_defaults(func=unlock)

# lock subparser
parser_lock = subparsers.add_parser('lock')
parser_lock.set_defaults(func=lock)

# add_input subparser
parser_add_input = subparsers.add_parser('add_input')
parser_add_input.add_argument('uri', type=str)
parser_add_input.set_defaults(func=add_input)

# status subparser
parser_status = subparsers.add_parser('status')
parser_status.set_defaults(func=status)

# revert subparser
parser_revert = subparsers.add_parser('revert')
parser_revert.add_argument('uri', type=str)
parser_revert.set_defaults(func=revert)

# update subparser
parser_update = subparsers.add_parser('update')
parser_update.add_argument('uri', type=str)
parser_update.set_defaults(func=update)

cmd_args = parser.parse_args()
if cmd_args.func:
    cmd_args.func(cmd_args)
