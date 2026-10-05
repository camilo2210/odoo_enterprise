import json

from lxml import html, etree
from markupsafe import Markup
from datetime import timedelta
from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import users

from odoo.addons.accountant_knowledge.controller.main import is_html_element_empty
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.addons.base.tests.common import TransactionCaseWithUserDemo


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestAccountantKnowledgeAuditReport(TransactionCaseWithUserDemo):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.invoice_user = mail_new_test_user(
            cls.env,
            login='invoice_user',
            groups='account.group_account_invoice',
            notification_type='inbox',
        )

        cls.company = cls.env['res.company'].create({
            'name': 'My Belgium Company',
            'country_id': cls.env.ref('base.be').id,
        })

        cls.env['account.report'].search([('root_report_id', '!=', False)]).unlink()
        cls.env['account.report'].search([]).unlink()

        cls.account_report = cls.env['account.report'].create({
            'name': 'Account Report',
            'country_id': cls.company.country_id.id,
        })
        cls.account_report_variant = cls.env['account.report'].create({
            'name': 'Account Report Variant',
            'root_report_id': cls.account_report.id,
            'country_id': cls.company.country_id.id,
        })

        cls.category = cls.env['knowledge.article.template.category'].create({
            'name': 'Accounting'
        })

        cls.audit_report_template = cls.env['knowledge.article'].create({
            'is_template': True,
            'is_audit_report_template': True,
            'template_name': 'Annual Report Root Template',
            'template_body': Markup('''
                <div>
                    <div data-embedded="articleIndex" data-embedded-props='{"showAllChildren": true}'/>
                    <div data-oe-id="e8949156e42774c3" data-embedded="accountReport" data-embedded-props="{
                        'name': 'My Account Report',
                        'options': {
                            'report_id': ref('accountant_knowledge.account_report'),
                            'comparison': {
                                'filter': 'same_last_year',
                            },
                        }
                    }"/>
                </div>
            '''),
            'template_category_id': cls.category.id,
        })

        cls.audit_report_child_template = cls.env['knowledge.article'].create({
            'is_template': True,
            'is_audit_report_template': True,
            'template_name': 'Annual Report Child Template',
            'template_body': Markup('''
                <div>
                    <a class="o_knowledge_article_link"
                        data-res_id="ref('accountant_knowledge.audit_report_template')">Link</a>
                </div>
            '''),
            'parent_id': cls.audit_report_template.id,
            'template_category_id': cls.category.id,
        })

        cls.env['ir.model.data'].create({
            'module': 'accountant_knowledge',
            'name': 'audit_report_template',
            'model': 'knowledge.article',
            'res_id': cls.audit_report_template.id
        })
        cls.env['ir.model.data'].create({
            'module': 'accountant_knowledge',
            'name': 'account_report',
            'model': 'account.report',
            'res_id': cls.account_report.id
        })

        cls.audit_report = cls.env['audit.report'].create({
            'company_id': cls.company.id,
            'knowledge_template_article_id': cls.audit_report_template.id,
            'title': 'My Annual Report',
            'start_date': '2025-01-01',
            'end_date': '2025-12-31',
            'responsible_user_ids': [
                Command.link(cls.user_demo.id),
            ],
        })

    def test_create_audit_report(self):
        """ Verify that when an audit report is created, the system correctly
            generates the articles from the template linked to the audit report,
            initializes the audit report options, populates the table of contents,
            resolves internal links, invites the responsible users to the
            root article."""

        # Parent article:
        parent_article = self.audit_report.knowledge_article_id

        self.assertEqual(len(parent_article.child_ids), 1)
        self.assertEqual(parent_article.internal_permission, 'none')
        self.assertEqual(len(parent_article.article_member_ids), 2)
        self.assertEqual(parent_article.article_member_ids[0].partner_id, self.env.user.partner_id)
        self.assertEqual(parent_article.article_member_ids[0].permission, 'write')
        self.assertEqual(parent_article.article_member_ids[1].partner_id, self.user_demo.partner_id)
        self.assertEqual(parent_article.article_member_ids[1].permission, 'write')
        self.assertEqual(parent_article.name, self.audit_report.title)

        parent_article_body = html.fragment_fromstring(parent_article.body, create_parent='div')

        # Check the table of contents:
        tables_of_contents = list(parent_article_body.xpath('.//*[@data-embedded="articleIndex"]'))
        self.assertEqual(len(tables_of_contents), 1)
        embedded_props = json.loads(tables_of_contents[0].get('data-embedded-props', '{}'))
        self.assertEqual(embedded_props, {
            'articles': [{
                'childIds': [],
                'id': parent_article.child_ids.id,
                'name': parent_article.child_ids.display_name
            }],
            'showAllChildren': True
        })

        # Check the embedded account report:
        embedded_account_reports = list(parent_article_body.xpath('.//*[@data-embedded="accountReport"]'))
        self.assertEqual(len(embedded_account_reports), 1)
        embedded_props = json.loads(embedded_account_reports[0].get('data-embedded-props', '{}'))
        self.assertEqual(embedded_props.get('name'), 'My Account Report')

        options = embedded_props.get('options')
        self.assertEqual(options.get('companies'), [{
            'name': self.company.display_name,
            'id': self.company.id,
            'currency_id': self.company.currency_id.id
        }])
        self.assertEqual(options.get('available_variants'), [{
            'id': self.account_report.id,
            'name': self.account_report.display_name,
            'country_id': self.account_report.country_id.id
        }, {
            'id': self.account_report_variant.id,
            'name': self.account_report_variant.display_name,
            'country_id': self.account_report_variant.country_id.id
        }])
        self.assertEqual(options.get('report_id'), self.account_report_variant.id)
        self.assertEqual(options.get('selected_variant_id'), self.account_report_variant.id)

        date = options.get('date', {})
        self.assertEqual(date.get('period_type'), 'year')
        self.assertEqual(date.get('date_from', False), '2025-01-01')
        self.assertEqual(date.get('date_to', False), '2025-12-31')
        comparison = options.get('comparison')
        self.assertEqual(comparison.get('filter', False), 'same_last_year')
        self.assertEqual(len(comparison.get('periods', [])), 1)
        self.assertDictEqual(comparison['periods'][0], {
            'string': '2024',
            'date_from': '2024-01-01',
            'date_to': '2024-12-31',
            'period_type': 'year',
            'fallback_from': 'custom',
        })

        # Child article:
        child_article = parent_article.child_ids
        self.assertEqual(len(child_article.child_ids), 0)
        self.assertFalse(child_article.internal_permission)
        self.assertEqual(len(child_article.article_member_ids), 0)
        self.assertEqual(child_article.name, self.audit_report_child_template.template_name)

        child_article_body = html.fragment_fromstring(child_article.body, create_parent='div')

        # Check the links:
        links = list(child_article_body.xpath('//*[contains(@class, "o_knowledge_article_link")]'))
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].get("data-res_id"), str(parent_article.id))

    def test_copy_audit_report(self):
        """ Verify that when an audit report is copied, the system correctly
            duplicates all articles linked to the original report, adjusts the
            embedded account report dates to the new start and end dates, updates
            the internal links, and refreshes the table of contents. """

        # Copy the report:
        new_audit_report = self.audit_report.copy_audit_report({
            'title': 'My Audit Report (copy)',
            'start_date': '2026-01-01',
            'end_date': '2026-12-31',
            'responsible_user_ids': []
        })

        # Parent article:
        parent_article = new_audit_report.knowledge_article_id
        self.assertEqual(len(parent_article.child_ids), 1)
        self.assertEqual(parent_article.internal_permission, 'none')
        self.assertEqual(len(parent_article.article_member_ids), 2)
        self.assertEqual(parent_article.article_member_ids[0].partner_id, self.env.user.partner_id)
        self.assertEqual(parent_article.article_member_ids[0].permission, 'write')
        self.assertEqual(parent_article.article_member_ids[1].partner_id, self.user_demo.partner_id)
        self.assertEqual(parent_article.article_member_ids[1].permission, 'write')
        self.assertEqual(parent_article.name, 'My Audit Report (copy)')

        parent_article_body = html.fragment_fromstring(parent_article.body, create_parent='div')

        # Check the table of contents:
        tables_of_contents = list(parent_article_body.xpath('.//*[@data-embedded="articleIndex"]'))
        self.assertEqual(len(tables_of_contents), 1)
        embedded_props = json.loads(tables_of_contents[0].get('data-embedded-props', '{}'))
        self.assertEqual(embedded_props, {
            'articles': [{
                'childIds': [],
                'id': parent_article.child_ids.id,
                'name': parent_article.child_ids.display_name
            }],
            'showAllChildren': True
        })

        # Check the embedded account report:
        embedded_account_reports = list(parent_article_body.xpath('.//*[@data-embedded="accountReport"]'))
        self.assertEqual(len(embedded_account_reports), 1)
        embedded_props = json.loads(embedded_account_reports[0].get('data-embedded-props', '{}'))
        self.assertEqual(embedded_props.get('name'), 'My Account Report')
        options = embedded_props.get('options')
        date = options.get('date', {})
        self.assertEqual(date.get('date_from', False), '2026-01-01')
        self.assertEqual(date.get('date_to', False), '2026-12-31')
        comparison = options.get('comparison')
        self.assertEqual(comparison.get('filter', False), 'same_last_year')
        self.assertEqual(len(comparison.get('periods', [])), 1)
        self.assertDictEqual(comparison['periods'][0], {
            'string': '2025',
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
            'period_type': 'year',
            'fallback_from': 'custom',
        })

        # Child article:
        child_article = parent_article.child_ids
        self.assertEqual(len(child_article.child_ids), 0)
        self.assertFalse(child_article.internal_permission)
        self.assertEqual(len(child_article.article_member_ids), 0)
        self.assertEqual(child_article.name, self.audit_report_child_template.template_name)

        child_article_body = html.fragment_fromstring(child_article.body, create_parent='div')

        # Check the links:
        links = list(child_article_body.xpath('//*[contains(@class, "o_knowledge_article_link")]'))
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].get("data-res_id"), str(parent_article.id))

    def test_is_html_element_empty(self):
        """ Check that the `is_html_element_empty` method correctly identifies
            empty HTML elements, ignoring all empty tags and whitespace
            characters."""
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div></div>
        ''')))
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div>   </div>
        ''')))
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div><div></div></div>
        ''')))
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div><div> </div></div>
        ''')))
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div><div> </div> </div>
        ''')))
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div> <div> </div> </div>
        ''')))
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div><p><br/></p></div>
        ''')))
        # NBSP character (\u00A0):
        self.assertTrue(is_html_element_empty(etree.fromstring('''
            <div><p>&#160;<br/></p></div>
        ''')))

        self.assertFalse(is_html_element_empty(etree.fromstring('''
            <div>Hello</div>
        ''')))
        self.assertFalse(is_html_element_empty(etree.fromstring('''
            <div><p>Hello<br/></p></div>
        ''')))

    @users('invoice_user')
    def test_invoice_user_can_apply_regular_knowledge_template(self):
        """Applying a regular Knowledge template should not require access to accountant-only models."""
        self.assertFalse(self.env['audit.report'].has_access('read'))
        article = self.env['knowledge.article'].create({'name': 'Test Article'})
        # The created article has an empty audit_report_id cached. Clear it to
        # reproduce the uncached access done when loading a template from the UI.
        article.invalidate_recordset(['audit_report_id'])

        body = article.apply_template(
            self.env.ref('knowledge.knowledge_article_template_meeting_minutes').id,
            skip_body_update=True,
        )
        self.assertTrue(body)

    def test_gc_trashed_articles_for_audit_report(self):
        """
        Check that trashed knowledge articles and their linked audit reports
        are deleted by the garbage collector.
        """
        parent_article = self.audit_report.knowledge_article_id
        child_article = parent_article.child_ids[0]
        other_child_article = self.env['knowledge.article'].create({
            'name': 'Other Child Article',
            'parent_id': parent_article.id,
        })
        parent_article.action_send_to_trash()
        other_child_article.action_unarchive()
        trash_limit_days = 30
        self.env['ir.config_parameter'].sudo().set_int(
            'knowledge.knowledge_article_trash_limit_days',
            trash_limit_days,
        )
        article_deletion_date = parent_article.write_date + timedelta(
            days=trash_limit_days,
            seconds=30,
        )

        with freeze_time(article_deletion_date):
            self.env['knowledge.article']._gc_trashed_articles()
        self.assertFalse(parent_article.exists(),
            "Trashed knowledge article linked to annual report should be deleted after _gc_trashed_articles.")
        self.assertFalse(child_article.exists(),
            "Trashed child article linked to parent article should be deleted after _gc_trashed_articles.")
        self.assertTrue(other_child_article.exists(),
            "Restored child article linked to parent article should not be deleted after _gc_trashed_articles.")
        self.assertFalse(parent_article.audit_report_id.exists(),
            "audit report should be deleted after _gc_trashed_articles.")
