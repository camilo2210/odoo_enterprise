import ast
import json
import re

from lxml import html
from urllib.parse import urlencode

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain


class KnowledgeArticle(models.Model):
    _name = 'knowledge.article'
    _inherit = ['knowledge.article']

    audit_report_id = fields.One2many('audit.report', 'knowledge_article_id')
    inherited_audit_report_id = fields.One2many('audit.report',
        compute='_compute_inherited_audit_report', store=False)
    is_audit_report_template = fields.Boolean('Annual Report Template')

    @api.depends('audit_report_id')
    def _compute_inherited_audit_report(self):
        for article in self:
            current = article
            while current and not current.audit_report_id:
                current = current.parent_id
            article.inherited_audit_report_id = current.audit_report_id \
                if current and current.audit_report_id else False

    def update_embedded_audit_report_options(self, html_element_host_id, new_options):
        self.ensure_one()
        fragment = html.fragment_fromstring(self.body, create_parent=True)
        selector = f'.//*[@data-embedded="accountReport"][@data-oe-id="{html_element_host_id}"]'
        for element in fragment.findall(selector):
            element.set('data-embedded-props', json.dumps({
                **json.loads(element.get('data-embedded-props')),
                'options': new_options
            }))
        elements = []
        for child in fragment.getchildren():
            elements.append(
                html.tostring(child, encoding='unicode', method='html'))
        self.write({
            'body': ''.join(elements)
        })

    @api.model
    def _get_available_template_domain(self):
        base_domain = super()._get_available_template_domain()
        return Domain.AND([base_domain, [("is_audit_report_template", "=", False)]])

    def _get_inherited_audit_report(self):
        self.ensure_one()
        return self.inherited_audit_report_id

    def _prepare_template(self, ref):
        fragment = super()._prepare_template(ref)
        account_report_elements = fragment.xpath('//*[@data-embedded="accountReport"]')
        if not account_report_elements:
            return fragment

        if 'target_article_id' in self.env.context:
            target_article = self.env['knowledge.article'].browse(
                self.env.context['target_article_id'])
            audit_report = target_article._get_inherited_audit_report()

            def transform_xmlid_to_res_id(match):
                return str(ref(match.group('xml_id')))

            for element in account_report_elements:
                embedded_props = ast.literal_eval(re.sub(
                    r'(?<![\w])ref\(\'(?P<xml_id>\w+\.\w+)\'\)',
                    transform_xmlid_to_res_id,
                    element.get('data-embedded-props')))
                if 'options' in embedded_props:
                    account_report_options = embedded_props['options']
                    if 'report_id' in account_report_options:
                        account_report = self.env['account.report'].browse(account_report_options['report_id'])
                        account_report = account_report.with_company(audit_report.company_id)
                        embedded_props['options'] = account_report.get_options({
                            'forced_companies': audit_report.company_id.ids,
                            'date': {
                                'date_from': str(audit_report.start_date),
                                'date_to': str(audit_report.end_date),
                            },
                            **embedded_props['options']
                        })
                element.set('data-embedded-props', json.dumps(embedded_props))
        else:
            for element in account_report_elements:
                embedded_props = ast.literal_eval(re.sub(
                    r'(?<![\w])ref\(\'(?P<xml_id>\w+\.\w+)\'\)',
                    lambda match: '0',
                    element.get('data-embedded-props')))
                element.set('data-embedded-props', json.dumps({
                    'name': embedded_props.get('name'),
                    'options': {}
                }))

        return fragment

    def action_export_audit_report_to_pdf(self):
        self.ensure_one()
        audit_report = self._get_inherited_audit_report()

        if not audit_report:
            raise UserError(_('This article does not have an associated audit report, so the PDF cannot be generated.'))

        if audit_report.company_id.external_report_layout_id:
            params = {
                'include_pdf_files': self.env.context.get('include_pdf_files', 1),
                'include_child_articles': self.env.context.get('include_child_articles', 1)
            }
            return {
                'type': 'ir.actions.act_url',
                'url': f'/knowledge_accountant/article/{self.id}/audit_report?{urlencode(params)}',
                'target': 'download'
            }

        # If no report layout is defined, we open an action that allows the user
        # to create one. In the `report_action` context value, we then specify
        # the action to execute when the user clicks the "Continue" button.

        action = self.env['ir.actions.act_window']._for_xml_id('web.action_base_document_layout_configurator')
        context = ast.literal_eval(action['context'])
        context.update({
            'report_action': {
                'type': 'ir.actions.client',
                'tag': 'download_audit_report',
                'params': {
                    'articleId': self.id,
                    'includePdfFiles': self.env.context.get('include_pdf_files', 1),
                    'includeChildArticles': self.env.context.get('include_child_articles', 1),
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }
        })
        action['context'] = context
        return action

    @api.autovacuum
    def _gc_trashed_articles(self):
        articles = self.with_context(active_test=False).search(
            self._get_gc_trashed_articles_domain(), limit=100,
        )
        self.env['audit.report'].search([
            ('knowledge_article_id', 'in', articles.ids),
        ]).unlink()
        return articles.unlink()
