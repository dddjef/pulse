from pulse.api import *
from pulse.repository_adapters.interface_class import *
import unittest
import os
import utils
import sys
test_project_name = "test"


class TestProjectSettings(unittest.TestCase):
    def setUp(self):
        utils.reset_test_data()
        self.cnx = Connection(adapter="json_db", path=utils.json_db_path)
        self.cnx.add_repository(name="local_test_storage", adapter="file_storage", path=utils.file_storage_path)

    def test_same_user_work_and_product_directory(self):
        prj = self.cnx.create_project(
            project_name=test_project_name,
            work_user_root=utils.sandbox_work_path,
            default_repository="local_test_storage"
        )
        resource = prj.create_resource("ch_anna", "model")
        work = resource.checkout()
        abc_product = work.create_product("abc")
        utils.add_file_to_directory(abc_product.directory, filename="model.abc")
        # check the work status don't list the product twice
        self.assertTrue(len(work.status()) == 1)
        # check when the work is trashed and there's a commit product, the commit product stay
        work.commit()
        utils.add_file_to_directory(work.directory, filename="change.blend")
        work_subfolder = os.path.join(work.directory, "subfolder")
        os.makedirs(work_subfolder)
        work.commit()
        work.trash()
        self.assertTrue(os.path.exists(abc_product.directory))
        self.assertFalse(os.path.exists(work_subfolder))
        # check the purge_unused_product delete the work directory
        prj.purge_unused_user_products()
        self.assertFalse(os.path.exists(work.directory))
        # check the previous commit product are not uploaded again when the work is commit
        work = resource.checkout()
        utils.add_file_to_directory(work.directory, filename="change_two.blend")
        self.assertTrue(len(work.status()) == 1)

    def test_environment_variables_in_project_path(self):
        # set up env var
        os.environ['PULSE_TEST'] = utils.test_data_output_path
        # create a project which use this variables in its work and product path
        prj = self.cnx.create_project(
            "env_var",
            "$PULSE_TEST/works",
            product_user_root="$PULSE_TEST/products",
            default_repository="local_test_storage"
        )
        # create a resource
        resource = prj.create_resource("ch_anna", "model")
        # check out the resource
        work = resource.checkout()
        # test its location
        self.assertTrue(os.path.exists(os.path.join(utils.test_data_output_path, "works/env_var/ch_anna-model")))
        # add an output product
        abc_product = work.create_product("abc")
        # test the product folder location
        self.assertTrue(
            os.path.exists(os.path.join(utils.test_data_output_path, "products/env_var/ch_anna-model/V001/abc")))
        # commit
        utils.add_file_to_directory(work.directory)
        work.commit()
        # trash
        work.trash(no_backup=True)
        prj.purge_unused_user_products()
        self.assertFalse(os.path.exists(os.path.join(
            utils.test_data_output_path,
            "works/env_var/ch_anna/model/V001/abc"
        )))
        # create another resource
        surf_resource = prj.create_resource("ch_anna", "surfacing")
        surf_work = surf_resource.checkout()
        # require this product
        surf_work.add_input(abc_product)
        # test the product location
        self.assertTrue(os.path.exists(os.path.join(
            utils.test_data_output_path,
            "products/env_var/ch_anna-model/V001/abc"
        )))

    def test_bad_repository_settings(self):
        # use backslash as path separator
        repo_path = utils.file_storage_path.replace("/", "\\")
        with self.assertRaises(PulseRepositoryError):
            self.cnx.add_repository(name="bad_path", adapter="file_storage", path=repo_path)
        if sys.platform == "win32":
            with self.assertRaises(WindowsError):
                self.cnx.add_repository(name="bad_path", adapter="file_storage", path="its:/invalid/path")


