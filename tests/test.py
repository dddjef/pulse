from pulse.api import *
import unittest
import os
import config as cfg

test_project_name = "test"


class TestBasic(unittest.TestCase):
    def setUp(self):
        cfg.reset_test_data()
        self.cnx = Connection(adapter="json_db", path=cfg.json_db_path)
        self.cnx.add_repository(name="local_test_storage", adapter="file_storage", path=cfg.file_storage_path)
        self.prj = self.cnx.create_project(
            test_project_name,
            cfg.sandbox_work_path,
            default_repository="local_test_storage",
            product_user_root=cfg.sandbox_products_path
        )

    def test_delete_project(self):
        anna_mdl = self.prj.create_resource("anna", "mdl")
        anna_mdl_work = anna_mdl.checkout()
        anna_mdl_work.create_product("abc")
        anna_mdl_work.commit()
        self.cnx.delete_project(test_project_name)
        with self.assertRaises(PulseDatabaseMissingObject):
            self.cnx.get_project(test_project_name)

    def test_template_resource(self):
        template_mdl = self.prj.create_template("mdl")
        template_mdl_work = template_mdl.checkout()
        template_mdl_work.create_product("abc")
        template_mdl_work.commit()
        template_mdl_work.trash()
        anna_mdl = self.prj.create_resource("anna", "mdl")
        anna_mdl_work = anna_mdl.checkout()
        self.assertTrue(os.path.exists(os.path.join(anna_mdl_work.get_products_directory(), "abc")))

    def test_unused_time_on_purged_product(self):
        anna_mdl = self.prj.create_resource("anna", "mdl")
        anna_mdl_work = anna_mdl.checkout()
        anna_mdl_work.create_product("abc")
        anna_mdl_v1 = anna_mdl_work.commit()
        anna_mdl_work.trash()
        self.prj.purge_unused_user_products()
        product = anna_mdl_v1.get_product("abc")
        self.assertTrue(product.get_unused_time(), -1)

    def test_same_work_and_product_user_path(self):
        cnx = Connection(adapter="json_db", path=cfg.json_db_path)
        prj = cnx.create_project(
            "project_simple_sandbox",
            cfg.sandbox_work_path,
            default_repository="local_test_storage"
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
        anna_mdl = self.prj.create_resource("anna", "mdl")
        anna_mdl_work = anna_mdl.checkout()
        anna_mdl_v1_abc = anna_mdl_work.create_product("abc")
        anna_mdl_work.trash()
        self.prj.purge_unused_user_products()
        anna_surf_work = self.prj.create_resource("anna", "surfacing").checkout()
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
        anna_mdl = self.prj.create_resource("anna", "mdl")
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
        res_mdl = self.prj.create_resource("res", "mdl")
        res_mdl.set_lock(True, "another_user")
        res_work = res_mdl.checkout()
        with self.assertRaises(PulseError):
            res_work.commit()

    def test_check_out_from_another_resource(self):
        shader_work_file = "shader_work_file.ma"
        shader_product_file = "shader_product_file.ma"
        template_resource = self.prj.create_resource("template", "surface")
        template_work = template_resource.checkout()
        cfg.add_file_to_directory(template_work.directory, shader_work_file)
        shader_product = template_work.create_product("shader")
        cfg.add_file_to_directory(shader_product.directory, shader_product_file)
        template_work.commit()

        anna_shd_resource = self.prj.create_resource("ch_anna", "surface", source_resource=template_resource)
        anna_shd_work = anna_shd_resource.checkout()
        self.assertTrue(os.path.exists(os.path.join(anna_shd_work.directory, shader_work_file)))
        self.assertTrue(os.path.exists(os.path.join(anna_shd_work.get_product("shader").directory,
                                                    shader_product_file)))

    def test_trashing_work_errors(self):
        anna_mdl_work = self.prj.create_resource("anna", "mdl").checkout()
        anna_mdl_abc = anna_mdl_work.create_product("abc")
        anna_surf_work = self.prj.create_resource("anna", "surfacing").checkout()
        anna_surf_work.add_input(anna_mdl_abc)
        with self.assertRaises(PulseError):
            anna_mdl_work.trash()
        anna_surf_work.trash()
        anna_mdl_work.trash()

    def test_recursive_dependencies_download(self):
        anna_surf_resource = self.prj.create_resource("ch_anna", "surfacing")
        anna_surf_work = anna_surf_resource.checkout()
        anna_surf_textures = anna_surf_work.create_product("textures")
        open(anna_surf_textures.directory + "\\product_file.txt", 'a').close()
        anna_surf_work.commit(comment="test generated product")
        anna_rig_resource = self.prj.create_resource("ch_anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_actor = anna_rig_work.create_product("actor_anim")
        anna_rig_actor.add_input(anna_surf_textures)
        anna_rig_work.commit()
        anna_rig_work.trash()
        anna_surf_work.trash()
        self.prj.purge_unused_user_products()
        self.assertFalse(os.path.exists(anna_surf_textures.directory))
        anim_resource = self.prj.create_resource("sh003", "anim")
        anim_work = anim_resource.checkout()
        anim_work.add_input(anna_rig_actor)
        self.assertTrue(os.path.exists(anna_surf_textures.directory))

    def test_work_cannot_commit_with_unpublished_inputs(self):
        anna_surf_resource = self.prj.create_resource("ch_anna", "surfacing")
        anna_surf_work = anna_surf_resource.checkout()
        anna_surf_textures = anna_surf_work.create_product("textures")
        product_folder = anna_surf_textures.directory
        open(product_folder + "\\product_file.txt", 'a').close()
        anna_rig_resource = self.prj.create_resource("ch_anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_work.add_input(anna_surf_textures)
        with self.assertRaises(PulseError):
            anna_rig_work.commit()

    def test_complete_scenario(self):
        # create a resource based on this template
        anna_mdl_resource = self.prj.create_resource("ch_anna", "modeling")
        self.assertEqual(anna_mdl_resource.last_version, 0)

        # checkout, and check directories are created
        anna_mdl_work = anna_mdl_resource.checkout()
        self.assertTrue(os.path.exists(anna_mdl_work.directory))
        # by default products should not exists
        self.assertFalse(os.path.exists(anna_mdl_work.get_products_directory()))

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
        # now products directory should exists
        self.assertTrue(os.path.exists(anna_mdl_work.get_products_directory()))
        open(anna_mdl_v2_abc.directory + "\\test.abc", 'a').close()
        # create a new commit
        anna_mdl_work.commit("some abc produced")
        self.assertEqual(anna_mdl_resource.last_version, 2)
        # create a new resource
        hat_mdl_resource = self.prj.create_resource("hat", "modeling")
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
        self.prj.purge_unused_user_products()
        # checkout the work
        hat_mdl_work = hat_mdl_resource.checkout()
        hat_mdl_work.remove_input(anna_mdl_v2_abc)
        anna_mdl_work.trash()

    def test_work_subdirectories_are_commit(self):
        subdirectory_name = "subdirtest"
        # create a resource based on this template
        anna_mdl_resource = self.prj.create_resource("ch_anna", "modeling")
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

    def test_get_unknown_resource_index(self):
        template_mdl = self.prj.create_template("mdl")
        template_mdl_work = template_mdl.checkout()
        template_mdl_work.create_product("abc")
        template_mdl_work.commit()
        template_mdl_work.trash()
        # test get an unknown tag raise a pulseError
        with self.assertRaises(PulseError):
            template_mdl.get_index("anytag")


if __name__ == '__main__':
    unittest.main()
