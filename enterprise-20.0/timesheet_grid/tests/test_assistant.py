import itertools
import re
from datetime import datetime
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import ValidationError

from odoo.addons.hr_timesheet.tests.test_timesheet import TestCommonTimesheet
from odoo.addons.mail.tests.common import mail_new_test_user


class TestAssistant(TestCommonTimesheet):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env["hr.employee"].create({
            "name": cls.env.user.name,
            "user_id": cls.env.user.id,
        })

        cls.base_url = "https://example.odoo.com"
        cls.env["ir.config_parameter"].sudo().set_str("web.base.url", cls.base_url)

        cls.assistant_models = {
            "project.task": {
                "label": "Task",
                "target": {"type": "self"},
            },
            "account.analytic.line": {
                "label": "Timesheet",
                "target": {
                    "type": "field",
                    "field": "task_id",
                    "target_model": "project.task",
                },
            },
        }

    def test_google_suite_rules_match(self):
        cases = [
                    (
                        "timesheet_grid.aw_rule_gdoc",
                        ("Untitled document",),
                        'Untitled document - Google Docs|https://docs.google.com/document/d/abc123/edit?tab=t.0',
                    ),
                    (
                        "timesheet_grid.aw_rule_gslide",
                        ("Présentation sans titre",),
                        "Présentation sans titre - Google Slides|https://docs.google.com/presentation/d/xyz987/edit?slide=id.p#slide=id.p",
                    ),
                    (
                        "timesheet_grid.aw_rule_gsheet",
                        ("Feuille de calcul sans titre",),
                        'Feuille de calcul sans titre - Google Sheets|https://docs.google.com/spreadsheets/d/mln4567/edit?gid=0#gid=0',
                    ),
                ]

        for xmlid, expected_groups, webstring in cases:
            rule = self.env.ref(xmlid)
            with self.subTest(rule=rule.name):
                reg_match = re.search(rule.regex, webstring)
                self.assertTrue(reg_match, f"{rule.name} should match the webstring : {webstring}")
                self.assertEqual(reg_match.groups(), expected_groups, f"{rule.name} should extract the right groups")

    def test_zoom_rules_match(self):
        cases = [
            (
                "timesheet_grid.aw_rule_zoom",
                ("User's Zoom Meeting",),
                "User's Zoom Meeting|https://app.zoom.us/wc/91229218550/start?ref_from=launch&pwd=abc.1&fromPWA=1",
            ),
            (
                ## For Zoom use on Ubuntu OS
                "timesheet_grid.aw_rule_zoom_app",
                (),
                "Meeting|zoom",
            ),
            (
                ## For Zoom use on Windows OS
                "timesheet_grid.aw_rule_zoom_app",
                (),
                "Zoom Meeting|Zoom.exe",
            ),
            (
                ## For Zoom use on Mac OS
                "timesheet_grid.aw_rule_zoom_app",
                (),
                "Zoom Meeting|Zoom",
            ),
        ]
        for xmlid, expected_groups, webstring in cases:
            rule = self.env.ref(xmlid)
            with self.subTest(rule=rule.name):
                reg_match = re.search(rule.regex, webstring)
                self.assertTrue(reg_match, f"{rule.name} should match the webstring : {webstring}")
                self.assertEqual(reg_match.groups(), expected_groups, f"{rule.name} should extract the right groups")

    def test_aw_rule_check_regex(self):
        rule = self.env["aw.rule"].create({
            "name": "Test Rule",
            "template": "Test Rule",
            "type": "odoo",
            "regex": "regex",   # Valid Regex, no error
        })
        with self.assertRaises(ValidationError, msg="An invalid regex should trigger the constraint."):
            rule.regex = "(regex"

    def test_discord_rules_match_app(self):
        """The Discord aw.rule regexes must match both the desktop app's window
        title (e.g. "#channel | server - Discord") and a browser tab's title + url
        (e.g. "Discord | #channel | server" concatenated with "|" + the tab's url
        client-side, since ActivityWatch reports them as separate fields).
        Each format leaves the other one's capture groups unmatched (None): that's
        what the client-side `match[i] ?? ""` guards against when building the
        suggestion title (otherwise "undefined" would leak into it).
        """
        rule = self.env.ref("timesheet_grid.aw_rule_discord")
        web_rule = self.env.ref("timesheet_grid.aw_rule_discord_web")
        cases = [
            (
                '"assistant-thread" | Odoo - Discord|Discord',
                ('"assistant-thread" | Odoo',),
                'Discord | "assistant-thread" | Odoo|https://discord.com/channels/1234/5678',
            ),
            (
                "#timesheets-assistant | Odoo - Discord|discord",
                ("#timesheets-assistant | Odoo",),
                "Discord | #timesheets-assistant | Odoo|https://discord.com/channels/1111/2222",
            ),
            (
                "@JohnDoe - Discord|Discord.exe",
                ("@JohnDoe",),
                "Discord | @JohnDoe|https://discord.com/channels/3333/4444",
            ),
            (
                "Alice, Bob - Discord|discord",
                ("Alice, Bob",),
                "Discord | Alice, Bob|https://discord.com/channels/5555/6666",
            ),
        ]

        for app_title, expected_app_groups, web_string in cases:
            with self.subTest(rule=rule.name):
                app_match = re.search(rule.regex, app_title)
                self.assertTrue(app_match, f"{rule.name} should match the desktop app title: {app_title!r}")
                self.assertEqual(
                    app_match.groups(), expected_app_groups,
                    f"{rule.name} should extract the right groups from the desktop app title",
                )

                web_match = re.search(web_rule.regex, web_string)
                self.assertEqual(
                    web_match.groups(), expected_app_groups,
                    f"{rule.name} should extract the right groups from the web app title",
                )

    def test_get_aw_timesheet_data_working_hours(self):
        """
        Test that the `get_aw_timesheet_data` method returns the expected working hours for the current employee
        """
        calendar = self.env["resource.calendar"].create({
            "name": "Test Calendar",
            "company_id": False,
            "full_time_required_hours": 40.0,
            "attendance_ids": [
                Command.create({"dayofweek": "0", "hour_from": 8, "hour_to": 12, "day_period": "morning"}),
                Command.create({"dayofweek": "1", "hour_from": 8, "hour_to": 12, "day_period": "morning"}),
                Command.create({"dayofweek": "1", "hour_from": 13, "hour_to": 17, "day_period": "afternoon"}),
                Command.create({"dayofweek": "3", "hour_from": 13, "hour_to": 17, "day_period": "afternoon"}),
                Command.create({"dayofweek": "4", "hour_from": 8, "hour_to": 12, "day_period": "morning"}),
            ],
        })

        users = user_normal, user_flexible, user_fully_flexible = [
            mail_new_test_user(self.env, login=login, password=login * 2, groups="hr_timesheet.group_timesheet_manager", tz="UTC")
            for login in ["normal", "flexible", "fully_flexible"]
        ]
        flexible_calendar, fully_flexible_calendar = self.env["resource.calendar"].create([
            {
                "name": "Flexible Calendar",
                "calendar_type": "undefined",
                "attendance_ids": [],
                "hours_per_week": 42,
                "hours_per_day": 6,
            }, {
                "name": "Fully Flexible Calendar",
                "calendar_type": "undefined",
                "attendance_ids": [],
            },
        ])
        self.env["hr.employee"].create([
            {
                "name": "normal",
                "user_id": user_normal.id,
                "resource_calendar_id": calendar.id,
            }, {
                "name": "flexible",
                "user_id": user_flexible.id,
                "resource_calendar_id": flexible_calendar.id,
            }, {
                "name": "fully_flexible",
                "user_id": user_fully_flexible.id,
                "resource_calendar_id": fully_flexible_calendar.id,
            },
        ])

        for date, expected_values in [
            ("2025-12-16", [8.0, 6.0, None]),
            ("2025-12-17", [0.0, 6.0, None]),
            ("2025-12-18", [4.0, 6.0, None]),
        ]:
            for user, expected_value in zip(users, expected_values):
                data = self.env["account.analytic.line"].with_user(user).get_aw_timesheet_data(date)
                self.assertEqual(data["working_hours"], expected_value, f"User {user.name} should work {expected_value} hours on {date}")

    def test_get_url_regex_for_models(self):
        model_name = "res.partner"
        self.env["ir.actions.act_window"].create({
            "name": "Test Action",
            "res_model": model_name,
            "view_mode": "tree,form",
            "path": "test-path",
        })

        regexes = self.env["account.analytic.line"]._get_url_regex_for_models([model_name])
        self.assertIn(model_name, regexes)
        regex = regexes[model_name]

        valid_urls = [
            f"{self.base_url}/odoo/test-path/67",
            f"{self.base_url}/odoo/somebody/once/told/me/test-path/123",
            f"{self.base_url}/odoo/res.partner/67",
        ]

        for url in valid_urls:
            match = re.search(regex, url)
            self.assertTrue(match, f"Regex should match: {url}")
            self.assertTrue(match.group(1).isdigit())

        invalid_urls = [
            f"{self.base_url}/odoo/test-path",
            f"{self.base_url}/odoo/test-path/abc",
            f"{self.base_url}/sap/test-path/42",
        ]

        for url in invalid_urls:
            self.assertFalse(re.search(regex, url), f"Regex should not match: {url}")

    def test_get_assistant_odoo_models_data(self):
        with patch.object(
            self.env.registry["account.analytic.line"],
            "_get_assistant_odoo_models",
            return_value=self.assistant_models,
        ):
            data = self.env["account.analytic.line"]._get_assistant_odoo_models_data()

        models = {d["model"]: d for d in data}

        self.assertIn("project.task", models)
        self.assertIn("account.analytic.line", models)

        self.assertEqual(models["project.task"]["label"], "Task")

        self.assertRegex(f"{self.base_url}/odoo/project.task/1", models["project.task"]["url_regex"])

    def test_resolve_assistant_models_targets(self):
        task = self.project.task_ids[0]
        with patch.object(
            self.env.registry["account.analytic.line"],
            "_get_assistant_odoo_models",
            return_value=self.assistant_models,
        ):
            result = self.env["account.analytic.line"].resolve_assistant_models_targets({
                "project.task": [task.id],
                "account.analytic.line": [self.timesheet.id],
            })

        task_target = result["project.task"][task.id]

        self.assertEqual(task_target["task_id"], task.id)
        self.assertEqual(task_target["task_name"], task.name)
        self.assertEqual(task_target["project_id"], self.project.id)
        self.assertEqual(task_target["project_name"], self.project.name)

        ts_target = result["account.analytic.line"][self.timesheet.id]

        self.assertEqual(ts_target["task_id"], task.id)
        self.assertEqual(ts_target["task_name"], task.name)
        self.assertEqual(ts_target["project_id"], self.project.id)
        self.assertEqual(ts_target["project_name"], self.project.name)

    def test_normalize_events(self):
        events = [
            {"start": datetime(2026, 1, 13, 8), "stop": datetime(2026, 1, 13, 10), "type": "A"},
            {"start": datetime(2026, 1, 13, 9), "stop": datetime(2026, 1, 13, 11), "type": "B"},
            {"start": datetime(2026, 1, 13, 10), "stop": datetime(2026, 1, 13, 12), "type": "C"},
            {"start": datetime(2026, 1, 13, 11), "stop": datetime(2026, 1, 13, 11, 30), "type": "D"},
        ]

        normalized = self.env["account.analytic.line"]._normalize_events(events)
        expected = [
            {"start": datetime(2026, 1, 13, 8), "stop": datetime(2026, 1, 13, 10), "type": "A"},
            {"start": datetime(2026, 1, 13, 10), "stop": datetime(2026, 1, 13, 11), "type": "B"},
            {"start": datetime(2026, 1, 13, 11), "stop": datetime(2026, 1, 13, 12), "type": "C"},
        ]

        self.assertEqual(normalized, expected)

    def test_get_assistant_events_with_overlaps(self):
        def getter_a(start, end):
            return [
                {
                    "start": datetime(2026, 1, 13, 8),
                    "stop": datetime(2026, 1, 13, 10),
                    "type": "A",
                },
                {
                    "start": datetime(2026, 1, 13, 9),
                    "stop": datetime(2026, 1, 13, 11),
                    "type": "A",
                },
            ]

        def getter_b(start, end):
            return [
                {
                    "start": datetime(2026, 1, 13, 9, 30),
                    "stop": datetime(2026, 1, 13, 10, 30),
                    "type": "B",
                },
            ]

        getters = [
            {"sequence": 20, "getter": getter_a},
            {"sequence": 10, "getter": getter_b},
        ]

        with patch.object(
            self.env.registry["account.analytic.line"],
            "_get_assistant_events_getters",
            return_value=getters,
        ):
            events = self.env["account.analytic.line"].get_assistant_events("2026-01-13")

        for prev, cur in itertools.pairwise(events):
            self.assertLessEqual(
                prev["stop"], cur["start"],
                "Successive events should not overlap",
            )

        expected = [
            {"start": datetime(2026, 1, 13, 8), "stop": datetime(2026, 1, 13, 9, 30), "type": "A"},
            {"start": datetime(2026, 1, 13, 9, 30), "stop": datetime(2026, 1, 13, 10, 30), "type": "B"},
            {"start": datetime(2026, 1, 13, 10, 30), "stop": datetime(2026, 1, 13, 11), "type": "A"},
        ]
        self.assertEqual(events, expected)

    def test_get_aw_timesheet_data_when_user_has_no_employee(self):
        """Test that `get_aw_timesheet_data` returns False for working_hours
           when the current user has no linked employee."""
        user = self.timesheet_manager_no_project_user
        self.assertFalse(user.employee_id)

        data = self.env["account.analytic.line"].with_user(user).get_aw_timesheet_data("2026-03-10")
        self.assertFalse(data["working_hours"])

    def test_get_aw_timesheet_data_excludes_non_timesheet_lines(self):
        """`get_aw_timesheet_data` should only return actual timesheets (lines with a project_id),
           not other account.analytic.line records logged the same day."""
        date = "2026-03-10"
        timesheet = self.env["account.analytic.line"].create({
            "name": "Real timesheet",
            "date": date,
            "user_id": self.env.user.id,
            "project_id": self.project.id,
            "task_id": self.project.task_ids[0].id,
            "unit_amount": 1,
        })
        self.env["account.analytic.line"].create({
            "name": "Non-timesheet analytic line",
            "date": date,
            "user_id": self.env.user.id,
            "account_id": self.analytic_account.id,
            "unit_amount": 1,
        })

        data = self.env["account.analytic.line"].get_aw_timesheet_data(date)
        self.assertEqual([t["id"] for t in data["timesheets"]["records"]], [timesheet.id])

    def test_map_actions_from_menus(self):
        mock_menus = [
            # Grandchild
            {"id": 1, "parent_id": False, "action": False, "name": "Sales App"},
            {"id": 2, "parent_id": [1, "Sales App"], "action": False, "name": "Orders"},
            {"id": 3, "parent_id": [2, "Orders"], "action": "ir.actions.act_window,105", "name": "Quotations"},

            # Action directly on a root menu
            {"id": 4, "parent_id": False, "action": "ir.actions.act_window,200", "name": "Dashboard App"},

            # Different branch, child
            {"id": 5, "parent_id": False, "action": False, "name": "Project App"},
            {"id": 6, "parent_id": [5, "Project App"], "action": "ir.actions.act_window,305", "name": "Tasks"},

            # Server action, should be ignored
            {"id": 7, "parent_id": [1, "Sales App"], "action": "ir.actions.server,999", "name": "Server Action Menu"},
        ]

        with patch("odoo.models.BaseModel.search_read", return_value=mock_menus):
            action_dict = self.env["account.analytic.line"]._map_actions_from_menus()

        self.assertEqual(
            action_dict.get("105"),
            "Sales App",
            msg="Deeply nested actions should successfully trace up their parents to the root menu"
        )
        self.assertEqual(
            action_dict.get("200"),
            "Dashboard App",
            msg="Actions attached directly to a root menu should map to the root menu itself"
        )
        self.assertEqual(
            action_dict.get("305"),
            "Project App",
            msg="First-level child actions should successfully trace up to their respective root menu"
        )
        self.assertNotIn(
            "999",
            action_dict,
            msg="Non-'act_window' actions (like server actions) should be ignored entirely"
        )

    def test_map_modules_to_apps(self):
        Module = self.env["ir.module.module"].sudo()
        sale = Module.create({"name": "test_sale_app", "shortdesc": "Sales", "state": "installed", "application": True})
        project = Module.create({"name": "test_project_app", "shortdesc": "Project", "state": "installed", "application": True})
        sale_project = Module.create({"name": "test_sale_project_bridge", "shortdesc": "Sale Project Bridge", "state": "installed", "application": False})
        self.env["ir.module.module.dependency"].sudo().create([
            {"module_id": sale_project.id, "name": sale.name},
            {"module_id": sale_project.id, "name": project.name},
        ])

        self.env.transaction.invalidate_ormcache()
        module_to_app = self.env["account.analytic.line"]._map_modules_to_apps()
        self.env.transaction.invalidate_ormcache()

        self.assertEqual(
            module_to_app.get(sale.name),
            "Sales",
            msg="Root applications should map directly to their own shortdesc"
        )
        self.assertIn(
            module_to_app.get(sale_project.name),
            ["Sales", "Project"],
            msg="Bridge modules should successfully map to one of their root dependencies"
        )

    def test_map_models_to_apps(self):
        mock_module_to_app = {
            "sale": "Sales",
            "sale_project": "Sales",
        }

        def mock_search_read(domain=None, fields=None, **kwargs):
            # ir.model.data query asks for 'res_id'
            if fields and "res_id" in fields:
                return [
                    {"res_id": 50, "module": "sale"},
                    {"res_id": 51, "module": "sale_project"},
                ]
            # ir.model query asks for 'id' and 'model'
            return [
                {"id": 50, "model": "sale.order"},
                {"id": 51, "model": "project.task"},
            ]

        AnalyticLine = self.env.registry["account.analytic.line"]
        self.env.transaction.invalidate_ormcache()
        with patch.object(AnalyticLine, "_map_modules_to_apps", return_value=mock_module_to_app), \
             patch("odoo.models.BaseModel.search_read", side_effect=mock_search_read):
            model_dict = self.env["account.analytic.line"]._map_models_to_apps()
        self.env.transaction.invalidate_ormcache()

        self.assertEqual(
            model_dict.get("sale.order"),
            "Sales",
            msg="Models should map to their parent module's resolved app"
        )
        self.assertEqual(
            model_dict.get("project.task"),
            "Sales",
            msg="Models from bridge modules should map to the resolved parent app"
        )

    def test_map_fallback_actions(self):
        mock_module_to_app = {
            "sale": "Sales",
            "sale_project": "Sales",
        }
        valid_modules = list(mock_module_to_app.keys())
        existing_action_dict = {"105": "Project"}

        mock_data = [
            {"res_id": 105, "module": "sale"},
            {"res_id": 200, "module": "sale_project"},
        ]

        with patch("odoo.models.BaseModel.search_read", return_value=mock_data):
            action_dict = self.env["account.analytic.line"]._map_fallback_actions(
                existing_action_dict, mock_module_to_app, valid_modules
            )

        self.assertEqual(
            action_dict.get("105"),
            "Project",
            msg="Pre-existing actions from the UI menu mapping should not be overwritten by fallback logic"
        )
        self.assertEqual(
            action_dict.get("200"),
            "Sales",
            msg="Menuless fallback actions should be successfully mapped based on their module"
        )

    def test_get_aw_app_from_urls(self):
        """Test that the backend correctly parses URL paths to resolve apps and record names."""
        test_partner = self.env['res.partner'].create({'name': 'Test Partner'})
        mock_dictionary = {

            "actions": {
                "105": {
                    "app_name": "Sales",
                    "res_model": "sale.order"
                }
            },
            "models": {
                'project.task': "Project",
                'res.partner': "Contacts"
            },
            "paths": {'invoicing-path': {'app_name': "Invoicing", 'res_model': 'account.move'}, 'spreadsheet': {'app_name': "Spreadsheet", 'res_model': 'account.move'}}
        }

        urls_to_test = [
            "https://odoo.com/odoo/action-105",
            "https://odoo.com/odoo/project.task/999999999",
            f"https://odoo.com/odoo/res.partner/{test_partner.id}",
            "https://odoo.com/odoo/invoicing-path",
            "http://odoo.com/odoo/documents/spreadsheet/-82",
            "https://odoo.com/odoo/unknown-path",
            "invalid_url_string",
            f"https://odoo.com/odoo/res.partner/{test_partner.id}/edit",
            "https://odoo.com/odoo/action-105/999999999",
            f"https://odoo.com/odoo/res.partner/{test_partner.id}/action-105"
        ]

        with patch.object(self.env["account.analytic.line"].__class__, "_get_app_lookup_dictionary", return_value=mock_dictionary):
            resolved = self.env["account.analytic.line"].get_aw_app_from_urls(urls_to_test)

        self.assertEqual(resolved.get("https://odoo.com/odoo/action-105"), {'app_name': 'Sales', 'record_name': False})
        self.assertEqual(resolved.get("https://odoo.com/odoo/project.task/999999999"), {'app_name': 'Project', 'record_name': False})
        self.assertEqual(resolved.get(f"https://odoo.com/odoo/res.partner/{test_partner.id}"), {'app_name': 'Contacts', 'record_name': 'Test Partner'})
        self.assertEqual(resolved.get("https://odoo.com/odoo/invoicing-path"), {'app_name': 'Invoicing', 'record_name': False})

        self.assertEqual(resolved.get(f"https://odoo.com/odoo/res.partner/{test_partner.id}/edit"), {'app_name': 'Contacts', 'record_name': 'Test Partner'})
        self.assertEqual(resolved.get("https://odoo.com/odoo/action-105/999999999"), {'app_name': 'Sales', 'record_name': False})
        self.assertEqual(resolved.get(f"https://odoo.com/odoo/res.partner/{test_partner.id}/action-105"), {'app_name': 'Sales', 'record_name': False})
        self.assertEqual(resolved.get("http://odoo.com/odoo/documents/spreadsheet/-82"), {'app_name': 'Spreadsheet', 'record_name': False})

        self.assertNotIn("https://odoo.com/odoo/unknown-path", resolved)
        self.assertNotIn("invalid_url_string", resolved)

    def test_resolve_gmail_partners_ignores_current_user(self):
        self_partner = self.user_employee.partner_id

        resolved = self.env['account.analytic.line'].with_user(self.user_employee).resolve_gmail_partners(
            [self_partner.email, self.partner.email]
        )

        self.assertNotIn(
            self_partner.email, resolved,
            "The current user's own address should not resolve to any project or task",
        )
        self.assertEqual(
            resolved[self.partner.email]['project_id'], self.partner.project_ids.filtered('allow_timesheets')[-1].id,
            "If no timesheets for the partner projects, the Partner Email should resolve to the timesheeted project with highest id",
        )

    def test_resolve_multi_partners_with_same_email(self):
        self.user_employee.login = self.partner.email
        self.partner.write({
            "user_ids": [Command.link(self.user_employee.id)],
        })

        self.user_employee2.login = "customer+portal@task.com"
        self.env["res.partner"].create([
            {"name": "Partner portal user", "email": "customer@task.com", "user_ids": [Command.link(self.user_employee2.id)]},
            {"name": "Partner 9 no user", "email": "customer@task.com"},
        ])

        resolved = self.env["account.analytic.line"].resolve_gmail_partners(["customer@task.com"])
        self.assertEqual(resolved["customer@task.com"]["partner_name"], self.partner.name, "The email should be resolved to the partner having a user with the same email")

        self.user_employee.login = "notTheSame@email.com"
        resolved = self.env["account.analytic.line"].resolve_gmail_partners(["customer@task.com"])
        self.assertIn("customer@task.com", resolved, "The email should be resolved to any partner as no one has a user with same email")

    def test_odoo_main_rule_matches(self):
        """ The Odoo Database aw.rule regex must match standard, dev, staging,
        and sandbox Odoo.sh URLs, capturing the core database name. It must
        strictly ignore internal system subdomains (runbot, pad, etc.).
        """

        rule = self.env.ref("timesheet_grid.aw_rule_odoo_main")

        positive_cases = [
            ("https://mycompany.odoo.com", "mycompany"),
            ("https://www.mycompany.odoo.com", "mycompany"),
            ("https://myproject-staging-123.dev.odoo.com", "myproject-staging-123"),
            ("https://mycompany.staging.odoo.com", "mycompany"),
            ("https://xxx.sandbox.odoo.com/web/login", "xxx"),
            ("https://database-name.custom-env.odoo.com/shop?test=1", "database-name"),
        ]

        for url, expected_db in positive_cases:
            with self.subTest(url=url):
                match = re.search(rule.regex, url)
                self.assertTrue(match, f"Rule should match the Odoo URL: {url!r}")
                self.assertEqual(
                    match.groups(), (expected_db,),
                    f"Rule should extract {expected_db!r} from {url!r}",
                )

        negative_cases = [
            "https://runbot.odoo.com",
            "https://www.runbot.odoo.com",
            "https://pad.odoo.com",
            "https://mergebot.odoo.com/web",
            "http://mycompany.odoo.com",
        ]

        for url in negative_cases:
            with self.subTest(url=url):
                match = re.search(rule.regex, url)
                self.assertIsNone(match, f"Rule should NOT match the system/invalid URL: {url!r}")

    def test_resolve_gmail_partners(self):
        # Five disjoint partner trees (parent_id/child_ids hierarchy):
        #     1 -> 2 -> 4        5 -> 6 -> 8
        #     |--> 3             |--> 7
        #
        # 9  -> 9c  : nothing anywhere in the tree (no project, no task, no timesheet)
        # 10 -> 10c : no timesheet, but a project is linked to the tree
        # 11 -> 11c : no timesheet, but tasks are linked to the tree (most recent one should be taken)
        (
            p1, p2, p3, p4, p5, p6, p7, p8,
            p9, p9c, p10, p10c, p11, p11c,
        ) = self.env["res.partner"].create([
            {"name": "Partner 1", "email": "partner1@test.com"},
            {"name": "Partner 2", "email": "partner2@test.com"},
            {"name": "Partner 3", "email": "partner3@test.com"},
            {"name": "Partner 4", "email": "partner4@test.com"},
            {"name": "Partner 5", "email": "partner5@test.com"},
            {"name": "Partner 6", "email": "partner6@test.com"},
            {"name": "Partner 7", "email": "partner7@test.com"},
            {"name": "Partner 8", "email": "partner8@test.com"},
            {"name": "Partner 9", "email": "partner9@test.com"},
            {"name": "Partner 9 child", "email": "partner9c@test.com"},
            {"name": "Partner 10", "email": "partner10@test.com"},
            {"name": "Partner 10 child", "email": "partner10c@test.com"},
            {"name": "Partner 11", "email": "partner11@test.com"},
            {"name": "Partner 11 child", "email": "partner11c@test.com"},
        ])
        p2.parent_id = p1.id
        p3.parent_id = p1.id
        p4.parent_id = p2.id

        p6.parent_id = p5.id
        p7.parent_id = p5.id
        p8.parent_id = p6.id

        p9c.parent_id = p9.id
        p10c.parent_id = p10.id
        p11c.parent_id = p11.id

        (
            project_1, project_2, project_3, _, project_8,
            _, project_10_timesheeted, _,
            project_11a, project_11b, project_11c_not_timesheeted,
        ) = self.env["project.project"].create([
            {"name": "Project 1", "partner_id": p1.id, "allow_timesheets": True},
            {"name": "Project 2", "partner_id": p2.id, "allow_timesheets": True},
            {"name": "Project 3", "partner_id": p3.id, "allow_timesheets": True},
            {"name": "Project 5", "partner_id": p5.id},
            {"name": "Project 8", "partner_id": p8.id},
            {"name": "Project 10 timesheeted low ID", "partner_id": p10.id, "allow_timesheets": True},
            {"name": "Project 10 timesheeted high ID", "partner_id": p10.id, "allow_timesheets": True},
            {"name": "Project 10 not timesheeted", "partner_id": p10.id, "allow_timesheets": False},
            {"name": "Project 11 a", "allow_timesheets": True},
            {"name": "Project 11 b", "allow_timesheets": True},
            {"name": "Project 11 c not timesheeted", "allow_timesheets": False},
        ])
        task_3 = self.env["project.task"].create({
            "name": "Task 3",
            "project_id": project_3.id,
        })

        # Task 11 a is superseded by Task 11 b (created later, so a higher id = "more recent").
        # Task 11 c has the highest id of all, but must be ignored since its project doesn't allow timesheets.
        self.env["project.task"].create({
            "name": "Task 11 a",
            "project_id": project_11a.id,
            "partner_id": p11.id,
        })
        task_11b = self.env["project.task"].create({
            "name": "Task 11 b",
            "project_id": project_11b.id,
            "partner_id": p11c.id,
        })
        self.env["project.task"].create({
            "name": "Task 11 c not timesheeted",
            "project_id": project_11c_not_timesheeted.id,
            "partner_id": p11.id,
        })

        self.env["account.analytic.line"].create([
            {
                "name": "Timesheet on partner 1",
                "date": "2026-01-01",
                "project_id": project_1.id,
                "user_id": self.env.user.id,
                "unit_amount": 1.0,
            },
            {
                "name": "Timesheet on partner 3",
                "date": "2026-01-10",
                "project_id": project_3.id,
                "task_id": task_3.id,
                "user_id": self.env.user.id,
                "unit_amount": 1.0,
            },
            {
                "name": "Timesheet on partner 2",
                "date": "2026-01-20",
                "project_id": project_2.id,
                "user_id": self.env.user.id,
                "unit_amount": 1.0,
            },
        ])

        resolved = self.env["account.analytic.line"].resolve_gmail_partners([p1.email, p2.email, p3.email, p4.email])

        for partner in [p1, p2, p3, p4]:
            self.assertEqual(
                resolved[partner.email]["project_id"], project_2.id,
                "Partner 2 has the most recent timesheet in the first Tree"
            )

        project_2.allow_timesheets = False
        resolved = self.env["account.analytic.line"].resolve_gmail_partners([
            p4.email, p8.email, p3.email, p1.email, p10.email, p6.email, p7.email, p2.email, p5.email,
            p9.email, p9c.email, p10c.email, p11.email, p11c.email,
        ])

        for partner in [p1, p2, p3, p4]:
            self.assertEqual(
                resolved[partner.email]["task_id"], task_3.id,
                "Partner 3 has the most recent timesheet in the first Tree"
            )
        for partner in [p5, p6, p7, p8]:
            self.assertEqual(
                resolved[partner.email]["project_id"], project_8.id,
                "all partners in the second Tree don't have timesheets, so the project with highest id is taken"
            )

        for partner in [p9, p9c]:
            self.assertFalse(
                resolved[partner.email]["project_id"] or resolved[partner.email]["task_id"],
                "Partner 9's tree has no timesheet, no task and no project anywhere"
            )

        for partner in [p10, p10c]:
            self.assertEqual(
                resolved[partner.email]["project_id"], project_10_timesheeted.id,
                "Partner 10's tree has no timesheet, so the timesheeted project with highest ID linked to the tree is taken"
            )

        for partner in [p11, p11c]:
            self.assertEqual(
                resolved[partner.email]["task_id"], task_11b.id,
                "Partner 11's tree has no timesheet, so the most recently created timesheeted task linked to the tree is taken"
            )
