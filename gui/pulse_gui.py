import sys
from PyQt5.uic import loadUi
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QApplication, QDialog, QTreeWidgetItem, QMenu, QMainWindow, QInputDialog, QMessageBox,\
    QListWidgetItem
from PyQt5.QtCore import Qt
from functools import partial
import pulse.api as pulse
import pulse.uri_standards as pulse_uri
import pulse.config as pulse_cfg
from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QIcon
import traceback
import os
import webbrowser

LOG = "interface"
SETTINGS_DEFAULT_TEXT = "attribute = value"


class PulseItem(QTreeWidgetItem):
    def __init__(self, parent, pulse_node):
        super(PulseItem, self).__init__(parent)
        self.pulse_node = pulse_node


class ProductItem(QListWidgetItem):
    def __init__(self, parent, pulse_node):
        super(ProductItem, self).__init__(parent)
        self.pulse_node = pulse_node


def text_settings_to_dict(text):
    settings = {}
    for prm in text.split("\n"):
        if "=" in prm:
            split_line = prm.split("=")
            settings[split_line[0].strip()] = split_line[1].strip()
    return settings


def print_exception(exception, window=None):
    if LOG == "interface":
        window.message_user(str(exception), message_type=type(exception).__name__)
        traceback.print_exc()


def set_tree_item_style(item, style):
    if style == "downloaded":
        item.setIcon(0, QIcon(r'icons\folder.png'))
    else:
        item.setIcon(0, QIcon())


class LocalProductsWindow(QDialog):
    def __init__(self, main_window):
        super(LocalProductsWindow, self).__init__()
        loadUi("products_local_cache.ui", self)
        self.mainWindow = main_window
        self.project = main_window.project
        self.process_pushButton.clicked.connect(self.remove)
        self.showUnused_checkBox.stateChanged.connect(self.update_inputs_list)
        self.unusedDays_spinBox.valueChanged.connect(self.update_inputs_list)
        self.update_inputs_list()

    def update_inputs_list(self):
        self.products_listWidget.clear()
        for uri in self.project.get_local_commit_products():
            print(uri)
            product = self.project.get_product(uri)
            if self.showUnused_checkBox.isChecked():
                if product.get_unused_time() < (self.unusedDays_spinBox.value()*86400):
                    continue
            users = product.get_product_users()
            item = ProductItem(product.uri + " (used : " + str(len(users)) + ")", pulse_node=product)
            self.products_listWidget.addItem(item)

    def remove(self):
        removed = 0
        for item in self.products_listWidget.selectedItems():
            try:
                item.pulse_node.remove_from_local_products()
                removed += 1
            except Exception as ex:
                print_exception(ex, self.mainWindow)
            return
        self.update_inputs_list()
        self.mainWindow.message_user(str(removed) + " product(s) removed from local cache")


# TODO : add the create from another resource feature
class CreateResourceTemplateWindow(QDialog):
    def __init__(self, main_window):
        super(CreateResourceTemplateWindow, self).__init__()
        loadUi("create_resource_template.ui", self)
        self.mainWindow = main_window
        # add the repository choice
        self.repositories = list(main_window.connection.get_repositories().keys())
        display_repo_names = []
        i = 0
        default_repository_index = 0
        for repo_name in self.repositories:
            if repo_name == main_window.project.cfg.default_repository:
                repo_name = repo_name + " (default)"
                default_repository_index = i
            display_repo_names.append(repo_name)
            i += 1
        self.repository_comboBox.addItems(display_repo_names)
        self.repository_comboBox.setCurrentIndex(default_repository_index)
        self.create_pushButton.clicked.connect(self.create_template)

    # TODO : create template did crash with a vanilla app session
    def create_template(self):
        try:
            new_resource = self.mainWindow.project.create_template(
                self.type_lineEdit.text(),
                repository=self.repositories[self.repository_comboBox.currentIndex()]
            )
        except Exception as ex:
            print_exception(ex, self.mainWindow)
            return
        resource_item = PulseItem([new_resource.uri], new_resource)
        self.mainWindow.treeWidget.addTopLevelItem(resource_item)
        self.close()


