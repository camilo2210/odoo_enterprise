import json

from collections import defaultdict
from datetime import date
from lxml import html

from odoo import api, fields, models, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools import SQL, format_date


class EsgReport(models.Model):
    _name = 'esg.report'
    _description = 'ESG Report'

    def _get_report_type_selection(self):
        selection = [
            ('vsme_basic', 'VSME - Basic Module'),
            ('vsme_advanced', 'VSME - Basic Module + Comprehensive Module'),
        ]
        if self.env.user.has_group('esg.group_esg_csrd_reporting'):
            selection.append(('csrd', 'CSRD'))
        return selection

    def _default_base_year(self):
        last_year_report = self.search([], order='create_date desc', limit=1)
        return last_year_report.base_year if last_year_report else fields.Date.context_today(self).year - 1

    report_type = fields.Selection(
        selection=lambda self: self._get_report_type_selection(),
        required=True,
    )
    color = fields.Integer(export_string_translation=False)
    knowledge_article_id = fields.Many2one(
        'knowledge.article',
        required=True,
        index=True,
    )
    title = fields.Char(required=True)
    start_date = fields.Date(
        string='Reporting Date',
        compute='_compute_dates',
        store=True,
        readonly=False,
        required=True,
    )
    end_date = fields.Date(
        string='Reporting End Date',
        compute='_compute_dates',
        store=True,
        readonly=False,
        required=True,
    )
    responsible_user_ids = fields.Many2many('res.users', string='Responsibles', default=lambda self: self.env.user)
    status = fields.Selection(
        string='Status',
        selection=[('draft', 'Draft'), ('done', 'Done')],
        default='draft',
    )
    company_id = fields.Many2one(
        'res.company',
        'Group Reporting Company',
        default=lambda self: self.env['res.company'].sudo().ESG_REPORT_DEFAULT_COMPANY or self.env.company,
        help='This company defines the fiscal year and main company information used for the report. If your group has several companies, choose the one representing the consolidated perimeter.',
        required=True,
    )
    nace_id = fields.Many2one(
        'esg.nace',
        string='NACE Code',
        help='Select the NACE code representing the company\'s main economic activity',
        default=lambda self: self.search([], order='create_date desc', limit=1).nace_id,
    )
    base_year = fields.Integer(
        help='''Select the histrocial reference year for tracking progress on metrics like GHG emissions, energy or water.
            It serves as a benchmark for future comparisons and may be adjusted if major structural changes occur.
        ''',
        default=_default_base_year
    )

    @api.constrains('base_year')
    def _check_base_year(self):
        for report in self:
            if report.base_year and not report._has_valid_base_year():
                raise ValidationError(self.env._('The base year is not valid. It must be between 1000 and 9999.'))

    @api.depends('company_id')
    def _compute_dates(self):
        today = fields.Date.context_today(self)
        for report in self:
            dates = report.company_id.sudo().compute_fiscalyear_dates(today)
            report.start_date = dates['date_from']
            report.end_date = dates['date_to']

    @api.model_create_multi
    def create(self, vals_list):
        root_articles = self.env['knowledge.article'].create([{
            'internal_permission': 'none',
            'article_member_ids': [Command.create({
                'partner_id': self.env.user.partner_id.id,
                'permission': 'write',
            })]
        } for _ in vals_list])
        for vals, root_article in zip(vals_list, root_articles):
            vals['knowledge_article_id'] = root_article.id

        esg_reports = super().create(vals_list)
        esg_report_per_type = {}
        for esg_report, root_article in zip(esg_reports, root_articles):
            if esg_report.report_type == 'csrd':
                if not (root_template := esg_report_per_type.get('csrd')):
                    root_template = self.env.ref('esg.esg_csrd_knowledge_article_template_csrd_report')
                    esg_report_per_type['csrd'] = root_template
            else:
                if not (root_template := esg_report_per_type.get('vsme')):
                    root_template = self.env.ref('esg.esg_csrd_knowledge_article_template_vsme_report')
                    esg_report_per_type['vsme'] = root_template
            root_article.apply_template(root_template.id)
            root_article.write({
                'name': esg_report.title
            })

            # Invite the responsible users:
            root_article.invite_members(esg_report.responsible_user_ids.partner_id, 'write')
        return esg_reports

    def write(self, vals):
        if vals.get('responsible_user_ids'):
            user_ids = [command[1] for command in vals['responsible_user_ids'] if command[0] == Command.LINK]
            users = self.env['res.users'].browse(user_ids)
            for article in self.knowledge_article_id:
                article.invite_members(users.partner_id, 'write')
        return super().write(vals)

    def _get_knowledge_report_data(self):
        def get_payment_terms_data(start_date, end_date):
            avg_days_payment = 0
            pct_payment_on_terms = 0
            reconciled_payments = self.env['account.move'].sudo().search([
                ('state', '=', 'posted'),
                ('move_type', 'in', self.env['account.move'].get_purchase_types(include_receipts=True)),
                ('invoice_date', '>=', start_date),
                ('invoice_date', '<=', end_date),
            ]).reconciled_payment_ids
            if reconciled_payments:
                # We take the last payment for each invoice to compute the average days to payment
                self.env.cr.execute(SQL(
                    """
                    SELECT AVG(latest_payments.diff)
                    FROM (
                        SELECT DISTINCT ON (am.id)
                            (ap.date - am.invoice_date) AS diff
                        FROM account_move__account_payment move_payement_rel
                        JOIN account_move am ON move_payement_rel.invoice_id = am.id
                        JOIN account_payment ap ON move_payement_rel.payment_id = ap.id
                        WHERE ap.id IN %(ids)s
                        ORDER BY am.id, ap.date DESC
                    ) AS latest_payments
                    """,
                    ids=tuple(reconciled_payments.ids),
                ))
                avg_days_payment = self.env.cr.fetchall()[0][0]

                self.env.cr.execute(SQL(
                    """
                    SELECT COUNT(ap.id)
                    FROM account_move__account_payment move_payement_rel
                    JOIN account_move am ON move_payement_rel.invoice_id = am.id
                    JOIN account_payment ap ON move_payement_rel.payment_id = ap.id
                    WHERE ap.id IN %(ids)s
                    AND am.invoice_date_due IS NOT NULL
                    AND ap.date <= am.invoice_date_due
                    """,
                    ids=tuple(reconciled_payments.ids),
                ))
                pct_payment_on_terms = round(self.env.cr.fetchall()[0][0] / len(reconciled_payments) * 100, 2) if reconciled_payments else 0
            return {
                'avg_days_payment': avg_days_payment,
                'pct_payment_on_terms': pct_payment_on_terms,
            }

        self.ensure_one()
        # Base Year
        base_year_start_date = 0
        base_year_end_date = 0
        has_base_year = self._has_valid_base_year()
        if has_base_year:
            base_year_date = self.company_id.sudo().compute_fiscalyear_dates(date(self.base_year, 1, 1))
            base_year_start_date = base_year_date['date_from']
            base_year_end_date = base_year_date['date_to']

        # Payment Terms data
        # Reporting Year
        payment_terms_data_reporting = get_payment_terms_data(self.start_date, self.end_date)
        avg_days_payment_reporting = payment_terms_data_reporting['avg_days_payment']
        pct_payment_on_terms_reporting = payment_terms_data_reporting['pct_payment_on_terms']
        # Base year
        avg_days_payment_base = 0
        pct_payment_on_terms_base = 0
        if has_base_year:
            payment_terms_data_base = get_payment_terms_data(base_year_start_date, base_year_end_date)
            avg_days_payment_base = payment_terms_data_base['avg_days_payment']
            pct_payment_on_terms_base = payment_terms_data_base['pct_payment_on_terms']

        data = {
            'report_name': self.title,
            'company_name': self.company_id.name,
            'date_start': format_date(self.env, self.start_date),
            'date_end': format_date(self.env, self.end_date),
            'avg_days_payment_reporting': str(round(avg_days_payment_reporting, 2)),
            'pct_payment_on_terms_reporting': str(round(pct_payment_on_terms_reporting, 2)),
            'avg_days_payment_base': str(round(avg_days_payment_base, 2)) if has_base_year else '',
            'pct_payment_on_terms_base': str(round(pct_payment_on_terms_base, 2)) if has_base_year else '',
        }

        if self.report_type != 'csrd':
            report_types_dict = dict(self._fields['report_type']._description_selection(self.env))
            balance_sheet_total = self.env['account.move.line'].sudo()._read_group(
                domain=[
                    ('parent_state', '=', 'posted'),
                    ('account_type', 'in', ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 'asset_prepayments']),
                    ('date', '>=', self.start_date),
                    ('date', '<=', self.end_date),
                ],
                aggregates=['balance:sum'],
            )
            net_turnover = self.env['account.move.line'].sudo()._read_group(
                domain=[
                    ('parent_state', '=', 'posted'),
                    ('account_type', 'in', ['income', 'income_other']),
                    ('date', '>=', self.start_date),
                    ('date', '<=', self.end_date),
                ],
                aggregates=['balance:sum'],
            )
            ghg_total = self.env['esg.carbon.emission.report'].sudo()._read_group(
                domain=[
                    ('esg_emission_factor_id', '!=', False),
                    ('date', '>=', self.start_date),
                    ('date', '<=', self.end_date),
                ],
                aggregates=['esg_emissions_value_t:sum'],
            )
            main_market_regions = []
            for country, _count in self.env['account.move'].sudo()._read_group(
                domain=[
                    ('state', '=', 'posted'),
                    ('move_type', 'in', self.env['account.move'].get_sale_types(include_receipts=True)),
                    ('invoice_date', '>=', self.start_date),
                    ('invoice_date', '<=', self.end_date),
                ],
                groupby=['partner_id.country_id'],
                aggregates=['__count'],
                order='__count desc',
                limit=5,
            ):
                if country and country.name not in main_market_regions:
                    main_market_regions.append(country.name)
            undefined = self.env._('[Not Mentioned]')
            data.update({
                'reporting_type': report_types_dict.get(self.report_type, undefined),
                'legal_form': self.company_id.partner_id._get_preferred_legal_entity_identifier_vals().get('value') or undefined,
                'nace_code': self.nace_id.complete_name or undefined,
                'country_of_main_operations': self.company_id.country_id.name or undefined,
                'balance_sheet_total': str(balance_sheet_total[0][0]) if balance_sheet_total else str(0.0),
                'net_turnover': str(net_turnover[0][0]) if net_turnover else str(0.0),
                'ghg_total': str(ghg_total[0][0]) if ghg_total else str(0.0),
                'ghg_intensity': str(round(ghg_total[0][0] / net_turnover[0][0], 5)) if ghg_total and net_turnover and net_turnover[0][0] != 0 else str(0.0),
                'main_market_regions': ', '.join(main_market_regions) if main_market_regions else undefined,
            })

        return data

    def _get_esg_action_attachments(self, actions):
        """ Return a mapping from each action's id to its non-chatter attachments (name + download url),
        excluding attachments coming from chatter messages (e.g. inline images) rather than deliberate uploads.
        """
        if not actions:
            return {}

        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', actions._name),
            ('res_id', 'in', actions.ids),
        ])
        message_attachment_ids = set(actions.mapped('message_ids.attachment_ids').ids)
        attachments = attachments - self.env['ir.attachment'].browse(message_attachment_ids)
        attachments.sudo().generate_access_token()

        attachments_per_action = defaultdict(list)
        for attachment in attachments:
            attachments_per_action[attachment.res_id].append({
                'name': attachment.name,
                'url': f'/web/content/{attachment.id}?access_token={attachment.access_token}&download=true',
            })
        return attachments_per_action

    def _get_knowledge_report_actions_data(self):
        """ Return the Actions relevant to this report as a flat list.

        Each entry carries the Metric it is linked to, so all actions can be reported together
        in a single global appendix regardless of which section(s) they relate to.

        :return: {'actions': [...], 'attachments': [...]}
        """
        self.ensure_one()
        if self.report_type != 'csrd':
            return {}

        def format_period(start, end):
            if start and end:
                return f'{format_date(self.env, start)} - {format_date(self.env, end)}'
            return format_date(self.env, start or end) if start or end else ''

        actions = self.env['esg.action'].search([
            ('metric_id', '!=', False),
            ('metric_id.date_start', '<=', self.end_date),
            ('metric_id.date_end', '>=', self.start_date),
        ])
        attachments_per_action = self._get_esg_action_attachments(actions)

        actions_data = [{
            'name': action.name,
            'code': action.metric_id.display_name,
            'esrs': action.esrs_id.code if action.esrs_id else '',
            'description': action.description,
            'has_values': action.has_target,
            'baseline_value': action.baseline_value,
            'baseline_period': format_period(action.baseline_start_date, action.baseline_end_date),
            'target_value': action.target_value,
            'target_period': format_period(action.target_start_date, action.target_end_date),
            'current_value': action.current_value,
            'current_value_date': format_date(self.env, action.current_value_date) if action.current_value_date else '',
            'unit_name': action.currency_id.name if action.measure_type == 'monetary' else action.uom_id.name,
        } for action in actions]

        attachments_data = [
            {'name': action.name, 'files': attachments_per_action[action.id]}
            for action in actions if attachments_per_action.get(action.id)
        ]

        return {
            'actions': actions_data,
            'attachments': attachments_data,
        }

    def action_set_to_draft(self):
        self.ensure_one()
        self.status = 'draft'

    def action_set_to_done(self):
        self.ensure_one()
        self.status = 'done'

    def action_edit_esg_report(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('esg.action_esg_report_quick_create')
        action['name'] = self.env._('Edit ESG Report')
        action['res_id'] = self.id
        action['context'] = {'default_report_type': self.report_type}
        return action

    def action_esg_report_pdf(self):
        self.ensure_one()
        return self.knowledge_article_id.action_export_esg_report_to_pdf()

    def action_update_materiality(self):
        self.ensure_one()
        if self.report_type != 'csrd':
            raise UserError(self.env._('You can only update the materiality of a CSRD report.'))
        material_metric_codes = set(
            self.env['esg.metric'].search_fetch(
                domain=[
                    ('date_start', '<=', self.end_date),
                    ('date_end', '>=', self.start_date),
                    ('materiality_type', '!=', 'non_material'),
                ],
                field_names=['esrs_code'],
            ).mapped('esrs_code')
        )
        root_article = self.knowledge_article_id
        stack = [root_article]

        while stack:
            article = stack.pop()
            fragment = html.fragment_fromstring(article.body, create_parent='div')

            is_section_updated = False
            for element in fragment.xpath('//*[@data-embedded-props]'):
                embedded_props = json.loads(element.get('data-embedded-props'))
                if esrs_code := embedded_props.get('esrs_code'):
                    embedded_props = json.loads(element.get('data-embedded-props'))
                    is_esrs_material = esrs_code in material_metric_codes

                    show_content = is_esrs_material == embedded_props.get('is_esrs_material')
                    embedded_props['showContent'] = show_content
                    element.set('data-embedded-props', json.dumps(embedded_props))
                    current_class = element.get('class', '')
                    if show_content:
                        # Remove 'd-print-none' if present
                        element.set('class', current_class.replace('d-print-none', ''))
                    else:
                        # Add 'd-print-none' if not already present
                        if 'd-print-none' not in current_class:
                            element.set('class', current_class + ' d-print-none')
                    is_section_updated = True

            if is_section_updated:
                elements = []
                for child in fragment.getchildren():
                    elements.append(html.tostring(child, encoding='unicode', method='html'))
                article.write({'body': ''.join(elements)})

            stack.extend(article.child_ids)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': self.env._(
                    'The sections of %(report_name)s have been succesfully updated with the latest materiality results.',
                    report_name=self.title,
                ),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_open_knowledge_report_article(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('knowledge.ir_actions_server_knowledge_home_page')
        action['context'] = {'res_id': self.knowledge_article_id.id}
        return action

    def _has_valid_base_year(self):
        self.ensure_one()
        return self.base_year >= 1000 and self.base_year <= 9999
