import sys
from PyQt5.uic import loadUi
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QApplication, QDialog, QTreeWidgetItem, QMenu, QAction, QMainWindow
from PyQt5.QtCore import Qt
from functools import partial
import pulse.api as pulse
import pulse.uri_standards as pulse_uri
from PyQt5.QtCore import QSettings

LOG = "interface"


class PulseItem(QTreeWidgetItem):
    def __init__(self, parent, pulse_node):
        super(PulseItem, self).__init__(parent)
        self.pulse_node = pulse_node


def text_settings_to_dict(text):
    settings = {}
    for prm in text.split("\n"):
        split_line = prm.split("=")
        settings[split_line[0].strip()] = split_line[1].strip()
    return settings


def message(message_text, message_type = "ERROR"):
    if LOG == "interface":
        mainwindow.message_label.setText(message_type + ": " + message_text)


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
        #TODO :  add the repository choice

    def create_resource(self):
        entity_name = self.entityName_lineEdit.text()
        if self.typeFromTemplate_radioButton.isChecked():
            entity_type = self.typeTemplate_comboBox.currentText()
        else:
            entity_type = self.typeCustom_lineEdit.text()
        #TODO : check the input strings are valid
        try:
            new_resource = self.mainWindow.project.create_resource(entity_name, entity_type)
        except Exception as e:
            message(str(e))
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

class ConnectWindow(QDialog):
    def __init__(self, mainWindow):
        super(ConnectWindow, self).__init__()
        loadUi("connect_database.ui", self)
        self.connectButton.clicked.connect(self.connect_button)
        #TODO : list available adapters
        #TODO : adapters should give the parameters they need to dynamicaly creates the interface
        self.mainWindow = mainWindow

    def connect_button(self):
        self.mainWindow.updateConnection(self.typeComboBox.currentText(), self.settings_textEdit.toPlainText())
        #TODO : force a username password parameters to have a dedicated password field
        #TODO : force a path parameter to database to inform the user the db path used
        #TODO : test connection quality before going further
        if self.saveConnectionSettingscheckBox.isChecked:
            self.mainWindow.settings.setValue('db_type', self.typeComboBox.currentText())
            self.mainWindow.settings.setValue('connection_settings', self.settings_textEdit.toPlainText())
        self.close()


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        loadUi("main_window.ui", self)
        self.treeWidget.itemClicked.connect(self.onItemClicked)
        self.treeWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeWidget.customContextMenuRequested.connect(self.tree_rc_menu)
        self.treeWidget.setColumnCount(1)

        self.actionConnect_to_Pulse_Server.triggered.connect(self.executeConnectPage)
        self.listResources_pushButton.clicked.connect(self.list_resources)

        self.connection = None
        self.project = None
        self.settings = QSettings('pulse_standalone', 'Main')
        try:
            self.resize(self.settings.value('window size'))
            self.move(self.settings.value('window position'))
            self.projectName_lineEdit.setText(self.settings.value('project_name'))

        except:
            pass
        try:
            self.updateConnection(self.settings.value('db_type'), self.settings.value('connection_settings'))
            self.update_project()
        except:
            pass
        self.show()

    def updateConnection(self, db_type, text_settings):
        settings = text_settings_to_dict(text_settings)
        try:
            self.connection = pulse.Connection(db_type, **settings)
        except Exception as e:
            message(str(e))
            self.setWindowTitle("Disconnected")
            return False
        self.setWindowTitle("Connected")
        message("Successfull connection", "INFO")
        return True

    def update_project(self):
        project_name = self.projectName_lineEdit.text()
        if project_name != "":
            try:
                self.project = self.connection.get_project(self.projectName_lineEdit.text())
            except Exception as e:
                message(str(e))
                return False
        return True

    def list_resources(self):
        if not self.project:
            if not self.update_project():
                return
        self.treeWidget.clear()
        project_name = self.projectName_lineEdit.text()
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
            message(str(e), "ERROR")
            return
        message(str(len(resources)) + " Resource(s) listed", "INFO")

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
        connect_page.exec_()

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
mainwindow = MainWindow()

try:
    sys.exit(app.exec_())
except:
    print('exiting')