class InputsWindow(QDialog):
    # TODO : should propose to enter manually an URI
    # TODO : should be placed upper than the treeview, to help the user to focus directly on the right part
    def __init__(self, main_window, pulse_node):
        QDialog.__init__(self, main_window)
        loadUi("edit_inputs.ui", self)
        self.mainWindow = main_window
        self.pulse_node = pulse_node
        self.setWindowTitle(self.mainWindow.treeWidget.currentItem().text(0) + " inputs")
        self.addInput_pushButton.clicked.connect(self.add_input)
        self.removeInput_pushButton.clicked.connect(self.remove_input)
        self.close_pushButton.clicked.connect(self.close)
        self.update_inputs_list()

    def update_inputs_list(self):
        self.inputs_listWidget.clear()
        for product in self.pulse_node.get_inputs():
            item = ProductItem(product.uri, pulse_node=product)
            self.inputs_listWidget.addItem(item)

    def add_input(self):
        current_item = self.mainWindow.treeWidget.currentItem()
        if not current_item:
            self.mainWindow.message_user("You have to select an item in the treeview", "ERROR")
        elif not isinstance(current_item.pulse_node, pulse.CommitProduct):
            self.mainWindow.message_user("the selected item should be a commit product only", "ERROR")
        else:
            self.pulse_node.add_input(current_item.pulse_node)
            self.mainWindow.message_user("Added to inputs : " + current_item.pulse_node.uri)
            self.update_inputs_list()
            # TODO : refresh the current tree view to show the downloaded product icon if needed
            # TODO : refresh current details

    def remove_input(self):
        try:
            selected = self.inputs_listWidget.selectedItems()[0]
        except IndexError:
            self.mainWindow.message_user("Select an input to remove", "ERROR")
            return
        self.pulse_node.remove_input(selected.pulse_node)
        self.update_inputs_list()


# TODO : add the create from another resource feature
class CreateResourceWindow(QDialog):
    def __init__(self, main_window, entity_name):
        super(CreateResourceWindow, self).__init__()
        loadUi("create_resource.ui", self)
        self.mainWindow = main_window
        self.typeFromTemplate_radioButton.clicked.connect(self.type_from_template_checked)
        self.typeCustom_radioButton.clicked.connect(self.type_custom_checked)
        self.entityName_lineEdit.setText(entity_name)
        self.createResource_pushButton.clicked.connect(self.create_resource)
        self.template_types = [
            pulse_uri.convert_to_dict(x)["resource_type"] for x in self.mainWindow.connection.db.find_uris(
                main_window.project.name,
                "Resource",
                "_template-*"
            )]
        self.typeTemplate_comboBox.addItems(self.template_types)
        self.repository_comboBox.clear()
        # add the repository choice
        self.repositories = list(main_window.connection.get_repositories().keys())
        display_repo_names = []
        i = 0
        default_repository_index = 0
        for repo_name in self.repositories:
            if repo_name == main_window.project.cfg.default_repository:
                repo_name = repo_name + " (default)"
                default_repository_index = i
            display_repo_names.append(repo_name)
            i += 1
        self.repository_comboBox.addItems(display_repo_names)
        self.repository_comboBox.setCurrentIndex(default_repository_index)

    def create_resource(self):
        entity_name = self.entityName_lineEdit.text()
        if self.typeFromTemplate_radioButton.isChecked():
            entity_type = self.typeTemplate_comboBox.currentText()
        else:
            entity_type = self.typeCustom_lineEdit.text()
        # TODO : check the input strings are valid

        try:
            new_resource = self.mainWindow.project.create_resource(
                entity_name,
                entity_type,
                repository=self.repositories[self.repository_comboBox.currentIndex()]
            )
        except Exception as ex:
            print_exception(ex, self.mainWindow)
            return
        resource_item = PulseItem([new_resource.uri], new_resource)
        self.mainWindow.treeWidget.addTopLevelItem(resource_item)
        self.close()

    def type_from_template_checked(self):
        self.typeTemplate_comboBox.setEnabled(True)
        self.typeCustom_lineEdit.setEnabled(False)

    def type_custom_checked(self):
        self.typeTemplate_comboBox.setEnabled(False)
        self.typeCustom_lineEdit.setEnabled(True)


