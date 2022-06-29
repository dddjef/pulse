from pulse.api import *
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
        resource = prj.create_resource("ch_anna-model")
        # check out the resource
        work = resource.checkout()
        # test its location
        self.assertTrue(os.path.exists(os.path.join(utils.test_data_output_path, "works/env_var/ch_anna-model")))
        # add an output product
        utils.add_file_to_directory(os.path.join(work.output_directory, "abc"), "model.abc")
        # test the product folder location
        self.assertTrue(
            os.path.exists(os.path.join(utils.test_data_output_path, "products/env_var/ch_anna-model/V001/abc")))
        # commit
        utils.add_file_to_directory(work.directory)
        anna_model_v1 = work.publish()
        # trash
        work.trash(no_backup=True)
        prj.purge_unused_local_products()
        self.assertFalse(os.path.exists(os.path.join(
            utils.test_data_output_path,
            "works/env_var/ch_anna/model/V001/abc"
        )))
        # create another resource
        surf_resource = prj.create_resource("ch_anna-surfacing")
        surf_work = surf_resource.checkout()
        # require this product
        surf_work.add_input(anna_model_v1.uri)
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
        resource = prj.create_resource("ch_anna-model")
        # check out the resource
        work = resource.checkout()
        # test there's no output directory
        self.assertFalse(os.path.exists(work.output_directory))

        # add an output product
        os.makedirs(fu.path_join(work.product_directory, "abc"))
        os.makedirs(work.output_directory)
        # commit
        utils.add_file_to_directory(work.directory)
        anna_mdl_v1 = work.publish()
        # trash
        work.trash(no_backup=True)
        prj.purge_unused_local_products()
        # create another resource
        surf_resource = prj.create_resource("ch_anna-surfacing")
        surf_work = surf_resource.checkout()
        # require this product
        surf_work.add_input(anna_mdl_v1.uri)
        # test the product location
        self.assertFalse(os.path.exists(work.input_directory))
        surf_work.publish()


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
        self.anna_mdl = self.prj.create_resource("anna-mdl")
        self.anna_mdl_work = self.anna_mdl.checkout()
        utils.add_file_to_directory(self.anna_mdl_work.directory, "work.blend")
        self.anna_abc_work_product = os.path.join(self.anna_mdl_work.output_directory, "abc")
        utils.add_file_to_directory(self.anna_abc_work_product, "anna.abc")
        self.anna_mdl_v1 = self.anna_mdl_work.publish()

    def test_delete_project(self):
        self.cnx.delete_project(test_project_name)
        with self.assertRaises(PulseError):
            self.cnx.get_project(test_project_name)

    def test_template_resource(self):
        template_mdl = self.prj.create_template("mdl")
        template_mdl_work = template_mdl.checkout()
        utils.add_file_to_directory(os.path.join(template_mdl_work.product_directory, "abc"), "mdl.abc")
        utils.add_file_to_directory(template_mdl_work.directory, "mdl.blend")
        template_mdl_work.publish()
        template_mdl_work.trash()
        froga_mdl = self.prj.create_resource("froga-mdl")
        froga_mdl_work = froga_mdl.checkout()
        self.assertTrue(os.path.exists(os.path.join(froga_mdl_work.directory, "mdl.blend")))
        self.assertTrue(os.path.exists(os.path.join(froga_mdl_work.product_directory, "abc", "mdl.abc")))

        # assert template products state are restored after commit
        os.remove(os.path.join(froga_mdl_work.product_directory, "abc", "mdl.abc"))
        utils.add_file_to_directory(os.path.join(froga_mdl_work.product_directory, "abc"), "extra.abc")
        froga_mdl_work.publish()
        self.assertFalse(os.path.exists(os.path.join(froga_mdl_work.product_directory, "abc", "extra.abc")))
        self.assertTrue(os.path.exists(os.path.join(froga_mdl_work.product_directory, "abc", "mdl.abc")))

        # assert template products are restored after checkout by default
        froga_mdl_work.trash()
        self.assertFalse(os.path.exists(os.path.join(froga_mdl_work.product_directory, "abc", "mdl.abc")))
        froga_mdl.checkout()
        self.assertTrue(os.path.exists(os.path.join(froga_mdl_work.product_directory, "abc", "mdl.abc")))

    def test_unused_time_on_purged_product(self):
        self.anna_mdl_work.trash()
        self.prj.purge_unused_local_products()
        product = self.anna_mdl_v1
        self.assertTrue(product.get_unused_time(), -1)

    def test_purged_product(self):
        # test the dry mode
        self.anna_mdl_v1 = self.prj.get_published_version("anna-mdl@1")
        self.assertTrue(os.path.exists(self.anna_mdl_v1.directory))
        # self.assertEqual(['anna-mdl@1'], self.prj.purge_unused_local_products(dry_mode=True))

        # test dry mode don't remove the directory
        self.assertTrue(os.path.exists(self.anna_mdl_v1.directory))

        # test product currently in use can't be purged
        self.anna_surf = self.prj.create_resource("anna-surfacing")
        self.anna_surf_work = self.anna_surf.checkout()
        self.anna_surf_work.add_input(self.anna_mdl_v1.uri)
        # self.assertEqual(self.prj.purge_unused_local_products(dry_mode=True), [])

        # test the normal mode
        self.anna_surf_work.trash()
        self.assertEqual(['anna-mdl@1'], self.prj.purge_unused_local_products(dry_mode=False))
        self.assertFalse(os.path.exists(self.anna_abc_work_product))

    def test_manipulating_trashed_work(self):
        # ensure a file inside output won't be an issue when trashing the work
        utils.add_file_to_directory(self.anna_mdl_work.output_directory, "wip.abc")
        self.anna_mdl_work.trash()
        self.prj.purge_unused_local_products()
        anna_surf_work = self.prj.create_resource("anna-surfacing").checkout()
        # ensure trashed worked have no directory anymore
        self.assertFalse(os.path.exists(self.anna_mdl_work.directory))
        # commit a trashed work
        with self.assertRaises(PulseMissingNode):
            self.anna_mdl_work.publish()


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
            res_work.publish()

    def test_checkout(self):
        # remove a work with a commit product
        self.anna_mdl_work.trash()
        print("bval", self.anna_mdl.jojo)
        print("bval", self.anna_mdl._jojo)
        self.anna_mdl.jojo = 5
        self.prj.purge_unused_local_products()
        # ensure the absolute product directory is missing
        self.assertFalse(os.path.exists(self.anna_mdl_work.product_directory))
        # checkout the resource again
        work = self.anna_mdl.checkout()
        # test the empty product has been restored
        self.assertTrue(os.path.exists(self.anna_mdl_work.product_directory))


    def test_work_checkout_product_conflict(self):
        os.environ["USER_VAR"] = "userA"
        prj_a = self.cnx.create_project(
            "project_conflict",
            utils.sandbox_work_path + "_${USER_VAR}",
            default_repository="main_storage",
            product_user_root=utils.sandbox_products_path + "_${USER_VAR}"
        )

        # userA checkout a modeling, he creates a abc product in V001
        work_model_a = prj_a.create_resource("joe-model").checkout()
        utils.add_file_to_directory(work_model_a.product_directory + "/abc")

        # userB checkout the same resource, but he commits first
        os.environ["USER_VAR"] = "userB"
        proj_b = self.cnx.get_project("project_conflict")
        work_model_b = proj_b.get_resource("joe-model").checkout()
        #abc_product_b = work_model_b.product_directory + "/abc")
        utils.add_file_to_directory(work_model_b.product_directory + "/abc", "userB_was_here.txt")
        work_model_b.publish()

        # userB use this product for a surfacing. he commits the surfacing
        surf_work_b = proj_b.create_resource("joe-surfacing").checkout()
        surf_work_b.add_input("joe-model/abc")
        surf_work_b.publish()

        # User A checkout the surfacing
        os.environ["USER_VAR"] = "userA"
        surf_a = prj_a.get_resource("joe-surfacing")

        # an error is raised by default
        with self.assertRaises(PulseWorkConflict):
            surf_a.checkout()

        # if the resolve argument is turn to "mine", user A version is kept
        surf_work_a = surf_a.checkout(resolve_conflict="mine")
        abc_product_a = surf_work_a.get_input("joe-model/abc")
        self.assertFalse(os.path.exists(os.path.join(abc_product_a.product_directory, "abc", "userB_was_here.txt")))

        # if the resolve argument is turn to "theirs", user B version is kept
        surf_work_a.trash()
        surf_a.checkout(resolve_conflict="theirs")
        self.assertTrue(os.path.exists(os.path.join(abc_product_a.product_directory, "abc", "userB_was_here.txt")))

    def test_check_out_from_template(self):
        # if no template exists
        resource = self.prj.create_resource("joe-surface")
        resource.checkout()

        # if a template exists, but without any version
        self.prj.create_template("rig")
        resource = self.prj.create_resource("joe-rig")
        resource.checkout()

        # if the template exists
        template = self.prj.create_template("shapes")
        template_work = template.checkout()
        utils.add_file_to_directory(template_work.directory)
        utils.add_file_to_directory(template_work.output_directory, "test.abc")
        os.makedirs(template_work.output_directory + "/empty_directory")
        template_work.publish()

        # by default checkout restore product data
        resource = self.prj.create_resource("joe-shapes")
        work = resource.checkout()
        self.assertTrue(os.path.exists(work.output_directory + "/test.abc"))
        self.assertTrue(os.path.exists(work.output_directory + "/empty_directory"))

    def test_check_out_from_another_resource(self):
        shader_work_file = "shader_work_file.ma"
        shader_product_file = "shader_product_file.ma"
        source_resource = self.prj.create_resource("source-surface")
        source_work = source_resource.checkout()
        utils.add_file_to_directory(source_work.directory, shader_work_file)
        utils.add_file_to_directory(os.path.join(source_work.output_directory, "shader"), shader_product_file)
        source_work.publish()

        anna_shd_resource = self.prj.create_resource("ch_anna-surface", source_resource=source_resource)
        anna_shd_work = anna_shd_resource.checkout()
        self.assertTrue(os.path.exists(os.path.join(anna_shd_work.directory, shader_work_file)))
        # check product files are not restored
        self.assertFalse(os.path.exists(os.path.join(
            anna_shd_work.output_directory, "shader",
            shader_product_file)))

    def test_work_dependencies_download(self):
        anna_surf_resource = self.prj.create_resource("ch_anna-surfacing")
        anna_surf_work = anna_surf_resource.checkout()
        anna_surf_textures_path = os.path.join(anna_surf_work.product_directory, "textures")
        utils.add_file_to_directory(anna_surf_textures_path, "product_file.txt")
        anna_surf_v2 = anna_surf_work.publish(comment="test generated product")
        anna_rig_resource = self.prj.create_resource("ch_anna-rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_work.add_input(anna_surf_v2.uri + "/textures")
        anna_rig_work.publish("comment test")
        anna_rig_work.trash()
        anna_surf_work.trash()
        self.prj.purge_unused_local_products()
        self.assertFalse(os.path.exists(anna_surf_textures_path))
        rig_v01 = anna_rig_resource.get_commit(1)
        self.assertTrue('ch_anna-surfacing@1/textures' in rig_v01.work_inputs)
        anna_rig_resource.checkout()
        self.assertTrue(os.path.exists(anna_surf_textures_path))

    def test_complete_scenario(self):
        # create a resource based on this template
        anna_mdl_resource = self.prj.create_resource("ch_anna-modeling")
        self.assertEqual(anna_mdl_resource.last_version, 0)

        # checkout, and check directories are created
        anna_mdl_sandbox = anna_mdl_resource.checkout()
        self.assertTrue(os.path.exists(anna_mdl_sandbox.directory))

        # commit should fail if nothing is change in work
        with self.assertRaises(PulseError):
            anna_mdl_sandbox.publish("very first time")

        # create a new file in work directory and try to commit again
        new_file = "test_complete.txt"
        mdl_work_dir = os.path.join(anna_mdl_sandbox.directory, "work")
        utils.add_file_to_directory(mdl_work_dir, new_file)
        self.assertEqual(anna_mdl_sandbox.status(), {"/work/" + new_file: 'added'})

        anna_mdl_sandbox.publish("add a file")
        self.assertEqual(anna_mdl_resource.last_version, 1)

        # create a sub resource
        abc_work_product = os.path.join(anna_mdl_sandbox.directory, "output", "abc")
        os.makedirs(abc_work_product)
        # now products directory should exists)
        utils.add_file_to_directory(abc_work_product, "test.abc")
        # create a new commit
        anna_mdl_v2 = anna_mdl_sandbox.publish("some abc produced")

        self.assertEqual(anna_mdl_resource.last_version, 2)
        # create a new resource
        anna_srf_resource = self.prj.create_resource("ch_anna-surfacing")
        self.assertEqual(anna_srf_resource.last_version, 0)
        anna_srf_work = anna_srf_resource.checkout()
        anna_srf_work.add_input("ch_anna-modeling/ABC")
        self.assertTrue(os.path.exists(os.path.join(anna_srf_work.input_directory, "ch_anna-modeling~ABC/test.abc")))

        anna_srf_work.publish("with input")
        self.assertEqual(anna_srf_resource.last_version, 1)

        anna_srf_work.trash()
        # remove the product
        self.prj.purge_unused_local_products()
        # checkout the work
        anna_srf_work = anna_srf_resource.checkout()
        # test the input is restored
        self.assertTrue(os.path.exists(os.path.join(anna_srf_work.input_directory, "ch_anna-modeling~ABC/test.abc")))

        anna_srf_work.remove_input("ch_anna-modeling/ABC")
        anna_mdl_sandbox.trash()
        # create a new output
        utils.add_file_to_directory(fu.path_join(anna_srf_work.output_directory, "ld"))

        # commit surfacing
        anna_srf_v2 = anna_srf_work.publish()
        self.assertEqual(anna_srf_v2.version, 2)

        # test work trash remove the work product directory
        product_dir = anna_srf_work.product_directory
        anna_srf_work.trash()
        self.assertFalse(os.path.exists(product_dir))

        # trash and download last commit to test restore product inputs
        anna_srf_v2.remove_from_local_products()
        self.assertFalse(os.path.exists(anna_srf_v2.directory))

        anna_srf_v2.download()
        self.assertTrue(os.path.exists(os.path.join(anna_srf_v2.directory, "ld")))


    def test_path_to_uri(self):
        self.assertEqual(uri.path_to_uri(self.anna_mdl_work.directory), "anna-mdl")
        self.assertEqual(uri.path_to_uri(self.anna_mdl_v1.directory), "anna-mdl@1")
        self.assertEqual(uri.path_to_uri
            ("C:/Users/dddje/PycharmProjects/pulse/tests/data/out/products/test/anna-mdl/V001/abc"),"anna-mdl@1/abc")
        self.assertEqual(uri.path_to_uri
            ("C:/Users/dddje/PycharmProjects/pulse/tests/data/out/products/test/anna-mdl/V001/abc/ld"),"anna-mdl@1/abc/ld")

    def test_work_commit(self):
        # test subdirectories are commit, empty or not
        subdirectory_name = "subdirectory_test"
        work_subdir_path = os.path.join(self.anna_mdl_work.directory, subdirectory_name)
        os.makedirs(work_subdir_path)
        open(work_subdir_path + "\\subdir_file.txt", 'a').close()
        subdirectory_name = "empty_subdirectory"
        work_subdir_empty_path = os.path.join(self.anna_mdl_work.directory, subdirectory_name)
        os.makedirs(work_subdir_empty_path)
        self.anna_mdl_work.publish()
        self.anna_mdl_work.trash()
        self.assertFalse(os.path.exists(self.anna_mdl_work.directory))
        mdl_work = self.anna_mdl.checkout()
        self.assertTrue(os.path.exists(work_subdir_path + "\\subdir_file.txt"))
        self.assertTrue(os.path.exists(work_subdir_empty_path))

        # test a commit using a uncommit input product will fail
        anna_surf_resource = self.prj.create_resource("ch_anna-surfacing")
        anna_surf_work = anna_surf_resource.checkout()
        anna_surf_work.add_input("anna-mdl", consider_work_product=True)
        with self.assertRaises(PulseError):
            anna_surf_work.publish()

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
        self.assertEqual(2, len(self.anna_mdl_work.status()))
        self.anna_mdl_work.revert()
        # test there's no more changes
        self.assertEqual(0, len(self.anna_mdl_work.status()))

    def test_work_update(self):
        # commit a new version (2), and trash it
        utils.add_file_to_directory(self.anna_mdl_work.directory, "new_file.txt")
        self.anna_mdl_work.publish()
        self.anna_mdl_work.trash()
        # checkout to version 1, and test the new file is not there
        work = self.anna_mdl.checkout(index=1)
        self.assertFalse(os.path.exists(os.path.join(self.anna_mdl_work.directory, "new_file.txt")))
        # update the work, check the new file is there
        time.sleep(1)
        work.update(force=True)
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
        utils.add_file_to_directory(self.anna_mdl_work.product_directory, "product_file.txt")
        # test trash work and its wip product
        self.anna_mdl_work.trash()
        self.assertFalse(os.path.exists(self.anna_mdl_work.product_directory))
        self.assertFalse(os.path.exists(self.anna_mdl_work.directory))
        self.assertFalse(os.path.exists(self.anna_mdl_work.pulse_product_data_file))

    def test_work_commit_data(self):
        anna_rig_resource = self.prj.create_resource("anna-rigging")
        anna_rig_work = anna_rig_resource.checkout()
        utils.add_file_to_directory(anna_rig_work.directory, "work_file.txt")
        anna_rig_work.publish()
        commit = anna_rig_resource.get_commit("last")
        self.assertEqual(list(commit.files.keys())[0], '/work_file.txt')


    def test_product_download(self):
        self.anna_mdl_work.trash()
        self.prj.purge_unused_local_products()
        anna_mdl_V1 = self.prj.get_published_version("anna-mdl@1")
        self.assertFalse(os.path.exists(anna_mdl_V1.directory))
        self.assertFalse(anna_mdl_V1.is_local())
        self.assertFalse(os.path.exists(anna_mdl_V1.pulse_product_data_file))
        anna_mdl_V1.download()
        self.assertTrue(os.path.exists(anna_mdl_V1.directory))
        self.assertTrue(os.path.exists(anna_mdl_V1.pulse_product_data_file))
        self.assertTrue(anna_mdl_V1.is_local())
        anna_mdl_V1.remove_from_local_products()
        self.assertFalse(os.path.exists(anna_mdl_V1.directory))
        self.assertFalse(os.path.exists(anna_mdl_V1.pulse_product_data_file))

        # test to download a product with a subpath which does not exists
        with self.assertRaises(PulseRepositoryError):
            anna_mdl_V1.download(subpath="/fancy_subpath")

        # test download a product partially, then completly
        anna_srf = self.prj.create_resource("anna-surfacing").checkout()
        abc_path = anna_srf.product_directory + "/abc"
        utils.add_file_to_directory(abc_path + "/ld", "ld.abc")
        utils.add_file_to_directory(abc_path, "base.abc")
        srf_v1 = anna_srf.publish()
        self.prj.purge_unused_local_products()
        self.assertFalse(os.path.exists(abc_path))

        # test download subpath supports without or without leadind slash
        srf_v1.download(subpath="abc/ld")
        self.assertTrue(os.path.exists(abc_path + "/ld/ld.abc"))
        self.prj.purge_unused_local_products()
        srf_v1.download(subpath="/abc/ld")
        self.assertTrue(os.path.exists(abc_path + "/ld/ld.abc"))

        # Download only a subdirectory does not download root files
        self.assertFalse(os.path.exists(abc_path + "/base.abc"))
        # download root files after does nto raise an error
        srf_v1.download()
        self.assertTrue(os.path.exists(abc_path + "/base.abc"))


    def test_product_download_conflict(self):
        os.environ["USER_VAR"] = "userA"
        prj_a = self.cnx.create_project(
            "project_conflict",
            utils.sandbox_work_path + "_${USER_VAR}",
            default_repository="main_storage",
            product_user_root=utils.sandbox_products_path + "_${USER_VAR}"
        )

        # userA checkout a modeling, he creates a abc product in V001
        work_model_a = prj_a.create_resource("joe-model").checkout()
        a_abc_product_directory = os.path.join(work_model_a.output_directory, "abc")
        os.makedirs(a_abc_product_directory)
        utils.add_file_to_directory(a_abc_product_directory, "userA_was_here.txt")

        # userB does the exact same thing, but he does not commit
        os.environ["USER_VAR"] = "userB"
        proj_b = self.cnx.get_project("project_conflict")
        work_model_b = proj_b.get_resource("joe-model").checkout()
        b_abc_product_directory = os.path.join(work_model_b.output_directory, "abc")
        os.makedirs(b_abc_product_directory)

        # userA commit
        os.environ["USER_VAR"] = "userA"
        work_model_a.publish()

        # then userB tries to download the last abc product, this should raise an error by default
        with self.assertRaises(PulseWorkConflict):
            os.environ["USER_VAR"] = "userB"
            commit_product = proj_b.get_published_version("joe-model@1/abc")
            commit_product.download()

    def test_project_list_products(self):
        anna_rig_resource = self.prj.create_resource("anna-rigging")
        anna_rig_work = anna_rig_resource.checkout()
        utils.add_file_to_directory(anna_rig_work.output_directory + "/actor_anim", "actor.blend")
        anna_rig_work.publish()
        self.assertTrue(len(self.prj.list_published_versions("anna*")) == 2)
        self.assertTrue(len(self.prj.list_published_versions("an?a*")) == 2)

    def test_project_list_works(self):
        anna_rig_resource = self.prj.create_resource("anna-rigging")
        anna_rig_resource.checkout()
        self.assertEqual(self.prj.list_works(), ['anna-mdl', 'anna-rigging'])

    def test_get_project_from_path(self):
        project = get_project_from_path(self.anna_mdl_work.directory)
        self.assertEqual(project.list_works(), ['anna-mdl'])

    def test_junction_point_work_output(self):
        # ensure a resource got its output directory by default
        resource = self.prj.create_resource("toto-model")
        work = resource.checkout()
        self.assertTrue(os.path.exists(os.path.join(work.directory, cfg.work_output_dir)))
        # ensure the output directory point to the current work product
        os.makedirs(os.path.join(work.output_directory, "export"))
        self.assertTrue(os.path.exists(os.path.join(work.product_directory, "export")))

    def test_work_add_input(self):
        anna_rig_resource = self.prj.create_resource("anna-rigging")
        anna_rig_work = anna_rig_resource.checkout()

        # test linked directory content is the same as the product content after add input
        anna_rig_work.add_input("anna-mdl/abc")
        self.assertEqual(os.listdir(os.path.join(
            anna_rig_work.directory,
            cfg.work_input_dir,
            "anna-mdl~abc"
        )), os.listdir(os.path.join(self.anna_mdl_v1.directory, "abc")))

        # test if the input already exists in current work inputs
        with self.assertRaises(PulseError):
            anna_rig_work.add_input("anna-mdl/abc")

        # test the input is a non existing product
        with self.assertRaises(PulseDatabaseMissingObject):
            anna_rig_work.add_input("unknown-product.uri")

        # test when the input has to be downloaded
        mdl_low_directory = os.path.join(self.anna_mdl_work.output_directory, "low")
        utils.add_file_to_directory(mdl_low_directory, "tex.jpg")
        anna_mdl_commit = self.anna_mdl_work.publish()
        self.anna_mdl_work.trash()
        self.prj.purge_unused_local_products()
        self.assertFalse(os.path.exists(mdl_low_directory))
        anna_rig_work.add_input("anna-mdl@2/low")
        tex_path = os.path.join(anna_mdl_commit.directory, "low", "tex.jpg")
        self.assertTrue(os.path.exists(tex_path))

        # test if downloaded product used as input is not purged
        self.prj.purge_unused_local_products()
        self.assertTrue(os.path.exists(tex_path))

        # test when the input is a work product
        self.anna_mdl_work = self.anna_mdl.checkout()
        high_geo_directory = os.path.join(self.anna_mdl_work.output_directory, "high_geo")
        utils.add_file_to_directory(high_geo_directory, "hi.abc")
        anna_rig_work.add_input("anna-mdl/high_geo", consider_work_product=True)
        self.assertTrue(os.path.exists(os.path.join(anna_rig_work.directory, "input", "anna-mdl~high_geo", "hi.abc")))

    def test_work_add_input_with_custom_name(self):
        anna_rig_resource = self.prj.create_resource("anna-rigging")
        anna_rig_work = anna_rig_resource.checkout()

        # test linked directory content is the same as the product content after add input
        anna_rig_work.add_input("anna-mdl/abc", input_name="modeling")
        self.assertEqual(os.listdir(os.path.join(
            anna_rig_work.directory,
            cfg.work_input_dir,
            "modeling"
        )), os.listdir(os.path.join(self.anna_mdl_v1.directory, "abc")))

    def test_work_update_input(self):
        anna_rig_resource = self.prj.create_resource("anna-rigging")
        anna_rig_work = anna_rig_resource.checkout()
        abc_input_dir = os.path.join(anna_rig_work.input_directory, "anna-mdl~abc")

        anna_rig_work.add_input("anna-mdl/abc")
        abc_v2 = self.anna_mdl_work.product_directory + "/abc"
        utils.add_file_to_directory(abc_v2, "V2.txt")
        # ignore work product with mutable input
        anna_rig_work.update_input("anna-mdl/abc")
        self.assertFalse("V2.txt" in os.listdir(abc_input_dir))

        self.anna_mdl_work.publish()
        anna_rig_work.update_input("anna-mdl/abc")
        self.assertTrue("V2.txt" in os.listdir(abc_input_dir))

        utils.add_file_to_directory(self.anna_mdl_work.product_directory + "/abc", "V3.txt")
        anna_rig_work.update_input("anna-mdl/abc", consider_work_product=True)
        self.assertTrue("V3.txt" in os.listdir(abc_input_dir))

        # input does update even if a mutable uri was given first
        anna_rig_work.remove_input("anna-mdl/abc")
        anna_rig_work.add_input(uri="anna-mdl@2/abc", input_name="anna-mdl/abc")
        self.anna_mdl_work.publish()
        anna_rig_work.update_input("anna-mdl/abc")
        self.assertTrue("V3.txt" in os.listdir(abc_input_dir))

        # update input can change the input uri
        anna_rig_work.update_input("anna-mdl/abc", uri="anna-mdl@2/abc")
        self.assertTrue("V2.txt" in os.listdir(abc_input_dir))

        # input uri change is permanent
        utils.add_file_to_directory(self.anna_mdl_work.product_directory + "/abc", "V4.txt")
        anna_rig_work.update_input("anna-mdl/abc", consider_work_product=True)
        self.assertTrue("V4.txt" in os.listdir(abc_input_dir))

        # test an input with mutable uri keep the last product version used when checkout
        anna_rig_work.remove_input("anna-mdl/abc")
        anna_rig_work.add_input(uri="anna-mdl/abc")
        self.assertTrue("V3.txt" in os.listdir(abc_input_dir))
        anna_rig_work.publish()
        anna_rig_work.trash()
        self.anna_mdl_work.publish()
        anna_rig_work = anna_rig_resource.checkout()
        self.assertTrue("V3.txt" in os.listdir(abc_input_dir))
        anna_rig_work.update_input("anna-mdl/abc")
        self.assertTrue("V4.txt" in os.listdir(abc_input_dir))

        # test update input when there's no new version
        anna_rig_work.update_input("anna-mdl/abc")
        self.assertTrue("V4.txt" in os.listdir(abc_input_dir))

        # test update a missing input
        with self.assertRaises(PulseError):
            anna_rig_work.update_input("missing-input")

        # test update input can download missing product
        anna_rig_work.publish()
        anna_rig_work.trash()
        self.prj.purge_unused_local_products()
        anna_rig_resource.checkout()
        self.assertTrue("V4.txt" in os.listdir(abc_input_dir))

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
        anna_rig_resource = self.prj.create_resource("anna-rigging")
        anna_rig_work = anna_rig_resource.checkout()
        anna_rig_work.add_input("anna-mdl/abc")
        self.assertTrue(os.path.exists(os.path.join(anna_rig_work.input_directory, "anna-mdl~abc")))
        anna_rig_work.remove_input("anna-mdl/abc")
        self.assertFalse(os.path.exists(os.path.join(anna_rig_work.input_directory, "anna-mdl~abc")))

        # test remove a missing input
        with self.assertRaises(PulseError):
            anna_rig_work.remove_input("unknown-uri")

    def test_concurrent_work(self):
        os.environ["USER_VAR"] = "userA"
        prj_a = self.cnx.create_project(
            "project_conflict",
            utils.sandbox_work_path + "_${USER_VAR}",
            default_repository="main_storage",
            product_user_root=utils.sandbox_products_path + "_${USER_VAR}"
        )

        # userA checkout a modeling, he creates a abc product in V001
        work_model_a = prj_a.create_resource("joe-model").checkout()
        utils.add_file_to_directory(work_model_a.directory)

        # userB checkout the same resource, but he commits first
        os.environ["USER_VAR"] = "userB"
        proj_b = self.cnx.get_project("project_conflict")
        resource_model_b = proj_b.get_resource("joe-model")

        # Ensure publish from another user increment the last version for every one
        self.assertEqual(resource_model_b.last_version, 0)
        work_model_a.publish()
        resource_model_b.db_read()
        self.assertEqual(resource_model_b.last_version, 1)

if __name__ == '__main__':
    unittest.main()