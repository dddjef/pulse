from pulse.api import *


#### generate random entity name
import string
import random
letters = string.ascii_lowercase
entity_name = ''.join(random.choice(letters) for i in range(10))
entity_name = "fixedAH"


uri_test = entity_name + "-modeling"
create_resource(uri_test)
resource = get_resource(uri_test)
work = resource.checkout()
print work.get_files_changes()
resource.set_lock(True)
work.commit("very first time")
# work.trash()


# resource.trash_work()