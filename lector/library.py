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
import pickle
import logging
import pathlib

from PyQt5 import QtGui, QtCore

from app.lector.lector import database

logger = logging.getLogger(__name__)


class Library:
    def __init__(self, parent):
        self.main_window = parent
        self.libraryModel = None
        self._translate = QtCore.QCoreApplication.translate

    def generate_model(self, mode, parsed_books=None, is_database_ready=True):
        if mode == 'build':
            self.libraryModel = QtGui.QStandardItemModel()
            self.libraryModel.setColumnCount(10)

            books = database.DatabaseFunctions(
                self.main_window.database_path).fetch_data(
                    ('Title', 'Author', 'Year', 'DateAdded', 'Path',
                     'Position', 'ISBN', 'Tags', 'Hash', 'LastAccessed',
                     'Addition'),
                    'books',
                    {'Title': ''},
                    'LIKE')

            if not books:
                logger.warning('Database returned nothing')
                return

        elif mode == 'addition':
            # Assumes self.libraryModel already exists and may be extended
            # Because any additional books have already been added to the
            # database using background threads

            books = []
            current_qdatetime = QtCore.QDateTime().currentDateTime()
            for i in parsed_books.items():
                try:
                    _tags = i[1]['tags']
                    if _tags:
                        _tags = ', '.join([j for j in _tags if j])
                except:  # Continuing seems more important than being correct
                    _tags = []
                    logger.warning('Tag generation error for: ' + i[1]['path'])

                books.append([
                    i[1]['title'], i[1]['author'], i[1]['year'], current_qdatetime,
                    i[1]['path'], None, i[1]['isbn'], _tags, i[0], None, i[1]['addition_mode']])

        else:
            return

        for i in books:
            # The database query returns (or the extension data is)
            # an iterable with the following indices:
            title = i[0]
            author = i[1]
            year = i[2]
            path = i[4]
            addition_mode = i[10]

            last_accessed = i[9]
            if last_accessed and not isinstance(last_accessed, QtCore.QDateTime):
                last_accessed = pickle.loads(last_accessed)

            tags = i[7]
            if isinstance(tags, list):  # When files are added for the first time
                if tags:
                    tags = ', '.join(str(this_tag) for this_tag in tags)
                else:
                    tags = None

            try:
                date_added = pickle.loads(i[3])
            except TypeError:  # Because of datetime.datetime.now() above
                date_added = i[3]

            position_perc = None
            position = i[5]
            if position:
                position = pickle.loads(position)
                position_perc = generate_position_percentage(position)

            try:
                file_exists = os.path.exists(path)
            except UnicodeEncodeError:
                print('Library: Unicode encoding error')

            all_metadata = {
                'title': title,
                'author': author,
                'year': year,
                'date_added': date_added,
                'path': path,
                'position': position,
                'isbn': i[6],
                'tags': tags,
                'hash': i[8],
                'last_accessed': last_accessed,
                'addition_mode': addition_mode,
                'file_exists': file_exists}

            author_string = self._translate('Library', 'Author')
            year_string = self._translate('Library', 'Year')
            tooltip_string = f'{title} \n{author_string}: {author} \n{year_string}: {str(year)}'

            # Additional data can be set using an incrementing
            # QtCore.Qt.UserRole
            # QtCore.Qt.DisplayRole is the same as item.setText()
            # The model is a single row and has no columns

            # No covers are set at this time
            # That is to be achieved by way of the culling function
            img_pixmap = QtGui.QPixmap()
            img_pixmap.load(':/images/blank.png')
            img_pixmap = img_pixmap.scaled(
                420, 600, QtCore.Qt.IgnoreAspectRatio)
            item = QtGui.QStandardItem()
            item.setToolTip(tooltip_string)

            # Just keep the following order. It's way too much trouble otherwise
            # User roles have to be correlated to sorting order below
            item.setData(title, QtCore.Qt.UserRole)
            item.setData(author, QtCore.Qt.UserRole + 1)
            item.setData(year, QtCore.Qt.UserRole + 2)
            item.setData(all_metadata, QtCore.Qt.UserRole + 3)
            item.setData(tags, QtCore.Qt.UserRole + 4)
            item.setData(file_exists, QtCore.Qt.UserRole + 5)
            item.setData(i[8], QtCore.Qt.UserRole + 6)  # File hash
            item.setData(position_perc, QtCore.Qt.UserRole + 7)
            item.setData(False, QtCore.Qt.UserRole + 8) # Is the cover being displayed?
            item.setData(date_added, QtCore.Qt.UserRole + 9)
            item.setData(last_accessed, QtCore.Qt.UserRole + 12)
            item.setData(path, QtCore.Qt.UserRole + 13)
            item.setIcon(QtGui.QIcon(img_pixmap))

            self.libraryModel.appendRow(item)

    def generate_proxymodels(self):
        self.update_proxymodels()

    def update_proxymodels(self):
        pass

    def generate_library_tags(self):
        db_library_directories = database.DatabaseFunctions(
            self.main_window.database_path).fetch_data(
                ('Path', 'Name', 'Tags'),
                'directories',  # This checks the directories table NOT the book one
                {'Path': ''},
                'LIKE')

        if db_library_directories:  # Empty database / table
            library_directories = {
                i[0]: (i[1], i[2]) for i in db_library_directories}

        else:
            db_library_directories = database.DatabaseFunctions(
                self.main_window.database_path).fetch_data(
                    ('Path',),
                    'books', # THIS CHECKS THE BOOKS TABLE
                    {'Path': ''},
                    'LIKE')

            library_directories = None
            if db_library_directories:
                library_directories = {
                    i[0]: (None, None) for i in db_library_directories}

        def get_tags(all_metadata):
            path = os.path.dirname(all_metadata['path'])
            path_ref = pathlib.Path(path)

            for i in library_directories:
                if i == path or pathlib.Path(i) in path_ref.parents:
                    directory_name = library_directories[i][0]
                    if directory_name:
                        directory_name = directory_name.lower()
                    else:
                        directory_name = i.rsplit(os.sep)[-1].lower()

                    directory_tags = library_directories[i][1]
                    if directory_tags:
                        directory_tags = directory_tags.lower()

                    return directory_name, directory_tags

            # A file is assigned a 'manually added' tag in case it isn't
            # in any designated library directory
            added_string = self._translate('Library', 'manually added')
            return added_string.lower(), None

        # Generate tags for the QStandardItemModel
        # This isn't triggered for an empty view model
        for i in range(self.libraryModel.rowCount()):
            this_item = self.libraryModel.item(i, 0)
            all_metadata = this_item.data(QtCore.Qt.UserRole + 3)
            directory_name, directory_tags = get_tags(all_metadata)

            this_item.setData(directory_name, QtCore.Qt.UserRole + 10)
            this_item.setData(directory_tags, QtCore.Qt.UserRole + 11)

    def prune_models(self, valid_paths):
        # To be executed when the library is updated by folder
        # All files in unselected directories will have to be removed
        # from both of the models
        # They will also have to be deleted from the library
        invalid_paths = []
        deletable_persistent_indexes = []

        for i in range(self.libraryModel.rowCount()):
            item = self.libraryModel.item(i)

            item_metadata = item.data(QtCore.Qt.UserRole + 3)
            book_path = item_metadata['path']
            try:
                addition_mode = item_metadata['addition_mode']
            except KeyError:
                addition_mode = 'automatic'
                logger.error('Libary: Error setting addition mode for prune')

            if (book_path not in valid_paths and
                    (addition_mode != 'manual' or addition_mode is None)):

                invalid_paths.append(book_path)
                deletable_persistent_indexes.append(
                    QtCore.QPersistentModelIndex(item.index()))

        if deletable_persistent_indexes:
            for i in deletable_persistent_indexes:
                self.libraryModel.removeRow(i.row())

        # Remove invalid paths from the database as well
        database.DatabaseFunctions(
            self.main_window.database_path).delete_from_database('Path', invalid_paths)


def generate_position_percentage(position):
    if not position:
        return None

    if position['is_read']:
        position_perc = 1
    else:
        try:
            position_perc = (
                position['current_block'] / position['total_blocks'])
        except (KeyError, ZeroDivisionError):
            try:
                position_perc = (
                    position['current_chapter'] / position['total_chapters'])
            except KeyError:
                position_perc = None

    return position_perc
