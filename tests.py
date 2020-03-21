from pulse.api import *
import string
import random
import pulse.path_resolver as pr

letters = string.ascii_lowercase
entity_name = ''.join(random.choice(letters) for i in range(10))
entity_name = "fixedK"

uri_test = entity_name + "-modeling"

create_resource(uri_test)
resource = get_resource(uri_test)
print resource.get_work_files_changes()

resource.checkout()
resource.set_lock(True)
resource.commit("very first time")

raise SystemExit(0)
resource.trash_work()