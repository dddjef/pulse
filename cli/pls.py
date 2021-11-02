#!/usr/bin/env python2
import argparse
from cli_utils import *

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
