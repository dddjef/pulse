from pulse.uri_parser import uri_parser
import pulse.file_manager as fm

# TO DO : create_resource should use test for existing resource within the api to avoid testing in file manager

def create_resource(uri_string):
    """Create a new resource for the given type
    """
    uri = uri_parser(uri_string)
    fm.create_resource(uri)

if __name__ == '__main__':
    print create_resource("paf-texture")