def uri_parser(uri_string):
    uri_split_main = uri_string.split("@")
    if len(uri_split_main)>1:
        version = uri_split_main[1]
    else:
        version = "0"
    uri_split = uri_split_main[0].split("-")
    entity = uri_split[0]
    resource_type = uri_split[1]
    return {"entity": entity, "resource_type": resource_type, "version":version}