# TODO : add a tooltip to explain how to add an env var in path
class ProjectWindow(QDialog):
    def __init__(self, main_window, repositories):
        super(ProjectWindow, self).__init__()
        loadUi("create_project.ui", self)
        self.createProject_pushButton.clicked.connect(self.create_project)
        self.mainWindow = main_window
        self.repository_comboBox.clear()
        self.repository_comboBox.addItems(repositories)
        self.sandboxPath_lineEdit.setText(os.path.join(os.path.expanduser("~"), "pulse_sandbox"))
        self.sameProductPath_checkBox.stateChanged.connect(self.same_path_checkbox_changed)

    def same_path_checkbox_changed(self):
        self.productsPath_lineEdit.setEnabled(not self.sameProductPath_checkBox.isChecked())

    def create_project(self):
        if self.sameProductPath_checkBox.isChecked():
            product_user_root = None
        else:
            product_user_root = self.productsPath_lineEdit.text()

        try:
            self.mainWindow.connection.create_project(
                project_name=self.name_lineEdit.text(),
                work_user_root=self.sandboxPath_lineEdit.text(),
                default_repository=self.repository_comboBox.currentText(),
                product_user_root=product_user_root,
            )

            self.mainWindow.message_user("project " + self.name_lineEdit.text() + " successfully created")
            self.close()
            self.mainWindow.project_comboBox.addItem(self.name_lineEdit.text())
            self.mainWindow.project_comboBox.setCurrentIndex(self.mainWindow.project_comboBox.count() - 1)
            self.mainWindow.update_project()
        except Exception as ex:
            print_exception(ex, self.mainWindow)


class RepositoryWindow(QDialog):
    def __init__(self, main_window):
        super(RepositoryWindow, self).__init__()
        loadUi("create_repository.ui", self)
        self.saveButton.clicked.connect(self.add_repository)
        self.typeComboBox.addItems(pulse.get_adapter_list("repository"))
        self.mainWindow = main_window
        self.settings_textEdit.setPlaceholderText(SETTINGS_DEFAULT_TEXT)

    def add_repository(self):
        # TODO : CBB detect the adapter mandatory attributes and show them in the interface
        try:
            self.mainWindow.connection.add_repository(
                name=self.name_lineEdit.text(),
                adapter=self.typeComboBox.currentText(),
                login=self.username_lineEdit.text(),
                password=self.password_lineEdit.text(),
                **text_settings_to_dict(self.settings_textEdit.toPlainText())
            )
            self.mainWindow.message_user("Repository successfully added " + self.name_lineEdit.text(), "INFO")
            # TODO: CBB ask a confirmation if the repository is not reachable
            self.close()
        except Exception as ex:
            print_exception(ex, self.mainWindow)


