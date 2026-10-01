import json

from datetime import datetime
from lxml import html

from odoo import _, api, Command, fields, models


class AuditReport(models.Model):
    _name = 'audit.report'
    _description = 'Annual Report'

    knowledge_article_id = fields.Many2one(
        'knowledge.article', string='Article', required=True, index=True)

    color = fields.Integer(string='Color Index', export_string_translation=False)
    title = fields.Char(string='Title', required=True, translate=True)
    status = fields.Selection(string='Status',
        selection=[('draft', 'Draft'), ('done', 'Done')], default='draft')
    start_date = fields.Date(string='Start Date', required=True,
        help='Start Date, included in the fiscal year.',
        default=lambda self: datetime(year=datetime.now().year - 1, month=1, day=1))
    end_date = fields.Date(string='End Date', required=True,
        help='Ending Date, included in the fiscal year.',
        default=lambda self: datetime(year=datetime.now().year - 1, month=12, day=31))
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    responsible_user_ids = fields.Many2many('res.users', string='Responsibles',
        default=lambda self: self.env.user)
    knowledge_template_article_id = fields.Many2one(
        'knowledge.article', string='Annual Report Template', required=True,
        domain="[('is_audit_report_template', '=', True)]",
        default=lambda self: self.env['knowledge.article'].search([('is_audit_report_template', '=', True)], limit=1))

    @api.model_create_multi
    def create(self, vals_list):
        root_articles = self.env['knowledge.article'].create([{
            'internal_permission': 'none',
            'article_member_ids': [(0, 0, {
                'partner_id': self.env.user.partner_id.id,
                'permission': 'write'
            })]
        } for _ in vals_list])
        for vals, root_article in zip(vals_list, root_articles):
            vals['knowledge_article_id'] = root_article.id

        audit_reports = super().create(vals_list)
        for audit_report, root_article in zip(audit_reports, root_articles):
            root_template = audit_report.knowledge_template_article_id
            root_article.apply_template(root_template.id)
            root_article.write({
                'name': audit_report.title
            })

            # Invite the responsible users:
            for user in audit_report.responsible_user_ids:
                root_article.invite_members(user.mapped('partner_id'), 'write')
        return audit_reports

    def write(self, vals):
        if vals.get('responsible_user_ids'):
            user_ids = [command[1] for command in vals['responsible_user_ids'] if command[0] == Command.LINK]
            users = self.env['res.users'].browse(user_ids)
            for article in self.knowledge_article_id:
                article.invite_members(users.mapped('partner_id'), 'write')
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_cascade_articles(self):
        if knowledge_articles := self.knowledge_article_id._filtered_access('write'):
            knowledge_articles.action_send_to_trash()

    def action_set_to_draft(self):
        self.status = 'draft'

    def action_set_to_done(self):
        self.status = 'done'

    def action_edit_audit_report(self):
        action = self.env['ir.actions.act_window']._for_xml_id(
            'accountant_knowledge.action_audit_report_quick_create')
        action['name'] = _('Edit Annual Report')
        action['res_id'] = self.id
        return action

    def action_audit_report_pdf(self):
        self.ensure_one()
        return self.knowledge_article_id.action_export_audit_report_to_pdf()

    def action_duplicate_audit_report(self):
        action = self.env['ir.actions.act_window']._for_xml_id(
            'accountant_knowledge.action_audit_report_quick_create')
        action['name'] = _('Duplicate Annual Report')
        action['context'] = {
            'default_title': _('%(title)s (copy)', title=self.title),
            'default_responsible_user_ids': self.responsible_user_ids.ids,
            'original_audit_report': self.id,
            'show_duplicate_button': True,
            'show_create_button': False
        }
        return action

    def copy_audit_report(self, default=None):
        """ Copy the audit report.
            Unlike the standard `copy` method, this method applies the following
            transformations to the body of the copied articles:
            1. It will update the internal links.
            2. It will update the article indexes.
            3. It will update the embedded account reports. """
        self.ensure_one()

        if not default:
            default = {}

        title = default.get('title', self.title)
        start_date = fields.Datetime.from_string(default['start_date']) \
            if 'start_date' in default else self.start_date
        end_date = fields.Datetime.from_string(default['end_date']) \
            if 'end_date' in default else self.end_date
        company_id = default.get('company_id', self.company_id.id)
        responsible_user_ids = default.get('responsible_user_ids', self.responsible_user_ids.ids)

        root_article = self.knowledge_article_id
        root_article_copy = self.knowledge_article_id.copy()

        def traverse(root_article):
            articles = []
            stack = [root_article]
            while stack:
                article = stack.pop()
                articles.append(article)
                stack.extend(article.child_ids.sorted(lambda child: child.sequence, reverse=True))
            return articles

        pairs = list(zip(traverse(root_article), traverse(root_article_copy)))
        id_mapping = {
            article.id: article_copy.id for article, article_copy in pairs
        }

        for article, article_copy in pairs:
            fragment = html.fragment_fromstring(article_copy.body, create_parent=True)

            # Remove the history steps:
            for element in fragment.findall('.//*[@data-last-history-commits]'):
                del element.attrib['data-last-history-commits']

            # Update the article indexes:
            for element in fragment.xpath('//*[@data-embedded="articleIndex"]'):
                embedded_props = json.loads(element.get('data-embedded-props', '{}'))
                if embedded_props.get('showAllChildren'):
                    def build_article_index(parent_article):
                        return [{
                            'id': child_article.id,
                            'name': child_article.display_name,
                            'childIds': build_article_index(child_article)
                        } for child_article in parent_article.child_ids
                            if not child_article.is_article_item]
                    articles = build_article_index(article_copy)
                else:
                    articles = [{
                        'id': child_article.id,
                        'name': child_article.display_name,
                        'childIds': []
                    } for child_article in article_copy.child_ids
                        if not child_article.is_article_item]
                element.set('data-embedded-props', json.dumps({
                    'articles': articles,
                    'showAllChildren': embedded_props.get('showAllChildren', False)
                }))

            # Update the internal links:
            for element in fragment.xpath('//*[contains(@class, "o_knowledge_article_link")]'):
                try:
                    article_id = int(element.get('data-res_id'))
                    article_id_copy = id_mapping.get(article_id, article_id)
                    element.set('href', '/knowledge/article/%s' % (article_id_copy))
                    element.set('data-res_id', str(article_id_copy))
                except ValueError:
                    pass

            # Update the embedded account reports:
            for element in fragment.findall('.//*[@data-embedded="accountReport"]'):
                embedded_props = json.loads(element.get('data-embedded-props'))
                account_report_options = embedded_props['options']
                account_report = self.env['account.report'].browse(
                    account_report_options['report_id'])
                new_account_report_options = account_report.get_options(previous_options={
                    **account_report_options,
                    'forced_companies': company_id,
                    'date': {
                        'date_from': start_date,
                        'date_to': end_date,
                    }})
                element.set('data-embedded-props', json.dumps({
                    **embedded_props,
                    'options': new_account_report_options
                }))

            elements = []
            for child in fragment.getchildren():
                elements.append(
                    html.tostring(child, encoding='unicode', method='html'))

            article_copy.write({
                'body': ''.join(elements)
            })

        audit_report = super().create({
            'knowledge_article_id': root_article_copy.id,
            'title': title,
            'start_date': start_date,
            'end_date': end_date,
            'company_id': company_id,
            'responsible_user_ids': [[4, responsible_user_id] for responsible_user_id in responsible_user_ids]
        })

        root_article_copy.invite_members(audit_report.responsible_user_ids.partner_id, 'write')
        root_article_copy.write({
            'name': audit_report.title
        })

        return audit_report


AuditReport.copy_audit_report.__override__ = False  # whitelist super()
