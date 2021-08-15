#!/usr/bin/env python3

# This file is a part of Lector, a Qt based ebook reader
# Copyright (C) 2017-2019 BasioMeusPuga

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import gc
import sys
import hashlib
import pathlib

# This allows for the program to be launched from the
# dir where it's been copied instead of needing to be
# installed
install_dir = os.path.realpath(__file__)
install_dir = pathlib.Path(install_dir).parents[1]
sys.path.append(str(install_dir))

from PyQt5 import QtWidgets, QtGui, QtCore

# Init logging
# Must be done first and at the module level
# or it won't work properly in case of the imports below
from app.lector.lector.logger import init_logging, VERSION
logger = init_logging(sys.argv)
logger.log(60, f'Lector {VERSION} - Application started')

from app.lector.lector import database
from app.lector.lector import sorter
from app.lector.lector.toolbars import LibraryToolBar, BookToolBar
from app.lector.lector.widgets import Tab
from app.lector.lector.delegates import LibraryDelegate
from app.lector.lector.threaded import BackGroundTabUpdate, BackGroundBookAddition, BackGroundBookDeletion
from app.lector.lector.library import Library
from app.lector.lector.guifunctions import QImageFactory, ViewProfileModification
from app.lector.lector.settings import Settings
from app.lector.lector.settingsdialog import SettingsUI
from app.lector.lector.metadatadialog import MetadataUI
from app.lector.lector.resources import mainwindow, resources


