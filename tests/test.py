from pulse.api import *
from pulse.repository_adapters.interface_class import *
import pulse.uri_standards as uri
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
        with self.assertRaises(PulseError):
            self.cnx.create_project(
                project_name=test_project_name,
                work_user_root=utils.sandbox_work_path,
                default_repository="local_test_storage",
                product_user_root=utils.sandbox_work_path
            )

        with self.assertRaises(PulseError):
            self.cnx.create_project(
                project_name=test_project_name,
                work_user_root=utils.sandbox_work_path,
                default_repository="local_test_storage",
                product_user_root=utils.sandbox_work_path + "/subdir"
            )

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
        work.create_product("abc")
        # test the product folder location
        self.assertTrue(
            os.path.exists(os.path.join(utils.test_data_output_path, "products/env_var/ch_anna-model/V001/abc")))
        # commit
        utils.add_file_to_directory(work.directory)
        commit = work.commit()
        abc_product = commit.get_product("abc")
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
        surf_work.add_input(abc_product.uri)
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

    def test_cfg_without_linked_directories(self):
        # set up env var
        # create a project which use this variables in its work and product path
        prj = self.cnx.create_project(
            test_project_name,
            utils.sandbox_work_path,
            default_repository="local_test_storage",
            product_user_root=utils.sandbox_products_path,
            use_linked_output_directory=False,
            use_linked_input_directories=False
        )
        # create a resource
        resource = prj.create_resource("ch_anna", "model")
        # check out the resource
        work = resource.checkout()
        # test there's no output directory
        self.assertFalse(os.path.exists(os.path.join(work.directory, "output")))
        # add an output product
        work.create_product("abc")
        # commit
        utils.add_file_to_directory(work.directory)
        commit = work.commit()
        abc_product = commit.get_product("abc")
        # trash
        work.trash(no_backup=True)
        prj.purge_unused_user_products()
        # create another resource
        surf_resource = prj.create_resource("ch_anna", "surfacing")
        surf_work = surf_resource.checkout()
        # require this product
        surf_work.add_input(abc_product.uri)
        # test the product location
        self.assertFalse(os.path.exists(os.path.join(surf_work.directory, "input")))
        surf_work.commit()


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
        self.anna_abc_work_product = self.anna_mdl_work.create_product("abc")
        utils.add_file_to_directory(self.anna_abc_work_product.directory, "anna.abc")
        self.anna_mdl_commit = self.anna_mdl_work.commit()
        self.anna_abc_product_v1 = self.prj.get_commit_product("anna-mdl.abc@1")

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

    def test_purged_product(self):
        # test the dry mode
        self.anna_abc_product_v1 = self.prj.get_commit_product("anna-mdl.abc@1")
        self.assertTrue(os.path.exists(self.anna_abc_product_v1.directory))
        self.assertEqual(self.prj.purge_unused_user_products(dry_mode=True), ['anna-mdl.abc@1'])
        self.assertTrue(os.path.exists(self.anna_abc_product_v1.directory))

        # test product currently in use can't be purged
        self.anna_surf = self.prj.create_resource("anna", "surfacing")
        self.anna_surf_work = self.anna_surf.checkout()
        self.anna_surf_work.add_input(self.anna_abc_product_v1.uri)
        self.assertEqual(self.prj.purge_unused_user_products(dry_mode=True), [])

        # test the normal mode
        self.anna_surf_work.trash()
        self.assertEqual(self.prj.purge_unused_user_products(dry_mode=False), ['anna-mdl.abc@1'])
        self.assertFalse(os.path.exists(self.anna_abc_product_v1.directory))

    def test_manipulating_trashed_work(self):
        wip_product = self.anna_mdl_work.create_product("wip")
        self.anna_mdl_work.trash()
        self.prj.purge_unused_user_products()
        anna_surf_work = self.prj.create_resource("anna", "surfacing").checkout()
        # add a trashed product
        with self.assertRaises(PulseDatabaseMissingObject):
            anna_surf_work.add_input(wip_product.uri)
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

    def test_checkout(self):
        # remove a work with a commit product
        self.anna_mdl_work.trash()
        self.prj.purge_unused_user_products()
        # ensure the product directory is missing
        self.assertFalse(os.path.exists(self.anna_abc_product_v1.directory))
        # checkout the resource again
        work = self.anna_mdl.checkout()
        # test the empty product has been restored
        product = work.get_product("abc")
        self.assertTrue(os.path.exists(product.directory))
        # test get a missing product raise an error
        with self.assertRaises(PulseError):
            work.get_product("abcd")

    def test_work_checkout_product_conflict(self):
        os.environ["USER_VAR"] = "userA"
        prj_a = self.cnx.create_project(
            "project_conflict",
            utils.sandbox_work_path + "_${USER_VAR}",
            default_repository="main_storage",
            product_user_root=utils.sandbox_products_path + "_${USER_VAR}"
        )

        # userA checkout a modeling, he creates a abc product in V001
        work_model_a = prj_a.create_resource("joe", "model").checkout()
        work_model_a.create_product("abc")

        # userB does the exact same thing, but he commits first
        os.environ["USER_VAR"] = "userB"
        proj_b = self.cnx.get_project("project_conflict")
        work_model_b = proj_b.get_resource("joe", "model").checkout()
        abc_product_b = work_model_b.create_product("abc")
        utils.add_file_to_directory(abc_product_b.directory, "userB_was_here.txt")
        work_model_b.commit()

        # userB use this product for a surfacing. he commits the surfacing
        surf_work_b = proj_b.create_resource("joe", "surfacing").checkout()
        surf_work_b.add_input("joe-model.abc")
        surf_work_b.commit()

        # User A checkout the surfacing
        os.environ["USER_VAR"] = "userA"
        surf_a = prj_a.get_resource("joe", "surfacing")

        # an error is raised by default
        with self.assertRaises(PulseWorkConflict):
            surf_a.checkout()

        # if the resolve argument is turn to "mine", user A version is kept
        surf_work_a = surf_a.checkout(resolve_conflict="mine")
        abc_product_a = surf_work_a.get_input_product("joe-model.abc")
        self.assertFalse(os.path.exists(os.path.join(abc_product_a.directory, "userB_was_here.txt")))

        # if the resolve argument is turn to "theirs", user B version is kept
        surf_work_a.trash()
        surf_a.checkout(resolve_conflict="theirs")
        self.assertTrue(os.path.exists(os.path.join(abc_product_a.directory, "userB_was_here.txt")))

    def test_check_out_from_template(self):
        # if no template exists
        resource = self.prj.create_resource("joe", "surface")
        resource.checkout()

        # if a template exists, but without any version
        self.prj.create_template("rig")
        resource = self.prj.create_resource("joe", "rig")
        resource.checkout()

        # if the template exists
        template = self.prj.create_template("shapes")
        template_work = template.checkout()
        utils.add_file_to_directory(template_work.directory)
        product = template_work.create_product("abc")
        utils.add_file_to_directory(product.directory, "test.abc")
        template_work.commit()

        resource = self.prj.create_resource("joe", "shapes")
        work = resource.checkout()
        work_abc = work.get_product("abc")
        self.assertFalse(os.path.exists(work_abc.directory + "/test.abc"))

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
        self.assertFalse(os.path.exists(os.path.join(
            anna_shd_work.get_product("shader").directory,
            shader_product_file)))

    def test_trashing_work_errors(self):
        froga_mdl_work = self.prj.create_resource("froga", "mdl").checkout()
        froga_mdl_work.create_product("abc")
        anna_surf_work = self.prj.create_resource("anna", "surfacing").checkout()
        anna_surf_work.add_input("froga-mdl.abc", consider_work_product=True)

        # trashing a product used by another resource is forbidden
        anna_surf_work.add_input(self.anna_abc_product_v1.uri)
        with self.assertRaises(PulseError):
            self.anna_abc_product_v1.remove_from_local_products()

    def test_work_dependencies_download(self):
        anna_surf_resource = self.prj.create_resource("ch_anna", "surfacing")
        anna_surf_work = anna_surf_resource.checkout()
        anna_surf_textures = anna_surf_work.create_product("textures")
        utils.add_file_to_directory(anna_surf_textures.directory, "product_file.txt")
        commit = anna_surf_work.commit(comment="test generated product")
        anna_rig_resource = self.prj.create_resource("ch_anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_surf_textures = commit.get_product("textures")
        anna_rig_work.add_input(anna_surf_textures.uri)
        anna_rig_work.commit("comment test")
        anna_rig_work.trash()
        anna_surf_work.trash()
        self.prj.purge_unused_user_products()
        self.assertFalse(os.path.exists(anna_surf_textures.directory))
        rig_v01 = anna_rig_resource.get_commit(1)
        self.assertTrue('ch_anna-surfacing.textures@1' in rig_v01.products_inputs)
        anna_rig_resource.checkout()
        self.assertTrue(os.path.exists(anna_surf_textures.directory))

    def test_recursive_dependencies_download(self):
        anna_surf_resource = self.prj.create_resource("ch_anna", "surfacing")
        anna_surf_work = anna_surf_resource.checkout()
        textures_work_product = anna_surf_work.create_product("textures")
        utils.add_file_to_directory(textures_work_product.directory, "product_file.txt")
        commit = anna_surf_work.commit(comment="test generated product")
        anna_surf_textures = commit.get_product("textures")
        anna_rig_resource = self.prj.create_resource("ch_anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_actor = anna_rig_work.create_product("actor_anim")
        anna_rig_actor.add_input(anna_surf_textures.uri)
        commit = anna_rig_work.commit()
        anna_rig_actor = commit.get_product("actor_anim")
        anna_rig_work.trash()
        anna_surf_work.trash()
        self.prj.purge_unused_user_products()
        self.assertFalse(os.path.exists(anna_surf_textures.directory))
        anim_resource = self.prj.create_resource("sh003", "anim")
        anim_work = anim_resource.checkout()
        anim_work.add_input(anna_rig_actor.uri)
        self.assertTrue(os.path.exists(anna_surf_textures.directory))

    def test_complete_scenario(self):
        # create a resource based on this template
        anna_mdl_resource = self.prj.create_resource("ch_anna", "modeling")
        self.assertEqual(anna_mdl_resource.last_version, 0)

        # checkout, and check directories are created
        anna_mdl_work = anna_mdl_resource.checkout()
        self.assertTrue(os.path.exists(anna_mdl_work.directory))

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
        abc_work_product = anna_mdl_work.create_product("ABC")
        # now products directory should exists
        self.assertTrue(os.path.exists(anna_mdl_work.get_products_directory()))
        utils.add_file_to_directory(abc_work_product.directory, "test.abc")
        # create a new commit
        commit = anna_mdl_work.commit("some abc produced")
        anna_mdl_v2_abc = commit.get_product("ABC")
        self.assertEqual(anna_mdl_resource.last_version, 2)
        # create a new resource
        hat_mdl_resource = self.prj.create_resource("hat", "modeling")
        self.assertEqual(hat_mdl_resource.last_version, 0)
        hat_mdl_work = hat_mdl_resource.checkout()
        hat_mdl_work.add_input("ch_anna-modeling.ABC")

        # test the product registration
        self.assertTrue("ch_anna-modeling.ABC" in hat_mdl_work.get_inputs())

        # check the work registration to product
        self.assertTrue(hat_mdl_work.directory in anna_mdl_v2_abc.get_product_users())

        # check you can't remove a product if it's used by a work
        with self.assertRaises(Exception):
            anna_mdl_v2_abc.remove_from_local_products()

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
        hat_mdl_work.remove_input("ch_anna-modeling.ABC")
        anna_mdl_work.trash()
        # test uri_standard
        self.assertEqual(uri.path_to_uri(hat_mdl_work.directory), hat_mdl_resource.uri)
        self.assertEqual(uri.path_to_uri(anna_mdl_v2_abc.directory), anna_mdl_v2_abc.uri)

    def test_work_commit(self):
        # test subdirectories are commit
        subdirectory_name = "subdirectory_test"
        work_subdir_path = os.path.join(self.anna_mdl_work.directory, subdirectory_name)
        os.makedirs(work_subdir_path)
        open(work_subdir_path + "\\subdir_file.txt", 'a').close()
        self.anna_mdl_work.commit()
        self.anna_mdl_work.trash()
        self.assertFalse(os.path.exists(self.anna_mdl_work.directory))
        mdl_work = self.anna_mdl.checkout()
        self.assertTrue(os.path.exists(work_subdir_path + "\\subdir_file.txt"))

        # test out product are kept and empty after commit
        product = mdl_work.create_product("export")
        utils.add_file_to_directory(product.directory, "export.txt")
        mdl_work.commit()
        clean_product = mdl_work.get_product("export")
        self.assertTrue(os.path.exists(clean_product.directory))
        self.assertFalse(os.path.exists(clean_product.directory + "/export.txt"))

        # test a commit using a uncommit input product will fail
        anna_surf_resource = self.prj.create_resource("ch_anna", "surfacing")
        anna_surf_work = anna_surf_resource.checkout()
        mdl_work.create_product("hidef")
        anna_surf_work.add_input("anna-mdl.hidef", consider_work_product=True)
        with self.assertRaises(PulseError):
            anna_surf_work.commit()

        # but when the input product is commit, the work can be commit too

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
        product = self.anna_mdl_work.get_product("abc")
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

    def test_work_create_product(self):
        # TODO : test work create product failed from a trash work
        pass

    def test_product_trash(self):
        anna_rig_resource = self.prj.create_resource("anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_actor = anna_rig_work.create_product("actor_anim")
        anna_rig_actor.add_input(self.anna_abc_product_v1.uri)
        anna_rig_work.trash_product("actor_anim")

    def test_product_download(self):
        self.anna_mdl_work.trash()
        self.prj.purge_unused_user_products()
        product = self.prj.get_commit_product("anna-mdl.abc@1")
        self.assertFalse(os.path.exists(product.directory))
        self.assertFalse(os.path.exists(product.product_users_file))
        product.download()
        self.assertTrue(os.path.exists(product.directory))
        self.assertTrue(os.path.exists(product.product_users_file))
        product.remove_from_local_products()
        self.assertFalse(os.path.exists(product.directory))
        self.assertFalse(os.path.exists(product.product_users_file))

    def test_product_download_conflict(self):
        os.environ["USER_VAR"] = "userA"
        prj_a = self.cnx.create_project(
            "project_conflict",
            utils.sandbox_work_path + "_${USER_VAR}",
            default_repository="main_storage",
            product_user_root=utils.sandbox_products_path + "_${USER_VAR}"
        )

        # userA checkout a modeling, he creates a abc product in V001
        work_model_a = prj_a.create_resource("joe", "model").checkout()
        abc_product_a = work_model_a.create_product("abc")
        utils.add_file_to_directory(abc_product_a.directory, "userA_was_here.txt")

        # userB does the exact same thing, but he do not commit
        os.environ["USER_VAR"] = "userB"
        proj_b = self.cnx.get_project("project_conflict")
        work_model_b = proj_b.get_resource("joe", "model").checkout()
        work_model_b.create_product("abc")

        # userA commit
        os.environ["USER_VAR"] = "userA"
        work_model_a.commit()

        # then userB try to download the last abc product, this should raise an error by default
        with self.assertRaises(PulseWorkConflict):
            os.environ["USER_VAR"] = "userB"
            commit_product = proj_b.get_commit_product("joe-model.abc@1")
            commit_product.download()

    def test_project_list_products(self):
        anna_rig_resource = self.prj.create_resource("anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_actor = anna_rig_work.create_product("actor_anim")
        anna_rig_actor.add_input(self.anna_abc_product_v1.uri)
        anna_rig_work.commit()
        self.assertTrue(len(self.prj.list_products("anna*")) == 2)
        self.assertTrue(len(self.prj.list_products("an?a*")) == 2)

    def test_project_list_works(self):
        anna_rig_resource = self.prj.create_resource("anna", "rigging")
        anna_rig_resource.checkout()
        self.assertEqual(self.prj.get_local_works(), ['anna-mdl', 'anna-rigging'])

    def test_get_project_from_path(self):
        project = get_project_from_path(self.anna_mdl_work.directory)
        self.assertEqual(project.get_local_works(), ['anna-mdl'])

    def test_junction_point_work_output(self):
        # ensure a resource got its output directory by default
        resource = self.prj.create_resource("toto", "model")
        work = resource.checkout()
        self.assertTrue(os.path.exists(os.path.join(work.directory, cfg.work_output_dir)))
        # ensure the output directory point to the current work product
        work.create_product("export")
        self.assertTrue(os.path.exists(os.path.join(work.directory, cfg.work_output_dir, "export")))

    def test_work_add_input(self):
        anna_rig_resource = self.prj.create_resource("anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()

        # test linked directory content is the same as the product content after add input
        anna_rig_work.add_input("anna-mdl.abc")
        self.assertEqual(os.listdir(os.path.join(
            anna_rig_work.directory,
            cfg.work_input_dir,
            "anna-mdl.abc"
        )), os.listdir(self.anna_abc_product_v1.directory))

        # test if the input already exists in work inputs
        with self.assertRaises(PulseError):
            anna_rig_work.add_input("anna-mdl.abc")

        # test the input is a non existing product
        with self.assertRaises(PulseDatabaseMissingObject):
            anna_rig_work.add_input("unknown-product.uri")

        # test where the input has to be downloaded
        low_texture = self.anna_mdl_work.create_product("low_texture")
        utils.add_file_to_directory(low_texture.directory, "tex.jpg")
        self.anna_mdl_work.commit()
        self.anna_mdl_work.trash()
        self.prj.purge_unused_user_products()
        self.assertFalse(os.path.exists(low_texture.directory))
        anna_rig_work.add_input(low_texture.uri)
        self.assertTrue(os.path.exists(os.path.join(low_texture.directory, "tex.jpg")))

        # test if downloaded product used as input is not purged
        self.prj.purge_unused_user_products()
        self.assertTrue(os.path.exists(os.path.join(low_texture.directory, "tex.jpg")))

        # test the input is a work product
        self.anna_mdl_work = self.anna_mdl.checkout()
        high_geo = self.anna_mdl_work.create_product("high_geo")
        utils.add_file_to_directory(high_geo.directory, "hi.abc")
        anna_rig_work.add_input("anna-mdl.high_geo", consider_work_product=True)
        self.assertTrue(os.path.exists(os.path.join(anna_rig_work.directory, "input", "anna-mdl.high_geo", "hi.abc")))

    def test_work_add_input_with_custom_name(self):
        anna_rig_resource = self.prj.create_resource("anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()

        # test linked directory content is the same as the product content after add input
        anna_rig_work.add_input("anna-mdl.abc", input_name="modeling")
        self.assertEqual(os.listdir(os.path.join(
            anna_rig_work.directory,
            cfg.work_input_dir,
            "modeling"
        )), os.listdir(self.anna_abc_product_v1.directory))

    def test_work_update_input(self):
        anna_rig_resource = self.prj.create_resource("anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        input_dir = os.path.join(anna_rig_work.directory, cfg.work_input_dir, "anna-mdl.abc")

        anna_rig_work.add_input("anna-mdl.abc")
        abc_v2 = self.anna_mdl_work.get_product("abc")
        utils.add_file_to_directory(abc_v2.directory, "V2.txt")
        # ignore work product with mutable input
        anna_rig_work.update_input("anna-mdl.abc")
        self.assertFalse("V2.txt" in os.listdir(input_dir))

        self.anna_mdl_work.commit()
        anna_rig_work.update_input("anna-mdl.abc")
        self.assertTrue("V2.txt" in os.listdir(input_dir))

        abc_v3 = self.anna_mdl_work.get_product("abc")
        utils.add_file_to_directory(abc_v3.directory, "V3.txt")
        anna_rig_work.update_input("anna-mdl.abc", consider_work_product=True)
        self.assertTrue("V3.txt" in os.listdir(input_dir))

        # input does update even if a mutable uri was given first
        anna_rig_work.remove_input("anna-mdl.abc")
        anna_rig_work.add_input(uri="anna-mdl.abc@2", input_name="anna-mdl.abc")
        self.anna_mdl_work.commit()
        anna_rig_work.update_input("anna-mdl.abc")
        self.assertTrue("V3.txt" in os.listdir(input_dir))

        # update input can change the input uri
        anna_rig_work.update_input("anna-mdl.abc", uri="anna-mdl.abc@2")
        self.assertTrue("V2.txt" in os.listdir(input_dir))

        # input uri change is permanent
        abc_v4 = self.anna_mdl_work.get_product("abc")
        utils.add_file_to_directory(abc_v4.directory, "V4.txt")
        anna_rig_work.update_input("anna-mdl.abc", consider_work_product=True)
        self.assertTrue("V4.txt" in os.listdir(input_dir))

        # test an input with mutable uri keep the last product version used when checkout
        anna_rig_work.remove_input("anna-mdl.abc")
        anna_rig_work.add_input(uri="anna-mdl.abc")
        self.assertTrue("V3.txt" in os.listdir(input_dir))
        anna_rig_work.commit()
        anna_rig_work.trash()
        self.anna_mdl_work.commit()
        anna_rig_work = anna_rig_resource.checkout()
        self.assertTrue("V3.txt" in os.listdir(input_dir))
        anna_rig_work.update_input("anna-mdl.abc")
        self.assertTrue("V4.txt" in os.listdir(input_dir))

        # test update input when there's no new version
        anna_rig_work.update_input("anna-mdl.abc")
        self.assertTrue("V4.txt" in os.listdir(input_dir))

        # test update a missing input
        with self.assertRaises(PulseError):
            anna_rig_work.update_input("missing-input")

        # test update input can download missing product
        anna_rig_work.commit()
        anna_rig_work.trash()
        self.prj.purge_unused_user_products()
        anna_rig_resource.checkout()
        self.assertTrue("V4.txt" in os.listdir(input_dir))

    def test_uri_validate(self):
        # test a product uri
        self.assertTrue(uri_standards.is_valid("anna-mdl.abc@2"))
        # test a commit uri
        self.assertTrue(uri_standards.is_valid("anna-mdl@2"))
        # test a resource uri
        self.assertTrue(uri_standards.is_valid("anna-mdl"))
        # test a nested resource uri
        self.assertTrue(uri_standards.is_valid("char.anna-mdl"))
        # test a mutable uri
        self.assertTrue(uri_standards.is_valid("anna-mdl.abc"))

        # test various malformed uri
        self.assertFalse(uri_standards.is_valid("an#na-mdl.abc@2"))
        self.assertFalse(uri_standards.is_valid("anna--mdl.abc"))
        self.assertFalse(uri_standards.is_valid("-annamdl.abc"))
        self.assertFalse(uri_standards.is_valid("anna.mdl@2"))

    def test_work_remove_input(self):
        # test remove product
        anna_rig_resource = self.prj.create_resource("anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_work.add_input("anna-mdl.abc")
        self.assertTrue(os.path.exists(os.path.join(anna_rig_work.directory, "input", "anna-mdl.abc")))
        anna_rig_work.remove_input("anna-mdl.abc")
        self.assertFalse(os.path.exists(os.path.join(anna_rig_work.directory, "input", "anna-mdl.abc")))

        # test remove a missing input
        with self.assertRaises(PulseError):
            anna_rig_work.remove_input(self.anna_abc_product_v1.uri)

    def test_product_add_input(self):
        anna_rig_resource = self.prj.create_resource("anna", "rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_hd = anna_rig_work.create_product("hd")
        anna_rig_hd.add_input(self.anna_abc_product_v1.uri)
        # test products don't have a "input" linked directory
        self.assertFalse(os.path.exists(os.path.join(anna_rig_hd.directory, "input")))


if __name__ == '__main__':
    unittest.main()
