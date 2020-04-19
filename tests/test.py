from pulse.api import *
import unittest
import os

# TODO : unhandled error on missing resource type
# TODO : test starting from another resource than template
# TODO : test trashing an open file

test_dir = os.path.dirname(__file__)
db = os.path.join(test_dir, "DB")
user_works = os.path.join(test_dir, "works")
user_products = os.path.join(test_dir, "products")
repos = os.path.join(test_dir, "repos")


def reset_files():
    for directory in [db, user_products, user_works, repos]:
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


def create_test_project(prj_name="test"):
    cnx = Connection({"DB_root": db})
    prj = cnx.create_project(
        prj_name,
        user_works,
        user_products,
        repository_parameters={"root": os.path.join(repos, "default")}
    )
    create_template(prj, "surfacing")
    create_template(prj, "rigging")
    create_template(prj, "anim")
    return cnx, prj


def create_template(prj, template_type):
    template = prj.get_pulse_node(TEMPLATE_NAME + "-" + template_type).initialize_data()
    # checkout the template to edit it and save it
    work = template.checkout()
    open(work.directory + "\\template_work.txt", 'a').close()
    work.commit()
    work.trash()
    return template


class TestBasic(unittest.TestCase):
    def setUp(self):
        reset_files()

    def tearDown(self):
        reset_files()

    def test_metadata(self):
        cnx, prj = create_test_project()
        prj.get_pulse_node(TEMPLATE_NAME + "-modeling").initialize_data()
        # anna_mdl_resource = prj.get_pulse_node("ch_anna-modeling")
        # anna_mdl_resource.metas = {"site": "Paris"}
        # anna_mdl_resource.initialize_data()
        # prj = cnx.get_project(prj.name)
        # res = prj.get_pulse_node("ch_anna-modeling")
        # res.read_data()
        # self.assertTrue(res.metas["site"] == "Paris")

    def test_multiple_repository_types(self):
        cnx, prj = create_test_project()
        create_template(prj, "mdl")
        cnx = Connection({"DB_root": db})
        ftp_prj = cnx.create_project(
            "testFTP",
            user_works + "\\ftp",
            user_products + "\\ftp",
            repository_type="ftp_repo",
            repository_parameters={"root": repos}
        )
        create_template(ftp_prj, "mdl")

    def test_shot_scenario(self):
        cnx, prj = create_test_project()
        anna_surf_resource = prj.get_pulse_node("ch_anna-surfacing").initialize_data()
        anna_surf_work = anna_surf_resource.checkout()
        product_folder = anna_surf_work.initialize_product_directory("textures")
        open(product_folder + "\\product_file.txt", 'a').close()
        anna_surf_work.commit(comment="test generated product")
        anna_rig_resource = prj.get_pulse_node("ch_anna-rigging").initialize_data()
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_work.initialize_product_directory("actor_anim")
        anna_rig_work.add_product_input("actor_anim", "ch_anna-surfacing-textures@1")
        anna_rig_work.commit()
        anna_rig_work.trash()
        anna_surf_work.trash()
        prj.purge_unused_user_products()
        anim_resource = prj.get_pulse_node("sh003-anim").initialize_data()
        anim_work = anim_resource.checkout()
        anim_work.add_work_input("ch_anna-rigging-actor_anim@1")

    def test_complete_scenario(self):
        # create a connection
        cnx, prj = create_test_project()
        # create a new template resource
        create_template(prj, "modeling")
        # create a resource based on this template
        anna_mdl_resource = prj.get_pulse_node("ch_anna-modeling").initialize_data()
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
        hat_mdl_resource = prj.get_pulse_node("hat-modeling").initialize_data()
        self.assertEqual(hat_mdl_resource.last_version, 0)
        hat_mdl_work = hat_mdl_resource.checkout()

        hat_mdl_work.add_work_input("ch_anna-modeling-ABC@2")
        # test the product registration
        hat_mdl_work.read()
        self.assertEqual(hat_mdl_work.get_work_inputs()[0], "ch_anna-modeling-ABC@2")
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
        prj.purge_unused_user_products()
        # checkout the work
        hat_mdl_work = hat_mdl_resource.checkout()
        hat_mdl_work.remove_work_input("ch_anna-modeling-ABC@2")
        anna_mdl_work.trash()
        for nd in prj.list_nodes("Resource", "*anna*"):
            print nd.uri


if __name__ == '__main__':
    unittest.main()
    reset_files()
