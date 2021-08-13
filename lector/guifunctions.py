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

from PyQt5 import QtCore, QtGui, QtWidgets

from app.lector.lector import database
from app.lector.lector.settings import Settings
from app.lector.lector.resources import resources

logger = logging.getLogger(__name__)


class QImageFactory:
    def __init__(self, parent):
        self.parent = parent

    def get_image(self, image_name):
        icon_theme = self.parent.settings['icon_theme']
        icon_path = f':/images/{icon_theme}/{image_name}.svg'

        this_qicon = QtGui.QIcon(icon_path)
        return this_qicon

class ViewProfileModification:
    def __init__(self, main_window):
        self.main_window = main_window

        self.settings = self.main_window.settings
        self.bookToolBar = self.main_window.bookToolBar
        self.comic_profile = self.main_window.comic_profile
        self.tabWidget = self.main_window.tabWidget
        self.alignment_dict = self.main_window.alignment_dict

    def get_color(self, signal_sender):
        def open_color_dialog(current_color):
            color_dialog = QtWidgets.QColorDialog()
            new_color = color_dialog.getColor(current_color)
            if new_color.isValid():  # Returned in case cancel is pressed
                return new_color
            else:
                return current_color

        if signal_sender == 'dialogBackground':
            current_color = self.settings['dialog_background']
            new_color = open_color_dialog(current_color)
            self.settings['dialog_background'] = new_color
            return

        profile_index = self.bookToolBar.profileBox.currentIndex()
        current_profile = self.bookToolBar.profileBox.itemData(
            profile_index, QtCore.Qt.UserRole)

        # Retain current values on opening a new dialog
        if signal_sender == 'fgColor':
            current_color = current_profile['foreground']
            new_color = open_color_dialog(current_color)
            self.bookToolBar.colorBoxFG.setStyleSheet(
                'background-color: %s' % new_color.name())
            current_profile['foreground'] = new_color

        elif signal_sender == 'bgColor':
            current_color = current_profile['background']
            new_color = open_color_dialog(current_color)
            self.bookToolBar.colorBoxBG.setStyleSheet(
                'background-color: %s' % new_color.name())
            current_profile['background'] = new_color

        elif signal_sender == 'comicBGColor':
            current_color = self.comic_profile['background']
            new_color = open_color_dialog(current_color)
            self.bookToolBar.comicBGColor.setStyleSheet(
                'background-color: %s' % new_color.name())
            self.comic_profile['background'] = new_color

        self.bookToolBar.profileBox.setItemData(
            profile_index, current_profile, QtCore.Qt.UserRole)
        self.format_contentView()

    def modify_font(self, signal_sender):
        profile_index = self.bookToolBar.profileBox.currentIndex()
        current_profile = self.bookToolBar.profileBox.itemData(
            profile_index, QtCore.Qt.UserRole)

        if signal_sender == 'fontBox':
            current_profile['font'] = self.bookToolBar.fontBox.currentFont().family()

        if signal_sender == 'fontSizeBox':
            old_size = current_profile['font_size']
            new_size = self.bookToolBar.fontSizeBox.itemText(
                self.bookToolBar.fontSizeBox.currentIndex())
            if new_size.isdigit():
                current_profile['font_size'] = new_size
            else:
                current_profile['font_size'] = old_size

        if signal_sender == 'lineSpacingUp' and current_profile['line_spacing'] < 200:
            current_profile['line_spacing'] += 5
        if signal_sender == 'lineSpacingDown' and current_profile['line_spacing'] > 90:
            current_profile['line_spacing'] -= 5

        if signal_sender == 'paddingUp':
            current_profile['padding'] += 5
        if signal_sender == 'paddingDown':
            current_profile['padding'] -= 5

        alignment_dict = {
            'alignLeft': 'left',
            'alignRight': 'right',
            'alignCenter': 'center',
            'alignJustify': 'justify'}
        if signal_sender in alignment_dict:
            current_profile['text_alignment'] = alignment_dict[signal_sender]

        self.bookToolBar.profileBox.setItemData(
            profile_index, current_profile, QtCore.Qt.UserRole)
        self.format_contentView()

    def modify_comic_view(self, signal_sender, key_pressed):
        comic_profile = self.main_window.comic_profile
        current_tab = self.tabWidget.widget(self.tabWidget.currentIndex())

        self.bookToolBar.fitWidth.setChecked(False)
        self.bookToolBar.bestFit.setChecked(False)
        self.bookToolBar.originalSize.setChecked(False)

        if signal_sender == 'zoomOut' or key_pressed == QtCore.Qt.Key_Minus:
            comic_profile['zoom_mode'] = 'manualZoom'
            comic_profile['padding'] += 50

            # This prevents infinite zoom out
            if comic_profile['padding'] * 2 > current_tab.contentView.viewport().width():
                comic_profile['padding'] -= 50

        if signal_sender == 'zoomIn' or key_pressed in (
                QtCore.Qt.Key_Plus, QtCore.Qt.Key_Equal):
            comic_profile['zoom_mode'] = 'manualZoom'
            comic_profile['padding'] -= 50

            # This prevents infinite zoom in
            if comic_profile['padding'] < 0:
                comic_profile['padding'] = 0

        if signal_sender == 'fitWidth' or key_pressed == QtCore.Qt.Key_W:
            comic_profile['zoom_mode'] = 'fitWidth'
            comic_profile['padding'] = 0
            self.bookToolBar.fitWidth.setChecked(True)

        # Padding in the following cases is decided by
        # the image pixmap loaded by the widget
        if signal_sender == 'bestFit' or key_pressed == QtCore.Qt.Key_B:
            comic_profile['zoom_mode'] = 'bestFit'
            self.bookToolBar.bestFit.setChecked(True)

        if signal_sender == 'originalSize' or key_pressed == QtCore.Qt.Key_O:
            comic_profile['zoom_mode'] = 'originalSize'
            self.bookToolBar.originalSize.setChecked(True)

        self.format_contentView()

    def format_contentView(self):
        current_tab = self.tabWidget.currentWidget()

        try:
            current_metadata = current_tab.metadata
        except AttributeError:
            return

        if current_metadata['images_only']:
            background = self.comic_profile['background']
            zoom_mode = self.comic_profile['zoom_mode']

            if zoom_mode == 'fitWidth':
                self.bookToolBar.fitWidth.setChecked(True)
            if zoom_mode == 'bestFit':
                self.bookToolBar.bestFit.setChecked(True)
            if zoom_mode == 'originalSize':
                self.bookToolBar.originalSize.setChecked(True)

            self.bookToolBar.comicBGColor.setStyleSheet(
                'background-color: %s' % background.name())

            current_tab.format_view(
                None, None, None, background, None, None, None)

        else:
            profile_index = self.bookToolBar.profileBox.currentIndex()
            current_profile = self.bookToolBar.profileBox.itemData(
                profile_index, QtCore.Qt.UserRole)

            font = current_profile['font']
            foreground = current_profile['foreground']
            background = current_profile['background']
            padding = current_profile['padding']
            font_size = current_profile['font_size']
            line_spacing = current_profile['line_spacing']
            text_alignment = current_profile['text_alignment']

            # Change toolbar widgets to match new settings
            self.bookToolBar.fontBox.blockSignals(True)
            self.bookToolBar.fontSizeBox.blockSignals(True)
            self.bookToolBar.fontBox.setCurrentText(font)
            current_index = self.bookToolBar.fontSizeBox.findText(
                str(font_size), QtCore.Qt.MatchExactly)
            self.bookToolBar.fontSizeBox.setCurrentIndex(current_index)
            self.bookToolBar.fontBox.blockSignals(False)
            self.bookToolBar.fontSizeBox.blockSignals(False)

            self.alignment_dict[current_profile['text_alignment']].setChecked(True)

            self.bookToolBar.colorBoxFG.setStyleSheet(
                'background-color: %s' % foreground.name())
            self.bookToolBar.colorBoxBG.setStyleSheet(
                'background-color: %s' % background.name())

            current_tab.format_view(
                font, font_size, foreground,
                background, padding, line_spacing,
                text_alignment)

    def reset_profile(self):
        current_profile_index = self.bookToolBar.profileBox.currentIndex()
        current_profile_default = Settings(self).default_profiles[current_profile_index]
        self.bookToolBar.profileBox.setItemData(
            current_profile_index, current_profile_default, QtCore.Qt.UserRole)
        self.format_contentView()