class ConnectWindow(QDialog):
    def __init__(self, main_window):
        super(ConnectWindow, self).__init__()
        loadUi("connect_database.ui", self)
        self.connectButton.clicked.connect(self.connect_button)
        adapters = pulse.get_adapter_list("database")
        self.typeComboBox.addItems(adapters)
        self.mainWindow = main_window
        self.settings_textEdit.setPlaceholderText(SETTINGS_DEFAULT_TEXT)
        if not self.mainWindow.settings.contains('db_type'):
            return
        try:
            index = adapters.index(self.mainWindow.settings.value('db_type'))
            self.typeComboBox.setCurrentIndex(index)
            self.path_lineEdit.setText(self.mainWindow.settings.value('path'))
            self.username_lineEdit.setText(self.mainWindow.settings.value('username'))
            self.password_lineEdit.setText(self.mainWindow.settings.value('password'))
            self.settings_textEdit.setPlainText(self.mainWindow.settings.value('connection_settings'))
        except Exception as ex:
            print_exception(ex, self)

    def connect_button(self):
        try:
            self.mainWindow.update_connection(
                self.typeComboBox.currentText(),
                self.path_lineEdit.text(),
                self.username_lineEdit.text(),
                self.password_lineEdit.text(),
                self.settings_textEdit.toPlainText()
            )
            # TODO : test connection quality before going further
            if self.saveConnectionSettingscheckBox.isChecked:
                self.mainWindow.settings.setValue('db_type', self.typeComboBox.currentText())
                self.mainWindow.settings.setValue('path', self.path_lineEdit.text())
                self.mainWindow.settings.setValue('username', self.username_lineEdit.text())
                self.mainWindow.settings.setValue('password', self.password_lineEdit.text())
                self.mainWindow.settings.setValue('connection_settings', self.settings_textEdit.toPlainText())
            self.close()
        except Exception as ex:
            print_exception(ex, self.mainWindow)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        loadUi("main_window.ui", self)

        self.treeWidget.itemClicked.connect(self.show_current_item_details)
        self.treeWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeWidget.customContextMenuRequested.connect(self.tree_rc_menu)
        self.treeWidget.setColumnCount(1)

        self.actionConnect_to_Pulse_Server.triggered.connect(self.open_connect_dialog)
        self.createProject_action.triggered.connect(self.open_create_project_dialog)
        self.createRepository_action.triggered.connect(self.open_repository_page)
        self.createResource_action.triggered.connect(self.create_resource)
        self.createResourceTemplate_action.triggered.connect(self.create_template)
        self.localProducts_action.triggered.connect(self.purge_products)

        self.filterEntity_lineEdit.returnPressed.connect(self.update_treeview)
        self.filterType_lineEdit.returnPressed.connect(self.update_treeview)
        self.filterTemplates_checkBox.stateChanged.connect(self.update_treeview)

        self.project_comboBox.activated.connect(self.update_project)

        self.filter_groupBox.setChecked(False)
        self.mode_buttonGroup.buttonClicked[int].connect(self.update_treeview)

        self.connection = None
        self.project_list = []
        self.project = None
        self.settings = QSettings('pulse_standalone', 'Main')
        if not self.settings.contains("'window size'"):
            self.show()
            self.message_user("No settings found", "INFO")
            return

        try:
            self.resize(self.settings.value('window size'))
            self.move(self.settings.value('window position'))
            # settings save the filter checkbox state in lowercase string, I have to convert it to boolean
            if self.settings.value('filter_visible') == "true":
                self.filter_groupBox.setChecked(True)
        except Exception as ex:
            print_exception(ex, self)
        self.show()
        self.message_user("Initializing Connection ...", "INFO")
        QApplication.processEvents()
        try:
            if self.update_connection(
                self.settings.value('db_type'),
                self.settings.value('path'),
                self.settings.value('username'),
                self.settings.value('password'),
                self.settings.value('connection_settings')
            ):
                self.update_treeview()
        except Exception as ex:
            print_exception(ex, self)

    def message_user(self, message_text, message_type="INFO"):
        self.message_label.setText(message_type + ": " + message_text)
        if message_type == "INFO":
            self.message_label.setStyleSheet("")
        else:
            self.message_label.setStyleSheet("background-color: pink;")

    def clear_displayed_data(self):
        self.treeWidget.clear()
        self.tableWidget.setRowCount(0)

    def update_connection(self, db_type, path, username, password, text_settings):
        self.message_user("Connecting to database...", "INFO")
        settings = text_settings_to_dict(text_settings)
        try:
            pass
            self.connection = pulse.Connection(db_type, path, username, password, **settings)
        except Exception as ex:
            print_exception(ex, self)
            self.setWindowTitle("Disconnected")
            return False
        self.setWindowTitle("Connected -- " + self.connection.path)
        self.project_list = self.connection.get_projects()
        self.update_project_list()
        self.message_user("Successful connection", "INFO")
        return True

    def update_project_list(self):
        self.project_comboBox.clear()
        self.project_comboBox.addItems(self.project_list)

        # try to restore last used project
        last_project = self.settings.value('current_project')
        if last_project:
            try:
                index = self.project_list.index(last_project)
                self.project_comboBox.setCurrentIndex(index)
            except ValueError:
                pass

        self.update_project()

    def update_project(self):
        self.clear_displayed_data()
        project_name = self.project_comboBox.currentText()
        self.settings.setValue('current_project', project_name)
        if project_name != "":
            self.project = self.connection.get_project(project_name)
            self.update_treeview()
        else:
            self.project = None

    def update_treeview(self):
        if not self.project:
            return
        self.message_user("Updating Tree View", "INFO")
        self.clear_displayed_data()
        if self.sandbox_pushButton.isChecked():
            self.sandbox_pushButton.setStyleSheet('QPushButton {font-weight: bold;}')
            self.project_pushButton.setStyleSheet('QPushButton {font-weight: normal;}')
            resources_uri = self.project.get_local_works(self.get_filter_string())
            try:
                for resource_uri in resources_uri:
                    uri_dict = pulse_uri.convert_to_dict(resource_uri)
                    if not self.filterTemplates_checkBox.isChecked() and uri_dict["entity"] == pulse.template_name:
                        continue
                    resource = self.project.get_resource(uri_dict["entity"], uri_dict["resource_type"])
                    work = pulse.Work(resource).read()
                    resource_item = PulseItem([resource_uri], work)
                    self.treeWidget.addTopLevelItem(resource_item)
                    for product_type in work.list_products():
                        product = work.get_product(product_type)
                        product_item = PulseItem([product_type], product)
                        resource_item.addChild(product_item)
            except Exception as ex:
                print_exception(ex, self)
                return
            self.tableWidget.setRowCount(0)
            self.message_user(str(len(resources_uri)) + " Work(s) listed", "INFO")
        else:
            self.project_pushButton.setStyleSheet('QPushButton {font-weight: bold;}')
            self.sandbox_pushButton.setStyleSheet('QPushButton {font-weight: normal;}')
            project_name = self.project_comboBox.currentText()
            resources = self.connection.db.find_uris(project_name, "Resource", self.get_filter_string())
            try:
                for resource_uri in resources:
                    uri_dict = pulse_uri.convert_to_dict(resource_uri)
                    if not self.filterTemplates_checkBox.isChecked() and uri_dict["entity"] == pulse_cfg.template_name:
                        continue
                    resource = self.project.get_resource(uri_dict["entity"], uri_dict["resource_type"])
                    resource_item = PulseItem([resource_uri], resource)
                    self.treeWidget.addTopLevelItem(resource_item)

                    # TODO : get commit products should an api method
                    for commit_uri in self.connection.db.find_uris(project_name, "Commit", resource_uri + "@*"):
                        version = commit_uri.split("@")[-1]
                        commit = resource.get_commit(int(version))
                        # TODO : format version as project preferences
                        commit_item = PulseItem(["V" + version.zfill(3)], commit)
                        resource_item.addChild(commit_item)

                        for product_uri in self.connection.db.find_uris(
                                project_name,
                                "CommitProduct",
                                resource_uri + ".*@" + version
                        ):
                            product_type = pulse_uri.convert_to_dict(product_uri)["product_type"]
                            product = pulse.CommitProduct(commit, product_type)
                            product_item = PulseItem([product_type], product)
                            if product.uri in self.project.get_local_commit_products():
                                set_tree_item_style(product_item, "downloaded")
                            commit_item.addChild(product_item)
            except Exception as ex:
                print_exception(ex, self)
                return
            self.tableWidget.setRowCount(0)
            self.message_user(str(len(resources)) + " Resource(s) listed", "INFO")

    def show_details(self, properties):
        self.tableWidget.setRowCount(len(properties))
        property_index = 0
        for property_name, value in properties.items():
            if type(value) == list:
                value = str(value)[1:-1]
            self.tableWidget.setItem(property_index, 0, QtWidgets.QTableWidgetItem(property_name))
            self.tableWidget.setItem(property_index, 1, QtWidgets.QTableWidgetItem(str(value)))
            property_index += 1
        # Table will fit the screen horizontally
        self.tableWidget.horizontalHeader().setStretchLastSection(True)
        self.tableWidget.horizontalHeader().setSectionResizeMode(
           QtWidgets.QHeaderView.Interactive)

    def get_filter_string(self):
        filter_entity = self.filterEntity_lineEdit.text()
        if filter_entity == "":
            filter_entity = "*"
        filter_type = self.filterType_lineEdit.text()
        if filter_type == "":
            filter_type = "*"
        return filter_entity + "-" + filter_type

    def show_current_item_details(self):
        try:
            item = self.treeWidget.currentItem()

            if isinstance(item.pulse_node, pulse.Resource):
                self.show_details({
                    "last_version": item.pulse_node.last_version,
                    "repository": item.pulse_node.repository,
                    "resource_template": item.pulse_node.resource_template,
                    "lock_user": item.pulse_node.lock_user
                })
            if isinstance(item.pulse_node, pulse.Commit):
                properties = {
                    "comment": item.pulse_node.comment,
                    "files": list(item.pulse_node.files.keys())
                }
                input_index = 1
                for product_uri in item.pulse_node.products_inputs:
                    properties["product input " + str(input_index)] = product_uri
                    input_index += 1
                self.show_details(properties)

            if isinstance(item.pulse_node, pulse.Work):
                properties = {
                    "directory": item.pulse_node.directory,
                    "version": item.pulse_node.version,
                }
                input_index = 1
                for product in item.pulse_node.get_inputs():
                    properties["product input " + str(input_index)] = product.uri
                    input_index += 1
                self.show_details(properties)

            if isinstance(item.pulse_node, pulse.WorkProduct):
                properties = {
                    "directory": item.pulse_node.directory,
                }
                input_index = 1
                for product in item.pulse_node.get_inputs():
                    properties["product input " + str(input_index)] = product.uri
                    input_index += 1
                self.show_details(properties)
        except Exception as ex:
            print_exception(ex, self)
            return

    def open_connect_dialog(self):
        connect_page = ConnectWindow(self)
        connect_page.exec_()

    def open_create_project_dialog(self):
        # ensure there's at least a repository before opening
        repositories = self.connection.get_repositories().keys()
        if not repositories:
            self.message_user("You have to create at least a repository before creating a project", "ERROR")
            return
        page = ProjectWindow(self, repositories)
        page.exec_()

    def open_repository_page(self):
        page = RepositoryWindow(self)
        page.exec_()

    def tree_rc_menu(self, pos):
        if not self.project:
            return
        item = self.treeWidget.currentItem()
        item1 = self.treeWidget.itemAt(pos)

        rc_menu = QMenu(self.treeWidget)

        if not item or not item1:
            action = rc_menu.addAction(self.tr("Create Resource"))
            action.triggered.connect(partial(self.create_resource, None))

        elif isinstance(item.pulse_node, pulse.Resource):
            action = rc_menu.addAction(self.tr("Create Resource"))
            action.triggered.connect(partial(self.create_resource, item))
            action2 = rc_menu.addAction(self.tr("Check out last version"))
            action2.triggered.connect(partial(self.checkout, item))

        elif isinstance(item.pulse_node, pulse.Commit):
            pass
            # action = rc_menu.addAction(self.tr("Commit Action"))
            # action.triggered.connect(partial(self.add_tree_item, item))

        elif isinstance(item.pulse_node, pulse.CommitProduct):
            action = rc_menu.addAction(self.tr("Download To Cache"))
            action.triggered.connect(partial(self.download_product, item))
            action2 = rc_menu.addAction(self.tr("Remove From Cache"))
            action2.triggered.connect(partial(self.remove_product, item))

        elif isinstance(item.pulse_node, pulse.WorkProduct):
            action = rc_menu.addAction(self.tr("Trash"))
            action.triggered.connect(partial(self.trash_product, item))
            action2 = rc_menu.addAction(self.tr("Edit Inputs"))
            action2.triggered.connect(partial(self.node_edit_inputs, item))

        elif isinstance(item.pulse_node, pulse.Work):
            action = rc_menu.addAction(self.tr("Commit"))
            action.triggered.connect(partial(self.commit_work, item))
            action2 = rc_menu.addAction(self.tr("Create Product"))
            action2.triggered.connect(partial(self.create_product, item))
            action3 = rc_menu.addAction(self.tr("Trash"))
            action3.triggered.connect(partial(self.trash_work, item))
            action4 = rc_menu.addAction(self.tr("Explore Directory"))
            action4.triggered.connect(partial(self.explore, item))
            action5 = rc_menu.addAction(self.tr("Edit Inputs"))
            action5.triggered.connect(partial(self.node_edit_inputs, item))

        rc_menu.exec_(self.treeWidget.mapToGlobal(pos))

    def node_edit_inputs(self, item):
        try:
            input_window = InputsWindow(self, item.pulse_node)
            input_window.show()
        except Exception as ex:
            print_exception(ex, self)
            return
    def explore(self, item):
        if not os.path.exists(item.pulse_node.directory):
            self.message_user("Directory missing : " + item.pulse_node.directory, message_type="ERROR")
            return
        webbrowser.open(item.pulse_node.directory)

    def trash_product(self, item):
        try:
            confirm = QMessageBox.question(
                self,
                'Confirm',
                "Are you sure you want to thrash this product?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            if confirm == QMessageBox.Yes:
                item.parent().pulse_node.trash_product(item.pulse_node.product_type)
                self.update_treeview()
                self.message_user("Product trashed")
            else:
                self.message_user("Process aborted")

        except Exception as ex:
            print_exception(ex, self)
            return

    def create_product(self, item):
        product_type, ok = QInputDialog.getText(self, "Input", "Product Type")
        if not ok:
            return
        try:
            item.pulse_node.create_product(product_type)
            self.message_user("Product Created " + product_type)
        except Exception as ex:
            print_exception(ex, self)
            return
        self.update_treeview()

    def commit_work(self, item):
        try:
            if not item.pulse_node.status():
                self.message_user("No changes to commit. Process Aborted", message_type="ERROR")
                return
            comment, ok = QInputDialog.getText(self, "Commit", "Optional Comment")
            if not ok:
                return
            commit = item.pulse_node.commit(comment=comment)
            self.message_user("commit to version " + str(commit.version))
        except Exception as ex:
            print_exception(ex, self)
            return
        self.update_treeview()

    def trash_work(self, item):

        try:
            trash_options = ("Keep work files in trash directory", "Delete files")
            trash_option, ok = QInputDialog.getItem(self, "Confirm", "Do you want to :", trash_options, 0, False)
            if not ok:
                self.message_user("Trash process aborted")
                return
            no_backup = trash_option == trash_options[1]
            item.pulse_node.trash(no_backup=no_backup)
            self.update_treeview()
            self.message_user("Work trashed")
        except Exception as ex:
            print_exception(ex, self)
            return

    def download_product(self, item):
        try:
            product_path = item.pulse_node.download()
            self.message_user("downloaded to " + product_path)
            set_tree_item_style(item, "downloaded")
        except Exception as ex:
            print_exception(ex, self)

    def remove_product(self, item):
        try:
            item.pulse_node.remove_from_local_products()
            self.message_user("Product removed from local cache")
            set_tree_item_style(item, None)
        except Exception as ex:
            print_exception(ex, self)

    def checkout(self, item):
        try:
            work = item.pulse_node.checkout()

            self.message_user("Checkout to :" + work.directory)
            self.sandbox_pushButton.setChecked(True)
            self.update_treeview()
            root = self.treeWidget.invisibleRootItem()
            child_count = root.childCount()
            for i in range(child_count):
                item = root.child(i)
                if item.pulse_node.resource.uri == work.resource.uri:
                    self.treeWidget.setCurrentItem(item, 0)
                    break
            self.show_current_item_details()
        except Exception as ex:
            print_exception(ex, self)
            return

    def create_resource(self, item=None):
        if not item:
            entity_name = ""
        else:
            entity_name = item.pulse_node.entity
        dialog = CreateResourceWindow(self, entity_name)
        dialog.exec_()


    def purge_products(self, item=None):
        dialog = LocalProductsWindow(self)
        dialog.exec_()

    def create_template(self, item=None):
        dialog = CreateResourceTemplateWindow(self)
        dialog.exec_()

    def closeEvent(self, event):
        try:
            self.settings.setValue('window size', self.size())
            self.settings.setValue('window position', self.pos())
            self.settings.setValue('project_name', self.project_comboBox.currentText())
            self.settings.setValue('filter_visible', self.filter_groupBox.isChecked())
        except Exception as ex:
            print_exception(ex, self)

app = QApplication(sys.argv)
main_window_app = MainWindow()
try:
    sys.exit(app.exec_())
except Exception as exit_exception:
    print('exiting')
    print(str(exit_exception))
