import sys
from PyQt5.uic import loadUi
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QApplication, QDialog, QTreeWidgetItem, QMenu, QAction, QMainWindow
from PyQt5.QtCore import Qt
from functools import partial
import pulse.api as pulse
import pulse.uri_standards as pulse_uri
from PyQt5.QtCore import QSettings
import traceback
import os

#TODO : add template resource funtion

LOG = "interface"
SETTINGS_DEFAULT_TEXT = "attribute = value"

class PulseItem(QTreeWidgetItem):
    def __init__(self, parent, pulse_node):
        super(PulseItem, self).__init__(parent)
        self.pulse_node = pulse_node


def text_settings_to_dict(text):
    settings = {}
    for prm in text.split("\n"):
        if "=" in prm:
            split_line = prm.split("=")
            settings[split_line[0].strip()] = split_line[1].strip()
    return settings


def message_user(message_text, message_type=""):
    mainwindow.message_label.setText(message_type + ": " + message_text)


def print_exception(exception):
    if LOG == "interface":
        message_user(str(exception), message_type=type(exception).__name__)
        traceback.print_exc()


class CreateResourceWindow(QDialog):
    def __init__(self, mainWindow, entity_name):
        super(CreateResourceWindow, self).__init__()
        loadUi("create_resource.ui", self)
        self.mainWindow = mainWindow
        self.typeFromTemplate_radioButton.clicked.connect(self.typeFromTemplateChecked)
        self.typeCustom_radioButton.clicked.connect(self.typeCustomChecked)
        self.entityName_lineEdit.setText(entity_name)
        self.createResource_pushButton.clicked.connect(self.create_resource)
        self.template_types = [pulse_uri.convert_to_dict(x)["resource_type"] for x in self.mainWindow.connection.db.find_uris(mainWindow.project.name, "Resource", "_template-*")]
        self.typeTemplate_comboBox.addItems(self.template_types)
        self.repository_comboBox.clear()
        # add the repository choice
        self.repositories = list(mainWindow.connection.get_repositories().keys())
        display_repo_names = []
        i = 0
        default_repository_index = 0
        for repo_name in self.repositories:
            if repo_name == mainWindow.project.cfg.default_repository:
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
        #TODO : check the input strings are valid

        try:
            new_resource = self.mainWindow.project.create_resource(
                entity_name,
                entity_type,
                repository=self.repositories[self.repository_comboBox.currentIndex()]
            )
        except Exception as e:
            print_exception(e)
            return
        resource_item = PulseItem([new_resource.uri], new_resource)
        self.mainWindow.treeWidget.addTopLevelItem(resource_item)
        self.close()

    def typeFromTemplateChecked(self):
        self.typeTemplate_comboBox.setEnabled(True)
        self.typeCustom_lineEdit.setEnabled(False)

    def typeCustomChecked(self):
        self.typeTemplate_comboBox.setEnabled(False)
        self.typeCustom_lineEdit.setEnabled(True)

class ProjectWindow(QDialog):
    def __init__(self, mainWindow):
        #TODO : add a tooltip to explain how to add an env var in pathes
        super(ProjectWindow, self).__init__()
        loadUi("create_project.ui", self)
        self.createProject_pushButton.clicked.connect(self.create_project)
        self.mainWindow = mainWindow
        self.repository_comboBox.clear()
        self.repository_comboBox.addItems(mainWindow.connection.get_repositories().keys())
        self.sandboxPath_lineEdit.setText(os.path.join(os.path.expanduser("~"), "pulse_sandbox"))
        self.versionPrefix_lineEdit.setText(pulse.DEFAULT_VERSION_PREFIX)
        self.versionPadding_spinBox.setValue(pulse.DEFAULT_VERSION_PADDING)
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
                version_padding=self.versionPadding_spinBox.value(),
                version_prefix=self.versionPrefix_lineEdit.text()
            )

            message_user("project " + self.name_lineEdit.text() + " successfully created")
            self.close()
            self.mainWindow.project_comboBox.addItem(self.name_lineEdit.text())
            self.mainWindow.project_comboBox.setCurrentIndex(self.mainWindow.project_comboBox.count() - 1)
            self.mainWindow.update_project()
        except Exception as e:
            print_exception(e)


