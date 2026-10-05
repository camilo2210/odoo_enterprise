import ast
import json

from urllib.parse import urlencode

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class KnowledgeArticle(models.Model):
    _name = 'knowledge.article'
    _inherit = ['knowledge.article']

    esg_report_id = fields.One2many('esg.report', 'knowledge_article_id', groups='esg.esg_group_manager')
    inherited_esg_report_id = fields.One2many('esg.report', compute='_compute_inherited_esg_report_id', groups='esg.esg_group_manager')
    is_esg_report_template = fields.Boolean()

    @api.depends('esg_report_id')
    def _compute_inherited_esg_report_id(self):
        for article in self:
            current = article
            while current and not current.esg_report_id:
                current = current.parent_id
            article.inherited_esg_report_id = current.esg_report_id \
                if current and current.esg_report_id else False

    def action_export_esg_report_to_pdf(self):
        self.ensure_one()
        esg_report = self._get_inherited_audit_report()

        if not esg_report:
            raise ValidationError(_('This article does not have an associated esg report, so the PDF cannot be generated.'))

        if esg_report.company_id.external_report_layout_id:
            params = {
                'include_pdf_files': self.env.context.get('include_pdf_files', 1),
                'include_child_articles': self.env.context.get('include_child_articles', 1)
            }
            return {
                'type': 'ir.actions.act_url',
                'url': f'/esg/article/{self.id}/esg_report?{urlencode(params)}',
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
                'tag': 'download_esg_report',
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

    def _get_inherited_audit_report(self):
        inherited_audit_report = super()._get_inherited_audit_report()
        if not self.env.user.has_group('esg.esg_group_manager'):
            return inherited_audit_report
        return inherited_audit_report or self.inherited_esg_report_id

    def _prepare_template(self, ref):
        fragment = super()._prepare_template(ref)
        if not self.env.user.has_group('esg.esg_group_manager'):
            return fragment
        if 'target_article_id' in self.env.context:
            target_article = self.env['knowledge.article'].browse(
                self.env.context['target_article_id'])
            esg_report = target_article.inherited_esg_report_id
            if esg_report.report_type != 'csrd':
                return fragment

            for element in fragment.xpath('//*[@data-embedded-props]'):
                embedded_props = json.loads(element.get('data-embedded-props'))
                if esrs_code := embedded_props.get('esrs_code'):
                    is_esrs_material = bool(self.env['esg.metric'].search([
                        ('esrs_code', '=', esrs_code),
                        ('date_start', '<=', esg_report.end_date),
                        ('date_end', '>=', esg_report.start_date),
                        ('materiality_type', '!=', 'non_material'),
                    ], limit=1))
                    if (embedded_props.get('is_esrs_material') and is_esrs_material) or (not embedded_props.get('is_esrs_material') and not is_esrs_material):
                        embedded_props = json.loads(element.get('data-embedded-props'))
                        embedded_props['showContent'] = True
                        element.set('data-embedded-props', json.dumps(embedded_props))
                        element.set('class', element.get('class', '').replace('d-print-none', ''))

        return fragment

    @api.model
    def _get_available_template_domain(self):
        base_domain = super()._get_available_template_domain()
        return Domain.AND([base_domain, [('is_esg_report_template', '=', False)]])

    def _should_load_all_annexes(self):
        # If the report is of type VSME + Comprehensive Module, we will load the Comprehensive articles as well
        return super()._should_load_all_annexes() and self.sudo().inherited_esg_report_id.report_type != 'vsme_advanced'