class TestResources(unittest.TestCase):
    def setUp(self):
        utils.reset_test_data()
        self.cnx = Connection(adapter="json_db", path=utils.json_db_path)
        self.cnx.add_repository(name="main_storage", adapter="file_storage", path=utils.file_storage_path)
        self.prj = self.cnx.create_project(
            test_project_name,
            utils.sandbox_work_path,
            default_repository="main_storage",
            product_user_root=utils.sandbox_products_path
        )
        self._initResource()

    def _initResource(self):
        self.anna_mdl = self.prj.create_resource("anna", "mdl")
        self.anna_mdl_work = self.anna_mdl.checkout()
        utils.add_file_to_directory(self.anna_mdl_work.directory, "work.blend")
        self.anna_abc_product = self.anna_mdl_work.create_product("abc")
        utils.add_file_to_directory(self.anna_abc_product.directory, "anna.abc")
        self.anna_mdl_commit = self.anna_mdl_work.commit()

    def test_delete_project(self):
        self.cnx.delete_project(test_project_name)
        with self.assertRaises(PulseError):
            self.cnx.get_project(test_project_name)

    def test_template_resource(self):
        template_mdl = self.prj.create_template("mdl")
        template_mdl_work = template_mdl.checkout()
        template_mdl_work.create_product("abc")
        utils.add_file_to_directory(template_mdl_work.directory)
        template_mdl_work.commit()
        template_mdl_work.trash()
        froga_mdl = self.prj.create_resource("froga", "mdl")
        froga_mdl_work = froga_mdl.checkout()
        self.assertTrue(os.path.exists(os.path.join(froga_mdl_work.get_products_directory(), "abc")))

    def test_unused_time_on_purged_product(self):
        self.anna_mdl_work.trash()
        self.prj.purge_unused_user_products()
        product = self.anna_mdl_commit.get_product("abc")
        self.assertTrue(product.get_unused_time(), -1)

    def test_manipulating_trashed_work(self):
        wip_product = self.anna_mdl_work.create_product("wip")
        self.anna_mdl_work.trash()
        self.prj.purge_unused_user_products()
        anna_surf_work = self.prj.create_resource("anna", "surfacing").checkout()
        # add a trashed product
        with self.assertRaises(PulseError):
            anna_surf_work.add_input(wip_product)
        # create product on a trashed work
        with self.assertRaises(PulseMissingNode):
            self.anna_mdl_work.create_product("abc")
        # commit a trashed work
        with self.assertRaises(PulseMissingNode):
            self.anna_mdl_work.commit()

    def test_trash_product(self):
        wip_product = self.anna_mdl_work.create_product("wip")
        self.anna_mdl_work.trash_product("wip")
        self.assertFalse(os.path.exists(wip_product.directory))

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
        self.anna_mdl.set_lock(True, "another_user")
        res_work = self.anna_mdl.checkout()
        with self.assertRaises(PulseError):
            res_work.commit()

    def test_check_out_from_template(self):
        #if no template exists
        resource = self.prj.create_resource("joe", "surface")
        resource.checkout()

        #if a template exists, but without any version
        self.prj.create_template("rig")
        resource = self.prj.create_resource("joe", "rig")
        resource.checkout()

        #if the template exists
        template = self.prj.create_template("shapes")
        template_work = template.checkout()
        utils.add_file_to_directory(template_work.directory)
        template_work.commit()

        resource = self.prj.create_resource("joe", "shapes")
        resource.checkout()

    def test_check_out_from_another_resource(self):
        shader_work_file = "shader_work_file.ma"
        shader_product_file = "shader_product_file.ma"
        source_resource = self.prj.create_resource("source", "surface")
        source_work = source_resource.checkout()
        utils.add_file_to_directory(source_work.directory, shader_work_file)
        source_product = source_work.create_product("shader")
        utils.add_file_to_directory(source_product.directory, shader_product_file)
        source_work.commit()

        anna_shd_resource = self.prj.create_resource("ch_anna", "surface", source_resource=source_resource)
        anna_shd_work = anna_shd_resource.checkout()
        self.assertTrue(os.path.exists(os.path.join(anna_shd_work.directory, shader_work_file)))
        self.assertTrue(os.path.exists(os.path.join(anna_shd_work.get_product("shader").directory,
                                                    shader_product_file)))

    def test_trashing_work_errors(self):
        froga_mdl_work = self.prj.create_resource("froga", "mdl").checkout()
        froga_mdl_abc = froga_mdl_work.create_product("abc")
        anna_surf_work = self.prj.create_resource("anna", "surfacing").checkout()
        anna_surf_work.add_input(froga_mdl_abc)
        # trashing a wip work with a product used by another resource is forbidden
        with self.assertRaises(PulseError):
            froga_mdl_work.trash()
        # trashing a wip product used by another resource is forbidden
        with self.assertRaises(PulseError):
            froga_mdl_work.trash_product("abc")

        # trashing a commit work with a product used by another resource is allowed

        # TODO : when this product is added, it's still a work product. Then its data path is wrong
        anna_surf_work.add_input(self.anna_abc_product)
        self.anna_mdl_work.trash()

        # trashing first the product user, then the product is allowed
        anna_surf_work.trash()
        froga_mdl_work.trash()

    def test_work_dependencies_download(self):
        anna_surf_resource = self.prj.create_resource("ch_anna", "surfacing")
        anna_surf_work = anna_surf_resource.checkout()
        anna_surf_textures = anna_surf_work.create_product("textures")
        utils.add_file_to_directory(anna_surf_textures.directory, "product_file.txt")
        anna_surf_work.commit(comment="test generated product")
        anna_rig_resource = self.prj.create_resource("ch_anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_work.add_input(anna_surf_textures)
        anna_rig_work.commit("comment test")
        anna_rig_work.trash()
        anna_surf_work.trash()
        self.prj.purge_unused_user_products()
        self.assertFalse(os.path.exists(anna_surf_textures.directory))
        rig_v01 = anna_rig_resource.get_commit(1)
        self.assertEqual(rig_v01.products_inputs[0], 'ch_anna-surfacing.textures@1')
        anna_rig_resource.checkout()
        self.assertTrue(os.path.exists(anna_surf_textures.directory))

    def test_recursive_dependencies_download(self):
        anna_surf_resource = self.prj.create_resource("ch_anna", "surfacing")
        anna_surf_work = anna_surf_resource.checkout()
        anna_surf_textures = anna_surf_work.create_product("textures")
        utils.add_file_to_directory(anna_surf_textures.directory, "product_file.txt")
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

        # commit should fail if nothing is change in work
        with self.assertRaises(PulseError):
            anna_mdl_work.commit("very first time")

        # create a new file in work directory and try to commit again
        new_file = "test_complete.txt"
        utils.add_file_to_directory(anna_mdl_work.directory, new_file)
        self.assertEqual(anna_mdl_work.status(), {"/" + new_file: 'added'})

        anna_mdl_work.commit("add a file")
        self.assertEqual(anna_mdl_resource.last_version, 1)

        # create a product
        anna_mdl_v2_abc = anna_mdl_work.create_product("ABC")
        # now products directory should exists
        self.assertTrue(os.path.exists(anna_mdl_work.get_products_directory()))
        utils.add_file_to_directory(anna_mdl_v2_abc.directory, "test.abc")
        # create a new commit
        anna_mdl_work.commit("some abc produced")
        self.assertEqual(anna_mdl_resource.last_version, 2)
        # create a new resource
        hat_mdl_resource = self.prj.create_resource("hat", "modeling")
        self.assertEqual(hat_mdl_resource.last_version, 0)
        hat_mdl_work = hat_mdl_resource.checkout()

        hat_mdl_work.add_input(anna_mdl_v2_abc)
        # test the product registration
        self.assertEqual(hat_mdl_work.get_inputs()[0].uri, "ch_anna-modeling.ABC@2")
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

    def test_work_commit(self):
        # test subdirectories are commit
        subdirectory_name = "subdirectory_test"
        work_subdir_path = os.path.join(self.anna_mdl_work.directory, subdirectory_name)
        os.makedirs(work_subdir_path)
        open(work_subdir_path + "\\subdir_file.txt", 'a').close()
        self.anna_mdl_work.commit()
        self.anna_mdl_work.trash()
        self.assertFalse(os.path.exists(self.anna_mdl_work.directory))
        self.anna_mdl.checkout()
        self.assertTrue(os.path.exists(work_subdir_path + "\\subdir_file.txt"))

    def test_get_unknown_resource_index(self):
        # test get an unknown tag raise a pulseError
        with self.assertRaises(PulseError):
            self.anna_mdl.get_index("any_tag")

    def test_work_get_file_changes(self):
        # test nothing is returned if nothing change
        self.assertTrue(self.anna_mdl_work.status() == {})
        # test nothing is returned if only the modification date change
        # test nothing is returned if only a empty directory is added
        # test edited file is returned when a work file is changed
        # test edited file is returned when a product file is changed
        # test added is returned when a new file is added
        # test removed is returned when a file is deleted

    def test_work_revert(self):
        # make some change in the work folder
        utils.add_file_to_directory(self.anna_mdl_work.directory)
        with open(os.path.join(self.anna_mdl_work.directory, "work.blend"), "a") as work_file:
            work_file.write("something")
        # test there's changes
        self.assertTrue(len(self.anna_mdl_work.status()) == 2)
        self.anna_mdl_work.revert()
        # test there's no more changes
        self.assertTrue(len(self.anna_mdl_work.status()) == 0)

    def test_work_update(self):
        # commit a new version (2), and trash it
        utils.add_file_to_directory(self.anna_mdl_work.directory, "new_file.txt")
        self.anna_mdl_work.commit()
        self.anna_mdl_work.trash()
        # checkout to version 1, and test the new file is not there
        work = self.anna_mdl.checkout(index=1)
        self.assertFalse(os.path.exists(os.path.join(self.anna_mdl_work.directory, "new_file.txt")))
        # update the work, check the new file is there
        time.sleep(1)
        work.update()
        self.assertTrue(os.path.exists(os.path.join(self.anna_mdl_work.directory, "new_file.txt")))
        # change the work file, test the update will raise an error
        utils.add_file_to_directory(self.anna_mdl_work.directory, "new_file2.txt")
        with self.assertRaises(PulseError):
            work.update()

    def test_work_status(self):
        # test new work file is reported, even in subdirectory
        utils.add_file_to_directory(self.anna_mdl_work.directory, "new_file.txt")
        # test new product files are reported, even in subdirectory
        subdir_path = os.path.join(self.anna_mdl_work.directory, "subdir")
        os.makedirs(subdir_path)
        utils.add_file_to_directory(subdir_path, "subfile.txt")
        # test work file edit are reported
        with open(os.path.join(self.anna_mdl_work.directory, "work.blend"), 'a') as f:
            f.write("another_line")
        self.assertEqual(self.anna_mdl_work.status(), {
            '/new_file.txt': 'added',
            '/subdir/subfile.txt': 'added',
            '/work.blend': 'edited'
        })
        # test work file deletion is reported
        os.remove(os.path.join(self.anna_mdl_work.directory, "work.blend"))
        self.assertEqual(self.anna_mdl_work.status(), {
            '/new_file.txt': 'added',
            '/subdir/subfile.txt': 'added',
            '/work.blend': 'removed'
        })

    def test_work_trash(self):
        product = self.anna_mdl_work.create_product("abc")
        utils.add_file_to_directory(product.directory, "product_file.txt")
        # test trash work and its wip product
        self.anna_mdl_work.trash()
        self.assertFalse(os.path.exists(product.directory))
        self.assertFalse(os.path.exists(self.anna_mdl_work.directory))
        self.assertFalse(os.path.exists(product.product_users_file))

    def test_work_commit_data(self):
        anna_rig_resource = self.prj.create_resource("anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        utils.add_file_to_directory(anna_rig_work.directory, "work_file.txt")
        anna_rig_work.commit()
        commit = anna_rig_resource.get_commit("last")
        self.assertEqual(list(commit.files.keys())[0], '/work_file.txt')

    def test_product_trash(self):
        anna_rig_resource = self.prj.create_resource("anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_actor = anna_rig_work.create_product("actor_anim")
        anna_rig_actor.add_input(self.anna_abc_product)
        anna_rig_work.trash_product("actor_anim")

    def test_product_download(self):
        self.anna_mdl_work.trash()
        self.prj.purge_unused_user_products()
        product = self.prj.get_product("anna-mdl.abc@1")
        self.assertFalse(os.path.exists(product.directory))
        self.assertFalse(os.path.exists(product.product_users_file))
        product.download()
        self.assertTrue(os.path.exists(product.directory))
        self.assertTrue(os.path.exists(product.product_users_file))
        product.remove_from_user_products()
        self.assertFalse(os.path.exists(product.directory))
        self.assertFalse(os.path.exists(product.product_users_file))

    def test_project_list_products(self):
        anna_rig_resource = self.prj.create_resource("anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_actor = anna_rig_work.create_product("actor_anim")
        anna_rig_actor.add_input(self.anna_abc_product)
        anna_rig_work.commit()
        self.assertTrue(len(self.prj.list_products("anna*")) == 2)
        self.assertTrue(len(self.prj.list_products("an?a*")) == 2)

    def test_project_list_works(self):
        anna_rig_resource = self.prj.create_resource("anna", "rigging")
        anna_rig_resource.checkout()
        self.assertEqual(self.prj.get_local_works(), ['anna-mdl', 'anna-rigging'])

if __name__ == '__main__':
    unittest.main()