class RepositoryWindow(QDialog):
    def __init__(self, mainWindow):
        super(RepositoryWindow, self).__init__()
        loadUi("create_repository.ui", self)
        self.saveButton.clicked.connect(self.add_repository)
        self.typeComboBox.addItems(pulse.get_adapter_list("repository"))
        self.mainWindow = mainWindow
        self.settings_textEdit.setPlaceholderText(SETTINGS_DEFAULT_TEXT)


    def add_repository(self):
        #TODO : detect the adapter mandatory attributes and show them in the interface
        try:
            self.mainWindow.connection.add_repository(
                name=self.name_lineEdit.text(),
                adapter=self.typeComboBox.currentText(),
                login=self.username_lineEdit.text(),
                password=self.password_lineEdit.text(),
                **text_settings_to_dict(self.settings_textEdit.toPlainText())
            )
        except Exception as ex:
            print_exception(ex)
        message_user("Repository successfully added " + self.name_lineEdit.text(), "INFO")
        self.close()


class ConnectWindow(QDialog):
    def __init__(self, mainWindow):
        super(ConnectWindow, self).__init__()
        loadUi("connect_database.ui", self)
        self.connectButton.clicked.connect(self.connect_button)
        self.typeComboBox.addItems(pulse.get_adapter_list("database"))
        self.mainWindow = mainWindow
        self.settings_textEdit.setPlaceholderText(SETTINGS_DEFAULT_TEXT)

    def connect_button(self):
        try:
            self.mainWindow.updateConnection(
                self.typeComboBox.currentText(),
                self.path_lineEdit.text(),
                self.username_lineEdit.text(),
                self.password_lineEdit.text(),
                self.settings_textEdit.toPlainText()
            )
            #TODO : test connection quality before going further
            if self.saveConnectionSettingscheckBox.isChecked:
                self.mainWindow.settings.setValue('db_type', self.typeComboBox.currentText())
                self.mainWindow.settings.setValue('path', self.path_lineEdit.text())
                self.mainWindow.settings.setValue('username', self.username_lineEdit.text())
                self.mainWindow.settings.setValue('password', self.password_lineEdit.text())
                self.mainWindow.settings.setValue('connection_settings', self.settings_textEdit.toPlainText())
            self.close()
        except Exception as ex:
            print_exception(ex)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        loadUi("main_window.ui", self)
        self.treeWidget.itemClicked.connect(self.onItemClicked)
        self.treeWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeWidget.customContextMenuRequested.connect(self.tree_rc_menu)
        self.treeWidget.setColumnCount(1)

        self.actionConnect_to_Pulse_Server.triggered.connect(self.executeConnectPage)
        self.projectCreate_action.triggered.connect(self.executeCreateProjectPage)
        self.actionCreate_Repository.triggered.connect(self.executeRepositoryPage)

        self.listResources_pushButton.clicked.connect(self.list_resources)
        self.project_comboBox.activated.connect(self.update_project)

        self.connection = None
        self.project_list = []
        self.project = None
        self.settings = QSettings('pulse_standalone', 'Main')
        try:
            self.resize(self.settings.value('window size'))
            self.move(self.settings.value('window position'))
            #TODO set project as settings

        except:
            pass
        try:
            self.updateConnection(
                self.settings.value('db_type'),
                self.settings.value('path'),
                self.settings.value('username'),
                self.settings.value('password'),
                self.settings.value('connection_settings')
            )
            self.update_project()
        except:
            pass
        self.show()

    def clear_displayed_data(self):
        self.treeWidget.clear()
        self.tableWidget.setRowCount(0)

    def updateConnection(self, db_type, path, username, password, text_settings):
        settings = text_settings_to_dict(text_settings)
        try:
            self.connection = pulse.Connection(db_type, path, username, password, **settings)
        except Exception as e:
            print_exception(e)
            self.setWindowTitle("Disconnected")
            return False
        self.setWindowTitle("Connected -- " + self.connection.path)
        self.project_list = self.connection.get_projects()
        self.update_project_list()
        message_user("Successfull connection", "INFO")
        return True

    def update_project_list(self):
        self.project_comboBox.clear()
        self.project_comboBox.addItems(self.project_list)
        self.update_project()

    def update_project(self):
        self.clear_displayed_data()
        project_name = self.project_comboBox.currentText()
        if project_name != "":
            self.project = self.connection.get_project(project_name)
        else:
            self.project = None


    def list_resources(self):
        if not self.project:
            return
        self.treeWidget.clear()
        project_name = self.project_comboBox.currentText()
        filter = self.filterEntity_lineEdit.text() + "-" + self.filterType_lineEdit.text()
        resources = self.connection.db.find_uris(project_name, "Resource", filter)
        try:
            for resource_uri in resources:
                uri_dict = pulse_uri.convert_to_dict(resource_uri)
                resource = self.project.get_resource(uri_dict["entity"], uri_dict["resource_type"])
                resource_item = PulseItem([resource_uri], resource)
                self.treeWidget.addTopLevelItem(resource_item)

                for commit_uri in self.connection.db.find_uris(project_name, "Commit", resource_uri + "@*"):
                    version = commit_uri.split("@")[-1]
                    commit = resource.get_commit(int(version))

                    commit_item = PulseItem(["V" + version.zfill(3)], commit)
                    resource_item.addChild(commit_item)

                    for product_uri in self.connection.db.find_uris(project_name, "CommitProduct", resource_uri + ".*@" + version):
                        product_type = pulse_uri.convert_to_dict(product_uri)["product_type"]
                        product = pulse.CommitProduct(commit, product_type)
                        product_item = PulseItem([product_type], product)
                        commit_item.addChild(product_item)
        except Exception as e:
            print_exception(e)
            return
        message_user(str(len(resources)) + " Resource(s) listed", "INFO")

    def showDetails(self, node, properties):
        self.tableWidget.setRowCount(len(properties))
        property_index = 0
        for property_name in properties:
            value = getattr(node, property_name)
            self.tableWidget.setItem(property_index, 0, QtWidgets.QTableWidgetItem(property_name))
            self.tableWidget.setItem(property_index, 1, QtWidgets.QTableWidgetItem(str(value)))
            property_index += 1
        # Table will fit the screen horizontally
        self.tableWidget.horizontalHeader().setStretchLastSection(True)
        self.tableWidget.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch)

    def onItemClicked(self):
        item = self.treeWidget.currentItem()
        if isinstance(item.pulse_node, pulse.Resource):
            self.showDetails(item.pulse_node, [
                "last_version",
                "repository",
                "resource_template",
                "lock_user"
            ])
        if isinstance(item.pulse_node, pulse.Commit):
            self.showDetails(item.pulse_node, [
                "comment",
                "products_inputs",
            ])

    def executeConnectPage(self, checked=None):
        connect_page = ConnectWindow(self)
        try:
            connect_page.path_lineEdit.setText(self.settings.value('path'))
            connect_page.username_lineEdit.setText(self.settings.value('username'))
            connect_page.password_lineEdit.setText(self.settings.value('password'))
            connect_page.settings_textEdit.setPlainText(self.settings.value('connection_settings'))
        except Exception as ex:
            print(Exception)
            pass
        connect_page.exec_()

    def executeCreateProjectPage(self):
        #TODO : check there's an exisiting repository before opening
        page = ProjectWindow(self)
        page.exec_()

    def executeRepositoryPage(self):
        page = RepositoryWindow(self)
        page.exec_()

    def tree_rc_menu(self, pos):
        if not self.project:
            return
        item = self.treeWidget.currentItem()
        item1 = self.treeWidget.itemAt(pos)

        popMenu = QMenu(self.treeWidget)

        if not item or not item1:
            action = popMenu.addAction(self.tr("Create Resource"))
            action.triggered.connect(partial(self.create_resource, None))
        elif isinstance(item.pulse_node, pulse.Resource):
            action = popMenu.addAction(self.tr("Create Resource"))
            action.triggered.connect(partial(self.create_resource, item))
        elif isinstance(item.pulse_node, pulse.Commit):
            action = popMenu.addAction(self.tr("Commit Action"))
            action.triggered.connect(partial(self.TreeItem_Add, item))
        elif isinstance(item.pulse_node, pulse.CommitProduct):
            action = popMenu.addAction(self.tr("Product Action"))
            action.triggered.connect(partial(self.TreeItem_Add, item))
        popMenu.exec_(self.treeWidget.mapToGlobal(pos))


    def TreeItem_Add(self, item):
        print(item.pulse_node)

    def create_resource(self, item=None):
        if not item:
            entity_name = ""
        else:
            entity_name = item.pulse_node.entity
        dialog = CreateResourceWindow(self, entity_name)
        dialog.exec_()

    def getParentPath(self, item):
        def getParent(item, outstring):
            if item.parent() is None:
                return outstring
            outstring = item.parent.text(0) + "/" + outstring
            return getParent(item.parent, outstring)

        output = getParent(item, item.text(0))
        return output

    def closeEvent(self, event):
        self.settings.setValue('window size', self.size())
        self.settings.setValue('window position', self.pos())
        self.settings.setValue('project_name', self.projectName_lineEdit.text())


app = QApplication(sys.argv)
try:
    mainwindow = MainWindow()
except Exception as e:
    traceback.print_exc()

try:
    sys.exit(app.exec_())
except:
    print('exiting')