# myls.py
# Import the argparse library
import argparse

import os
import sys

# Create the parser
my_parser = argparse.ArgumentParser(description='List the content of a folder')

# Add the arguments
my_parser.add_argument('Path',
                       metavar='path',
                       type=str,
                       help='the path to list')

# Execute the parse_args() method
args = my_parser.parse_args()

input_path = args.Path
print os.getcwd()
os.chdir("c:\\")
os.system('cd..')