#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import QWidget
from core.buffer import Buffer

from app.lector.eaf_lector import LectorWidget

class AppBuffer(Buffer):
    def __init__(self, buffer_id, url, arguments):
        Buffer.__init__(self, buffer_id, url, arguments, True)

        self.add_widget(LectorWidget(url))
        self.build_all_methods(self.buffer_widget)