class MainUI(QtWidgets.QMainWindow, mainwindow.Ui_MainWindow):
    def __init__(self):
        super(MainUI, self).__init__()
        self.setupUi(self)

        # Set window icon
        self.setWindowIcon(
            QtGui.QIcon(':/images/Lector.png'))

        # Central Widget - Make borders disappear
        self.centralWidget().layout().setContentsMargins(0, 0, 0, 0)
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)

        # Initialize translation function
        self._translate = QtCore.QCoreApplication.translate

        # Empty variables that will be infested soon
        self.settings = {}
        self.thread = None  # Background Thread
        self.current_contentView = None  # For fullscreening purposes
        self.display_profiles = None
        self.current_profile_index = None
        self.comic_profile = {}
        self.database_path = None
        self.active_docks = []

        # Initialize application
        Settings(self).read_settings()  # This should populate all variables that need
                                        # to be remembered across sessions

        # Initialize icon factory
        self.QImageFactory = QImageFactory(self)

        # Initialize toolbars
        self.libraryToolBar = LibraryToolBar(self)
        self.bookToolBar = BookToolBar(self)

        # Widget declarations
        self.statusMessage = QtWidgets.QLabel()

        # Reference variables
        self.alignment_dict = {
            'left': self.bookToolBar.alignLeft,
            'right': self.bookToolBar.alignRight,
            'center': self.bookToolBar.alignCenter,
            'justify': self.bookToolBar.alignJustify}

        # Create the database in case it doesn't exist
        database.DatabaseInit(self.database_path)

        # Initialize settings dialog
        self.settingsDialog = SettingsUI(self)

        # Initialize metadata dialog
        self.metadataDialog = MetadataUI(self)

        # Make the statusbar invisible by default
        self.statusBar.setVisible(False)

        # Statusbar widgets
        self.statusMessage.setObjectName('statusMessage')
        self.statusBar.addPermanentWidget(self.statusMessage)
        self.errorButton = QtWidgets.QPushButton(self.statusBar)
        self.errorButton.setIcon(QtGui.QIcon(':/images/error.svg'))
        self.errorButton.setFlat(True)
        self.errorButton.setVisible(False)
        self.errorButton.setToolTip('What hast thou done?')
        self.errorButton.clicked.connect(self.show_errors)
        self.statusBar.addPermanentWidget(self.errorButton)
        self.sorterProgress = QtWidgets.QProgressBar()
        self.sorterProgress.setMaximumWidth(300)
        self.sorterProgress.setObjectName('sorterProgress')
        sorter.progressbar = self.sorterProgress  # This is so that updates can be
                                                  # connected to setValue
        self.statusBar.addWidget(self.sorterProgress)
        self.sorterProgress.setVisible(False)

        # Application wide temporary directory
        self.temp_dir = QtCore.QTemporaryDir()

        # Init the Library
        self.lib_ref = Library(self)

        # Initialize profile modification functions
        self.profile_functions = ViewProfileModification(self)

        # Toolbar display
        # Maybe make this a persistent option
        self.settings['show_bars'] = True

        # Library toolbar
        self.libraryToolBar.colorButton.triggered.connect(self.get_color)
        self.libraryToolBar.settingsButton.triggered.connect(
            lambda: self.show_settings(0))
        self.libraryToolBar.aboutButton.triggered.connect(
            lambda: self.show_settings(3))
        self.libraryToolBar.sortingBox.activated.connect(self.lib_ref.update_proxymodels)
        self.addToolBar(self.libraryToolBar)

        self.stackedWidget.setCurrentIndex(1)
        self.libraryToolBar.sortingBoxAction.setVisible(False)
        self.resizeEvent()

        # Book toolbar
        self.bookToolBar.addBookmarkButton.triggered.connect(
            lambda: self.tabWidget.currentWidget().sideDock.bookmarks.add_bookmark())
        self.bookToolBar.bookmarkButton.triggered.connect(
            lambda: self.tabWidget.currentWidget().toggle_side_dock(0))
        self.bookToolBar.annotationButton.triggered.connect(
            lambda: self.tabWidget.currentWidget().toggle_side_dock(1))
        self.bookToolBar.searchButton.triggered.connect(
            lambda: self.tabWidget.currentWidget().toggle_side_dock(2))
        self.bookToolBar.distractionFreeButton.triggered.connect(
            self.toggle_distraction_free)
        self.bookToolBar.fullscreenButton.triggered.connect(
            lambda: self.tabWidget.currentWidget().go_fullscreen())

        self.bookToolBar.doublePageButton.triggered.connect(self.change_page_view)
        self.bookToolBar.mangaModeButton.triggered.connect(self.change_page_view)
        self.bookToolBar.invertButton.triggered.connect(self.change_page_view)
        self.bookToolBar.rotateRightButton.triggered.connect(self.change_page_view)
        self.bookToolBar.rotateLeftButton.triggered.connect(self.change_page_view)
        if self.settings['double_page_mode']:
            self.bookToolBar.doublePageButton.setChecked(True)
        if self.settings['manga_mode']:
            self.bookToolBar.mangaModeButton.setChecked(True)
        if self.settings['invert_colors']:
            self.bookToolBar.invertButton.setChecked(True)

        for count, i in enumerate(self.display_profiles):
            self.bookToolBar.profileBox.setItemData(count, i, QtCore.Qt.UserRole)
        self.bookToolBar.profileBox.currentIndexChanged.connect(
            self.profile_functions.format_contentView)
        self.bookToolBar.profileBox.setCurrentIndex(self.current_profile_index)

        self.bookToolBar.fontBox.currentFontChanged.connect(self.modify_font)
        self.bookToolBar.fontSizeBox.currentIndexChanged.connect(self.modify_font)
        self.bookToolBar.lineSpacingUp.triggered.connect(self.modify_font)
        self.bookToolBar.lineSpacingDown.triggered.connect(self.modify_font)
        self.bookToolBar.paddingUp.triggered.connect(self.modify_font)
        self.bookToolBar.paddingDown.triggered.connect(self.modify_font)
        self.bookToolBar.resetProfile.triggered.connect(
            self.profile_functions.reset_profile)

        profile_index = self.bookToolBar.profileBox.currentIndex()
        current_profile = self.bookToolBar.profileBox.itemData(
            profile_index, QtCore.Qt.UserRole)
        for i in self.alignment_dict.items():
            i[1].triggered.connect(self.modify_font)
        self.alignment_dict[current_profile['text_alignment']].setChecked(True)

        self.bookToolBar.zoomIn.triggered.connect(
            self.modify_comic_view)
        self.bookToolBar.zoomOut.triggered.connect(
            self.modify_comic_view)
        self.bookToolBar.fitWidth.triggered.connect(
            lambda: self.modify_comic_view(False))
        self.bookToolBar.bestFit.triggered.connect(
            lambda: self.modify_comic_view(False))
        self.bookToolBar.originalSize.triggered.connect(
            lambda: self.modify_comic_view(False))
        self.bookToolBar.comicBGColor.clicked.connect(
            self.get_color)

        self.bookToolBar.colorBoxFG.clicked.connect(self.get_color)
        self.bookToolBar.colorBoxBG.clicked.connect(self.get_color)
        self.bookToolBar.tocBox.currentIndexChanged.connect(self.set_toc_position)
        self.addToolBar(self.bookToolBar)

        # Make the correct toolbar visible
        self.current_tab = self.tabWidget.currentIndex()
        self.tab_switch()
        self.tabWidget.currentChanged.connect(self.tab_switch)

        # Tab Widget formatting
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.setDocumentMode(True)
        self.tabWidget.tabBarClicked.connect(self.tab_disallow_library_movement)

        # Get list of available parsers
        self.available_parsers = '*.' + ' *.'.join(sorter.available_parsers)
        logger.log(60, 'Available parsers: ' + self.available_parsers)

        # The Library tab gets no button
        self.tabWidget.tabBar().setTabButton(
            0, QtWidgets.QTabBar.RightSide, None)
        self.tabWidget.widget(0).is_library = True
        self.tabWidget.tabCloseRequested.connect(self.tab_close)
        self.tabWidget.setTabBarAutoHide(True)

        # Init display models
        self.lib_ref.generate_model('build')
        self.lib_ref.generate_proxymodels()
        self.lib_ref.generate_library_tags()

        # Keyboard shortcuts
        self.ksDistractionFree = QtWidgets.QShortcut(QtGui.QKeySequence('Ctrl+D'), self)
        self.ksDistractionFree.setContext(QtCore.Qt.ApplicationShortcut)
        self.ksDistractionFree.activated.connect(self.toggle_distraction_free)

        self.ksExitAll = QtWidgets.QShortcut(QtGui.QKeySequence('Ctrl+Q'), self)
        self.ksExitAll.setContext(QtCore.Qt.ApplicationShortcut)
        self.ksExitAll.activated.connect(self.closeEvent)

        self.ksCloseTab = QtWidgets.QShortcut(QtGui.QKeySequence('Ctrl+W'), self)
        self.ksCloseTab.setContext(QtCore.Qt.ApplicationShortcut)
        self.ksCloseTab.activated.connect(self.tab_close)

        self.open_books_at_startup()

    def open_books_at_startup(self):
        # Last open books and command line books aren't being opened together
        # so that command line books are processed last and therefore retain focus

        # Open last... open books.
        # Then set the value to None for the next run
        if self.settings['last_open_books']:
            files_to_open = {i: None for i in self.settings['last_open_books']}
            self.open_files(files_to_open)
        else:
            self.settings['last_open_tab'] = None

    def process_post_hoc_files(self, file_list, open_files_after_processing):
        # Takes care of both dragged and dropped files
        # As well as files sent as command line arguments
        file_list = [i for i in file_list if os.path.exists(i)]
        if not file_list:
            return

        books = sorter.BookSorter(
            file_list,
            ('addition', 'manual'),
            self.database_path,
            self.settings,
            self.temp_dir.path())

        parsed_books, errors = books.initiate_threads()
        if not parsed_books and not open_files_after_processing:
            return

        database.DatabaseFunctions(self.database_path).add_to_database(parsed_books)
        self.lib_ref.generate_model('addition', parsed_books, True)

        file_dict = {i: None for i in file_list}
        if open_files_after_processing:
            self.open_files(file_dict)

        self.move_on(errors)

    def open_files(self, path_hash_dictionary):
        # file_paths is expected to be a dictionary
        # This allows for threading file opening
        # Which should speed up multiple file opening
        # especially @ application start
        file_paths = [i for i in path_hash_dictionary]

        for filename in path_hash_dictionary.items():

            file_md5 = filename[1]
            if not file_md5:
                try:
                    with open(filename[0], 'rb') as current_book:
                        first_bytes = current_book.read(1024 * 32)  # First 32KB of the file
                        file_md5 = hashlib.md5(first_bytes).hexdigest()
                except FileNotFoundError:
                    return

            # Remove any already open files
            # Set focus to last file in case only one is open
            for i in range(1, self.tabWidget.count()):
                tab_metadata = self.tabWidget.widget(i).metadata
                if tab_metadata['hash'] == file_md5:
                    file_paths.remove(filename[0])
                    if not file_paths:
                        self.tabWidget.setCurrentIndex(i)
                        return

        if not file_paths:
            return

        logger.info(
            'Attempting to open: ' + ', '.join(file_paths))

        contents, errors = sorter.BookSorter(
            file_paths,
            ('reading', None),
            self.database_path,
            self.settings,
            self.temp_dir.path()).initiate_threads()

        if errors:
            self.display_error_notification(errors)

        if not contents:
            logger.error('No parseable files found')
            return

        successfully_opened = []
        for i in contents:
            # New tabs are created here
            # Initial position adjustment is carried out by the tab itself
            file_data = contents[i]
            Tab(file_data, self)
            successfully_opened.append(file_data['path'])
        logger.info(
            'Successfully opened: ' + ', '.join(file_paths))

        if self.settings['last_open_tab'] == 'library':
            self.tabWidget.setCurrentIndex(0)
            self.settings['last_open_tab'] = None
            return

        for i in range(1, self.tabWidget.count()):
            this_path = self.tabWidget.widget(i).metadata['path']
            if self.settings['last_open_tab'] == this_path:
                self.tabWidget.setCurrentIndex(i)
                self.settings['last_open_tab'] = None
                return

        self.tabWidget.setCurrentIndex(self.tabWidget.count() - 1)

    def move_on(self, errors=None):
        self.settingsDialog.okButton.setEnabled(True)
        self.sorterProgress.setVisible(False)
        self.sorterProgress.setValue(0)

        # The errors argument is a list and will only be present
        # in case of addition and reading
        if errors:
            self.display_error_notification(errors)

        self.lib_ref.update_proxymodels()
        self.lib_ref.generate_library_tags()

    def tab_switch(self):
        try:
            # Disallow library tab movement
            # Does not need to be looped since the library
            # tab can only ever go to position 1
            if not self.tabWidget.widget(0).is_library:
                self.tabWidget.tabBar().moveTab(1, 0)

            if self.current_tab != 0:
                self.tabWidget.widget(
                    self.current_tab).update_last_accessed_time()
        except AttributeError:
            pass

        self.current_tab = self.tabWidget.currentIndex()

        # Hide all side docks whenever a tab is switched
        for i in range(1, self.tabWidget.count()):
            self.tabWidget.widget(i).sideDock.setVisible(False)

        # If library
        if self.tabWidget.currentIndex() == 0:
            self.resizeEvent()

            if self.settings['show_bars']:
                self.bookToolBar.hide()
                self.libraryToolBar.show()

        else:
            if self.settings['show_bars']:
                self.bookToolBar.show()
                self.libraryToolBar.hide()

            current_tab = self.tabWidget.currentWidget()
            self.bookToolBar.tocBox.setModel(current_tab.tocModel)
            self.bookToolBar.tocTreeView.expandAll()
            current_tab.set_tocBox_index(None, None)

            # Needed to set the contentView widget background
            # on first run. Subsequent runs might be redundant,
            # but it doesn't seem to visibly affect performance
            self.profile_functions.format_contentView()
            self.statusBar.setVisible(False)

            if self.bookToolBar.fontButton.isChecked():
                self.bookToolBar.customize_view_on()
            else:
                if current_tab.are_we_doing_images_only:
                    self.bookToolBar.searchButton.setVisible(False)
                    self.bookToolBar.annotationButton.setVisible(False)
                    self.bookToolBar.bookSeparator2.setVisible(False)
                    self.bookToolBar.bookSeparator3.setVisible(False)
                else:
                    self.bookToolBar.searchButton.setVisible(True)
                    self.bookToolBar.annotationButton.setVisible(True)
                    self.bookToolBar.bookSeparator2.setVisible(True)
                    self.bookToolBar.bookSeparator3.setVisible(True)

    def tab_close(self, tab_index=None):
        if not tab_index:
            tab_index = self.tabWidget.currentIndex()
            if tab_index == 0:
                return

        tab_metadata = self.tabWidget.widget(tab_index).metadata

        self.thread = BackGroundTabUpdate(
            self.database_path, [tab_metadata])
        self.thread.start()

        self.tabWidget.widget(tab_index).update_last_accessed_time()

        self.tabWidget.widget(tab_index).deleteLater()
        self.tabWidget.widget(tab_index).setParent(None)
        gc.collect()

    def tab_disallow_library_movement(self, tab_index):
        # Makes the library tab immovable
        if tab_index == 0:
            self.tabWidget.setMovable(False)
        else:
            self.tabWidget.setMovable(True)

    def set_toc_position(self, event=None):
        currentIndex = self.bookToolBar.tocTreeView.currentIndex()
        required_position = currentIndex.data(QtCore.Qt.UserRole)
        if not required_position:
            return  # Initial startup might return a None

        # The set_content method is universal
        # It's going to do position tracking
        current_tab = self.tabWidget.currentWidget()
        current_tab.set_content(required_position, True, True)

    def display_error_notification(self, errors):
        self.statusBar.setVisible(True)
        self.errorButton.setVisible(True)

    def show_errors(self):
        # TODO
        # Create a separate viewing area for errors
        # before showing the log

        self.show_settings(3)
        self.settingsDialog.aboutTabWidget.setCurrentIndex(1)
        self.errorButton.setVisible(False)
        self.statusBar.setVisible(False)

    def show_settings(self, stacked_widget_index):
        if not self.settingsDialog.isVisible():
            self.settingsDialog.show()
        else:
            self.settingsDialog.hide()

    #==================================================================
    # The contentView modification functions are in the guifunctions
    # module. self.profile_functions is the reference here.

    def get_color(self):
        self.profile_functions.get_color(
            self.sender().objectName())

    def modify_font(self):
        self.profile_functions.modify_font(
            self.sender().objectName())

    def modify_comic_view(self, key_pressed=None):
        if key_pressed:
            signal_sender = None
        else:
            signal_sender = self.sender().objectName()

        self.profile_functions.modify_comic_view(
            signal_sender, key_pressed)

    #=================================================================

    def change_page_view(self, key_pressed=False):
        # Switch page to whatever index is selected in the tocBox
        current_tab = self.tabWidget.currentWidget()
        chapter_number = current_tab.metadata['position']['current_chapter']

        # Set zoom mode to best fit to
        # make the transition less jarring
        # if the sender isn't the invert colors button
        if self.sender() != self.bookToolBar.invertButton:
            self.comic_profile['zoom_mode'] = 'bestFit'

        # Rotate the image left or right
        # The double page mode is incompatible with this
        if self.sender() == self.bookToolBar.rotateLeftButton:
            current_tab.generate_rotation(-90)
            self.bookToolBar.doublePageButton.setChecked(False)
        if self.sender() == self.bookToolBar.rotateRightButton:
            current_tab.generate_rotation(90)
            self.bookToolBar.doublePageButton.setChecked(False)
        if self.sender() == self.bookToolBar.doublePageButton:
            current_tab.image_rotation = 0

        # Toggle Double page mode / manga mode on keypress
        if key_pressed == QtCore.Qt.Key_D:
            self.bookToolBar.doublePageButton.setChecked(
                not self.bookToolBar.doublePageButton.isChecked())
        if key_pressed == QtCore.Qt.Key_M:
            self.bookToolBar.mangaModeButton.setChecked(
                not self.bookToolBar.mangaModeButton.isChecked())

        # Change settings according to the
        # current state of each of the toolbar buttons
        self.settings['double_page_mode'] = self.bookToolBar.doublePageButton.isChecked()
        self.settings['manga_mode'] = self.bookToolBar.mangaModeButton.isChecked()
        self.settings['invert_colors'] = self.bookToolBar.invertButton.isChecked()

        current_tab.set_content(chapter_number, False)

    def toggle_distraction_free(self):
        self.settings['show_bars'] = not self.settings['show_bars']

        if self.tabWidget.count() > 1:
            self.tabWidget.tabBar().setVisible(
                self.settings['show_bars'])

        current_tab = self.tabWidget.currentIndex()
        if current_tab == 0:
            self.libraryToolBar.setVisible(
                not self.libraryToolBar.isVisible())
        else:
            self.bookToolBar.setVisible(
                not self.bookToolBar.isVisible())

    def resizeEvent(self, event=None):
        return

    def closeEvent(self, event=None):
        if event:
            event.ignore()

        self.hide()
        self.metadataDialog.hide()
        self.settingsDialog.hide()
        self.temp_dir.remove()
        for this_dock in self.active_docks:
            try:
                this_dock.setVisible(False)
            except RuntimeError:
                pass

        self.settings['last_open_books'] = []
        if self.tabWidget.count() > 1:

            # All tabs must be iterated upon here
            all_metadata = []
            for i in range(1, self.tabWidget.count()):
                tab_metadata = self.tabWidget.widget(i).metadata
                all_metadata.append(tab_metadata)

                if self.settings['remember_files']:
                    self.settings['last_open_books'].append(tab_metadata['path'])

            Settings(self).save_settings()
            self.thread = BackGroundTabUpdate(
                self.database_path, all_metadata)
            self.thread.finished.connect(self.database_care)
            self.thread.start()

        else:
            Settings(self).save_settings()
            self.database_care()

    def database_care(self):
        database.DatabaseFunctions(self.database_path).vacuum_database()
        QtWidgets.qApp.exit()


# def main():
#     # before we create the app, we hijack QT_AUTO_SCREEN_SCALE_FACTOR to force device scaling to be accurate
#     os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
#     # Make icons sharp in HiDPI screen
#     QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
#     QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)

#     app = QtWidgets.QApplication(sys.argv)
#     app.setApplicationName('Lector')  # This is needed for QStandardPaths
#                                       # and my own hubris

#     # Internationalization support
#     translator = QtCore.QTranslator()
#     translations_found = translator.load(
#         QtCore.QLocale.system(), ':/translations/translations_bin/Lector_')
#     app.installTranslator(translator)

#     translations_out_string = ' (Translations found)'
#     if not translations_found:
#         translations_out_string = ' (No translations found)'
#     print(f'Locale: {QtCore.QLocale.system().name()}' + translations_out_string)

#     form = MainUI()
#     form.show()
#     form.resizeEvent()
#     app.exec_()


# if __name__ == '__main__':
#     main()
