from odoo import fields
from odoo.tests import tagged, HttpCase

from odoo.addons.project.tests.test_access_rights import TestProjectPortalCommon


@tagged('at_install', '-post_install')
class TestPortalProject(TestProjectPortalCommon, HttpCase):

    def test_portal_project_tasks_sorted_by_planned_date(self):
        """Verify that project tasks are sorted by planned start date."""
        self.authenticate(self.user_projectmanager.login, self.user_projectmanager.login)

        self.task_3.planned_date_begin = fields.Datetime.to_datetime("2026-06-19 09:00:00")
        self.task_5.planned_date_begin = fields.Datetime.to_datetime("2026-06-18 09:00:00")

        response = self.url_open(f'/my/projects/{self.project_pigs.id}?sortby=planned_date_begin+asc')
        content = response.text

        self.assertEqual(response.status_code, 200)
        self.assertLess(content.index(self.task_5.name), content.index(self.task_3.name))
