from pulse.api import *
import unittest
import os

# TODO : test trashing an open file

test_dir = os.path.dirname(__file__)
db_root = os.path.join(test_dir, "DB")
user_works = os.path.join(test_dir, "works")
user_products = os.path.join(test_dir, "products")
repos = os.path.join(test_dir, "repos")


def reset_files():
    for directory in [db_root, user_products, user_works, repos]:
        if not os.path.exists(directory):
            continue
        for path, subdirs, files in os.walk(directory):
            for name in files:
                filepath = os.path.join(path, name)
                if filepath.endswith(".pipe"):
                    os.chmod(filepath, 0o777)
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
    cnx = Connection(db_root)
    print repos
    prj = cnx.create_project(
        prj_name,
        user_works,
        repository_url=os.path.join(repos, "default"),
        product_user_root=user_products,

    )
    return cnx, prj


def add_file_to_directory(directory, filename, source_filepath=None):
    if not source_filepath:
        open(os.path.join(directory, filename), 'a').close()


class TestBasic(unittest.TestCase):
    def setUp(self):
        reset_files()

    # def tearDown(self):
    #     reset_files()

    def test_template_resource(self):
        cnx, prj = create_test_project()
        template_mdl = prj.create_template("mdl")
        template_mdl_work = template_mdl.checkout()
        template_mdl_work.create_product("abc")
        template_mdl_v1 = template_mdl_work.commit()
        template_mdl_work.trash()
        anna_mdl = prj.create_resource("anna", "mdl")
        anna_mdl_work = anna_mdl.checkout()
        self.assertTrue(os.path.exists(os.path.join(anna_mdl_work.get_products_directory(), "abc")))


    def test_unused_time_on_purged_product(self):
        cnx, prj = create_test_project()
        anna_mdl = prj.create_resource("anna", "mdl")
        anna_mdl_work = anna_mdl.checkout()
        anna_mdl_work.create_product("abc")
        anna_mdl_v1 = anna_mdl_work.commit()
        anna_mdl_work.trash()
        prj.purge_unused_user_products()
        product = anna_mdl_v1.get_product("abc")
        self.assertTrue(product.get_unused_time(), -1)

    def test_same_work_and_product_user_path(self):
        cnx = Connection(db_root)
        prj = cnx.create_project(
            "project_simple_sandbox",
            user_works,
            repository_url=os.path.join(repos, "default")
        )
        mdl_res = prj.create_resource("anna", "mdl")
        mdl_work = mdl_res.checkout()
        mdl_work.create_product("abc")
        mdl_v1 = mdl_work.commit()
        abc = mdl_v1.get_product("abc")
        surf_work = prj.create_resource("anna", "surf").checkout()
        surf_work.add_input(abc)
        mdl_work.trash()

    def test_manipulating_trashed_work(self):
        cnx, prj = create_test_project()
        anna_mdl = prj.create_resource("anna", "mdl")
        anna_mdl_work = anna_mdl.checkout()
        anna_mdl_v1_abc = anna_mdl_work.create_product("abc")
        anna_mdl_work.trash()
        prj.purge_unused_user_products()
        anna_surf_work = prj.create_resource("anna", "surfacing").checkout()
        # add a trashed product
        with self.assertRaises(PulseMissingNode):
            anna_surf_work.add_input(anna_mdl_v1_abc)
        # create product on a trashed work
        with self.assertRaises(PulseMissingNode):
            anna_mdl_work.create_product("abc")
        # commit a trashed work
        with self.assertRaises(PulseMissingNode):
            anna_mdl_work.commit()

    def test_trash_product(self):
        cnx, prj = create_test_project()
        anna_mdl = prj.create_resource("anna", "mdl")
        anna_mdl_work = anna_mdl.checkout()
        abc_product = anna_mdl_work.create_product("abc")
        anna_mdl_work.trash_product("abc")
        self.assertFalse(os.path.exists(abc_product.directory))

    def test_metadata(self):
        pass
        # cnx, prj = create_test_project()
        # anna_mdl_resource = prj.get_pulse_node("ch_anna-modeling")
        # anna_mdl_resource.metas = {"site": "Paris"}
        # anna_mdl_resource.initialize_data()
        # prj = cnx.get_project(prj.name)
        # res = prj.get_pulse_node("ch_anna-modeling")
        # res.read_data()
        # self.assertTrue(res.metas["site"] == "Paris")

    def test_lock_resource(self):
        cnx, prj = create_test_project()
        res_mdl = prj.create_resource("res", "mdl")
        res_mdl.set_lock(True, "another_user")
        res_work = res_mdl.checkout()
        with self.assertRaises(PulseError):
            res_work.commit()

    def test_check_out_from_another_resource(self):
        shader_work_file = "shader_work_file.ma"
        shader_product_file = "shader_product_file.ma"
        cnx, prj = create_test_project()
        template_resource = prj.create_resource("template", "surface")
        template_work = template_resource.checkout()
        add_file_to_directory(template_work.directory, shader_work_file)
        shader_product = template_work.create_product("shader")
        add_file_to_directory(shader_product.directory, shader_product_file)
        template_work.commit()

        anna_shd_resource = prj.create_resource("ch_anna", "surface", source_resource=template_resource)
        anna_shd_work = anna_shd_resource.checkout()
        self.assertTrue(os.path.exists(os.path.join(anna_shd_work.directory, shader_work_file)))

        anna_shader_v1 = anna_shd_resource.get_commit(1).get_product("shader")
        anna_shader_v1.download()
        self.assertTrue(os.path.exists(os.path.join(anna_shader_v1.directory, shader_product_file)))

    def test_trashing_work_errors(self):
        cnx, prj = create_test_project()
        anna_mdl_work = prj.create_resource("anna", "mdl").checkout()
        anna_mdl_abc = anna_mdl_work.create_product("abc")
        anna_surf_work = prj.create_resource("anna", "surfacing").checkout()
        anna_surf_work.add_input(anna_mdl_abc)
        with self.assertRaises(PulseError):
            anna_mdl_work.trash()
        anna_surf_work.trash()
        anna_mdl_work.trash()

    def test_recursive_dependencies_download(self):
        cnx, prj = create_test_project()
        anna_surf_resource = prj.create_resource("ch_anna", "surfacing")
        anna_surf_work = anna_surf_resource.checkout()
        anna_surf_textures = anna_surf_work.create_product("textures")
        open(anna_surf_textures.directory + "\\product_file.txt", 'a').close()
        anna_surf_work.commit(comment="test generated product")
        anna_rig_resource = prj.create_resource("ch_anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_actor = anna_rig_work.create_product("actor_anim")
        anna_rig_actor.add_input(anna_surf_textures)
        anna_rig_work.commit()
        anna_rig_work.trash()
        anna_surf_work.trash()
        prj.purge_unused_user_products()
        self.assertFalse(os.path.exists(anna_surf_textures.directory))
        anim_resource = prj.create_resource("sh003", "anim")
        anim_work = anim_resource.checkout()
        anim_work.add_input(anna_rig_actor)
        self.assertTrue(os.path.exists(anna_surf_textures.directory))

    def test_work_cannot_commit_with_unpublished_inputs(self):
        cnx, prj = create_test_project()
        anna_surf_resource = prj.create_resource("ch_anna", "surfacing")
        anna_surf_work = anna_surf_resource.checkout()
        anna_surf_textures = anna_surf_work.create_product("textures")
        product_folder = anna_surf_textures.directory
        open(product_folder + "\\product_file.txt", 'a').close()
        anna_rig_resource = prj.create_resource("ch_anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_work.add_input(anna_surf_textures)
        with self.assertRaises(PulseError):
            anna_rig_work.commit()

    def test_complete_scenario(self):
        # create a connection
        cnx, prj = create_test_project()
        # create a resource based on this template
        anna_mdl_resource = prj.create_resource("ch_anna", "modeling")
        self.assertEqual(anna_mdl_resource.last_version, 0)

        # checkout, and check directories are created
        anna_mdl_work = anna_mdl_resource.checkout()
        self.assertTrue(os.path.exists(anna_mdl_work.directory))
        self.assertTrue(os.path.exists(anna_mdl_work.get_products_directory()))

        # commit should file if nothing is change in work
        with self.assertRaises(PulseError):
            anna_mdl_work.commit("very first time")

        # create a new file in work directory and try to commit again
        new_file = "\\test_complete.txt"
        open(anna_mdl_work.directory + new_file, 'a').close()
        self.assertEqual(anna_mdl_work.get_files_changes(), [(new_file, 'added')])

        anna_mdl_work.commit("add a file")
        self.assertEqual(anna_mdl_resource.last_version, 1)

        # create a product
        anna_mdl_v2_abc = anna_mdl_work.create_product("ABC")
        open(anna_mdl_v2_abc.directory + "\\test.abc", 'a').close()
        # create a new commit
        anna_mdl_work.commit("some abc produced")
        self.assertEqual(anna_mdl_resource.last_version, 2)
        # create a new resource
        hat_mdl_resource = prj.create_resource("hat", "modeling")
        self.assertEqual(hat_mdl_resource.last_version, 0)
        hat_mdl_work = hat_mdl_resource.checkout()

        hat_mdl_work.add_input(anna_mdl_v2_abc)
        # test the product registration
        self.assertEqual(hat_mdl_work.get_inputs()[0].uri, "ch_anna-modeling-ABC@2")
        # check the work registration to product

        self.assertTrue(hat_mdl_work.directory in anna_mdl_v2_abc.get_product_users())
        # check you can't remove a product if it's used by a work
        with self.assertRaises(Exception):
            anna_mdl_v2_abc.remove_from_user_products()

        hat_mdl_work.commit("with input")
        self.assertEqual(hat_mdl_resource.last_version, 1)
        # trash the hat

        hat_mdl_work.trash()
        self.assertTrue(hat_mdl_work.directory not in anna_mdl_v2_abc.get_product_users())
        # check the unused time for the product
        self.assertTrue(anna_mdl_v2_abc.get_unused_time() > 0)
        # remove the product
        prj.purge_unused_user_products()
        # checkout the work
        hat_mdl_work = hat_mdl_resource.checkout()
        hat_mdl_work.remove_input(anna_mdl_v2_abc)
        anna_mdl_work.trash()
        for nd in prj.list_products("*anna*"):
            print nd.uri

    def test_work_subdirectories_are_commit(self):
        subdirectory_name = "subdirtest"
        # create a connection
        cnx, prj = create_test_project()
        # create a resource based on this template
        anna_mdl_resource = prj.create_resource("ch_anna", "modeling")
        self.assertEqual(anna_mdl_resource.last_version, 0)

        # checkout, and check directories are created
        anna_mdl_work = anna_mdl_resource.checkout()
        work_subdir_path = os.path.join(anna_mdl_work.directory, subdirectory_name)
        os.makedirs(work_subdir_path)
        open(work_subdir_path + "\\subdir_file.txt", 'a').close()
        anna_mdl_work.commit()
        anna_mdl_work.trash()
        self.assertFalse(os.path.exists(anna_mdl_work.directory))
        anna_mdl_resource.checkout()
        self.assertTrue(os.path.exists(work_subdir_path + "\\subdir_file.txt"))


if __name__ == '__main__':
    unittest.main()
    reset_files()
