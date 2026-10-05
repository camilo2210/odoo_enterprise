# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo.tests import tagged

from .common import TestCommonSalePlanning
from odoo.addons.planning.tests.common import TestUiCommon

@tagged('post_install', '-at_install')
class TestSalePlanningUi(TestCommonSalePlanning, TestUiCommon):

    def test_01_ui_inherit(self):
        if self.env["ir.module.module"].search([("name", "=", "planning_field_service"), ("state", "=", "installed")]):
            self.skipTest("planning_field_service remove the multi_add in gantt view, so the tour is invalid.")
        self.plannable_so.action_confirm()
        self.start_tour("/odoo", 'sale_planning_test_tour', login='admin')
