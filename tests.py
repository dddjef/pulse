from pulse.api import *
import string
import random
import pulse.path_resolver as pr

letters = string.ascii_lowercase
entity_name = ''.join(random.choice(letters) for i in range(10))
entity_name = "fixedX"

uri_test = entity_name + "-modeling"

create_resource(uri_test)
resource = get_resource(uri_test)


work = resource.checkout()
print work.get_files_changes()
# resource.set_lock(True)
work.commit("very first time")

# resource.trash_work()