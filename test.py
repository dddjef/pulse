from pulse.api import *
import unittest
import string
import random

# TODO : unhandled error on missing resource type


class TestBasic(unittest.TestCase):
    def setUp(self):
        letters = string.ascii_lowercase
        random_name = ''.join(random.choice(letters) for i in range(10))
        resource_type = "riggingc"
        self.uri_test = "test" + "-" + resource_type
        self.uri_rand = random_name + "-" + resource_type

    def test_create_resource_with_existing_type(self):
        resource = create_resource(self.uri_rand)
        self.assertEqual(resource.last_version, 0)

    def test_get_existing_resource(self):
        resource = get_resource(self.uri_test)
        self.assertTrue(resource.last_version >= 0)

    # TODO : add cleanup functions
    def test_complete_scenario(self):
        self.assertEqual(create_resource(self.uri_rand).last_version, 0)
        resource = get_resource(self.uri_rand)
        self.assertTrue(resource.last_version >= 0)
        work = resource.checkout()

        # check directories are created
        self.assertTrue(os.path.exists(work.directory))
        self.assertTrue(os.path.exists(work.get_products_directory()))
        # should have no change
        self.assertEqual(work.get_files_changes(), [])
        # commit should failed, since there's no change
        self.assertEqual(work.commit("very first time"), None)
        # create a new file in work directory and try to commit again
        new_file ="\\test_complete.txt"
        open( work.directory + new_file, 'a').close()
        self.assertEqual(work.get_files_changes(), [(new_file, 'added')])
        work.commit("very first time")
        self.assertEqual(resource.last_version, 1)


        # resource.set_lock(True)
        #
        # print "============  commit"
        # work.commit("very first time")
        self.assertEqual(work.trash(), True)


if __name__ == '__main__':
    unittest.main()
