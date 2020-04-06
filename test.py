from pulse.api import *
import unittest
import string
import random

# TODO : unhandled error on missing resource type
# TODO : test starting from another resource than template
# TODO : test trashing an open file


def reset_files():
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

    print "FILES RESETED"


class TestBasic(unittest.TestCase):

    def setUp(self):
        reset_files()
        letters = string.ascii_lowercase
        random_name = ''.join(random.choice(letters) for i in range(10))
        resource_type = "modeling"
        self.uri_template = TEMPLATE_NAME + "-" + resource_type
        self.uri_test = "ch_anna" + "-" + resource_type
        self.uri_rand = random_name + "-" + resource_type

    @unittest.skip("demonstrating skipping")
    def test_exceptions_resource(self):
        # test resource without template
        with self.assertRaises(Exception):
            create_resource(self.uri_test)
        # TODO : test resource with mis formed uri
        # test create an existing resource
        create_resource(self.uri_template)
        create_resource(self.uri_test)
        with self.assertRaises(Exception):
            create_resource(self.uri_test)
        # TODO : test get missing resource

    def test_complete_scenario(self):
        # create a new template resource
        template = uri_to_object(self.uri_template)
        template.initialize_data()
        # checkout the template to edit it and save it
        work = template.checkout()
        open(work.directory + "\\template_work.txt", 'a').close()
        work.commit()
        # create a resource based on this template
        anna_mdl_resource = uri_to_object("ch_anna-modeling").initialize_data()
        self.assertEqual(anna_mdl_resource.last_version, 0)

        # checkout, and check directories are created
        anna_mdl_work = anna_mdl_resource.checkout()
        self.assertTrue(os.path.exists(anna_mdl_work.directory))
        self.assertTrue(os.path.exists(anna_mdl_work.get_products_directory()))
        # should have no change
        self.assertEqual(anna_mdl_work.get_files_changes(), [])
        # commit should failed, since there's no change
        with self.assertRaises(PulseError):
            anna_mdl_work.commit("very first time")
        # create a new file in work directory and try to commit again
        new_file = "\\test_complete.txt"
        open(anna_mdl_work.directory + new_file, 'a').close()
        self.assertEqual(anna_mdl_work.get_files_changes(), [(new_file, 'added')])
        anna_mdl_work.commit("very first time")
        self.assertEqual(anna_mdl_resource.last_version, 1)

        # create a product
        abc_dir = anna_mdl_work.get_products_directory() + "\\ABC"
        os.mkdir(abc_dir)
        open(abc_dir + "\\test.abc", 'a').close()
        # create a new commit
        anna_mdl_v2 = anna_mdl_work.commit("some abc produced")
        self.assertEqual(anna_mdl_resource.last_version, 2)
        # create a new resource
        hat_mdl_resource = uri_to_object("hat-modeling").initialize_data()
        self.assertEqual(hat_mdl_resource.last_version, 0)
        hat_mdl_work = hat_mdl_resource.checkout()

        hat_mdl_work.add_product_input(anna_mdl_resource, 2, "ABC")
        # test the product registration
        hat_mdl_work.read()
        self.assertEqual(hat_mdl_work.products_inputs[0], "ch_anna-modeling-ABC@2")
        anna_mdl_v2_abc = anna_mdl_v2.get_product("ABC")
        # check the work registration to product
        self.assertTrue(hat_mdl_work.directory in anna_mdl_v2_abc.get_work_users())
        # check you can't remove a product if it's used by a work
        with self.assertRaises(Exception):
            anna_mdl_v2_abc.remove_from_user_products()

        hat_mdl_work.commit("with input")
        self.assertEqual(hat_mdl_resource.last_version, 1)
        # trash the hat

        hat_mdl_work.trash()
        self.assertTrue(hat_mdl_work.directory not in anna_mdl_v2_abc.get_work_users())
        # check the unused time for the product
        self.assertTrue(anna_mdl_v2_abc.get_unused_time() > 0)
        # remove the product
        purge_unused_user_products()
        # checkout the work
        hat_mdl_work = hat_mdl_resource.checkout()
        hat_mdl_work.remove_product_inputs(anna_mdl_resource, 2, "ABC")
        anna_mdl_work.trash()


        # resource.set_lock(True)
        #
        # print "============  commit"
        # work.commit("very first time")


if __name__ == '__main__':
    unittest.main()
