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

import logging
import pathlib

from PyQt5 import QtCore, QtWidgets
from app.lector.lector.resources import pie_chart

logger = logging.getLogger(__name__)


class BookmarkProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent=None):
        super(BookmarkProxyModel, self).__init__(parent)
        self.parent = parent
        self.parentTab = self.parent.parent
        self.filter_text = None

    def setFilterParams(self, filter_text):
        self.filter_text = filter_text

    def setData(self, index, value, role):
        if role == QtCore.Qt.EditRole:
            source_index = self.mapToSource(index)
            identifier = self.sourceModel().data(source_index, QtCore.Qt.UserRole + 2)

            self.sourceModel().setData(source_index, value, QtCore.Qt.DisplayRole)
            self.parentTab.metadata['bookmarks'][identifier]['description'] = value

            return True

class MostExcellentFileSystemModel(QtWidgets.QFileSystemModel):
    # Directories are tracked on the basis of their paths
    # Poll the tag_data dictionary to get User selection
    def __init__(self, tag_data, parent=None):
        super(MostExcellentFileSystemModel, self).__init__(parent)
        self.tag_data = tag_data
        self.field_dict = {
            0: 'check_state',
            4: 'name',
            5: 'tags'}

    def columnCount(self, parent):
        # The QFileSystemModel returns 4 columns by default
        # Columns 1, 2, 3 will be present but hidden
        return 6

    def headerData(self, col, orientation, role):
        # Columns not mentioned here will be hidden
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            column_dict = {
                0: 'Path',
                4: 'Name',
                5: 'Tags'}
            try:
                return column_dict[col]
            except KeyError:
                pass

    def data(self, index, role):
        if (index.column() in (4, 5)
                and (role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole)):

            read_field = self.field_dict[index.column()]
            try:
                return self.tag_data[self.filePath(index)][read_field]
            except KeyError:
                return QtCore.QVariant()

        if role == QtCore.Qt.CheckStateRole and index.column() == 0:
            return self.checkState(index)

        return QtWidgets.QFileSystemModel.data(self, index, role)

    def flags(self, index):
        if index.column() in (4, 5):
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable
        else:
            return QtWidgets.QFileSystemModel.flags(self, index) | QtCore.Qt.ItemIsUserCheckable

    def checkState(self, index):
        while index.isValid():
            index_path = self.filePath(index)
            if index_path in self.tag_data:
                return self.tag_data[index_path]['check_state']
            index = index.parent()
        return QtCore.Qt.Unchecked

    def setData(self, index, value, role):
        if (role == QtCore.Qt.EditRole or role == QtCore.Qt.CheckStateRole) and index.isValid():
            write_field = self.field_dict[index.column()]
            self.layoutAboutToBeChanged.emit()

            this_path = self.filePath(index)
            if this_path not in self.tag_data:
                self.populate_dictionary(this_path)
            self.tag_data[this_path][write_field] = value

            self.depopulate_dictionary()

            self.layoutChanged.emit()
            return True

    def populate_dictionary(self, path):
        self.tag_data[path] = {}
        self.tag_data[path]['name'] = None
        self.tag_data[path]['tags'] = None
        self.tag_data[path]['check_state'] = QtCore.Qt.Checked

    def depopulate_dictionary(self):
        # This keeps the tag_data dictionary manageable as well as preventing
        # weird ass behaviour when something is deselected and its tags are cleared
        deletable = set()
        for i in self.tag_data.items():
            all_data = [j[1] for j in i[1].items()]
            filtered_down = list(filter(lambda x: x is not None and x != 0, all_data))
            if not filtered_down:
                deletable.add(i[0])

        # Get untagged subdirectories too
        all_dirs = [i for i in self.tag_data]
        all_dirs.sort()

        def is_child(this_dir):
            this_path = pathlib.Path(this_dir)
            for i in all_dirs:
                if pathlib.Path(i) in this_path.parents:
                    # If a parent folder has tags, we only want the deletion
                    # to kick in in case the parent is also checked
                    if self.tag_data[i]['check_state'] == QtCore.Qt.Checked:
                        return True
            return False

        for i in all_dirs:
            if is_child(i):
                dir_tags = (self.tag_data[i]['name'], self.tag_data[i]['tags'])
                filtered_down = list(filter(lambda x: x is not None and x != '', dir_tags))
                if not filtered_down:
                    deletable.add(i)

        for i in deletable:
            del self.tag_data[i]
