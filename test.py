from pulse.api import *
import unittest
import string
import random

# TODO : unhandled error on missing resource type
# TODO : test starting from another resource than template

class TestBasic(unittest.TestCase):
    def setUp(self):

        # start by a cleanup
        directories_to_clean = [
            r"D:\pipe\pulse\test\sandbox",
            r"D:\pipe\pulse\test\work_repository",
            r"D:\pipe\pulse\test\product_repository",
            r"D:\pipe\pulse\test\DB",
            r"D:\pipe\pulse\test\user_products",
            ]

        for directory in directories_to_clean:
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print('Failed to delete %s. Reason: %s' % (file_path, e))

        letters = string.ascii_lowercase
        random_name = ''.join(random.choice(letters) for i in range(10))
        resource_type = "modeling"
        self.uri_template = TEMPLATE_NAME + "-" + resource_type
        self.uri_test = "ch_anna" + "-" + resource_type
        self.uri_rand = random_name + "-" + resource_type

    def test_complete_scenario(self):
        # create a new template resource
        template = create_resource(self.uri_template)
        # checkout the template to edit it and save it
        work = template.checkout()
        open(work.directory + "\\template_work.txt", 'a').close()
        work.commit()
        # create a resource based on this template
        self.assertEqual(create_resource(self.uri_rand).last_version, 0)
        resource = get_resource(self.uri_rand)
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
