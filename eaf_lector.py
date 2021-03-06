#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app.lector.lector.mainui import MainUI

class LectorWidget(MainUI):
    def __init__(self, url):
        super(LectorWidget, self).__init__()
        self.process_post_hoc_files([url], True)
        self.show()
        self.resizeEvent()
