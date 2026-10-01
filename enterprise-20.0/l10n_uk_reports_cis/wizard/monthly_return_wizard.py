from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning


class MontlhyReturnWizard(models.TransientModel):
    _name = "cis.monthly.return.wizard"
    _description = "CIS monthly return wizard"

    return_id = fields.Many2one('account.return', string="Return", required=True)
    date_from = fields.Date(string="Date From", related="return_id.date_from")
    date_to = fields.Date(string="Date To", related="return_id.date_to")
    subcontractor_verification = fields.Boolean(string="Subcontractor Verification")
    employment_status = fields.Boolean(string="Employment Status")
    inactivity_indicator = fields.Boolean(string="Inactivity Indicator")
    information_correct = fields.Boolean(string="Information Correct")
    hmrc_cis_password = fields.Char(string="CIS password", store=False)
    already_submited_period = fields.Boolean(string="Already Submited Period", compute="_compute_already_submited_period")

    @api.depends("return_id.date_from", "return_id.date_to")
    def _compute_already_submited_period(self):
        for record in self:
            record.already_submited_period = bool(self.env['l10n_uk.hmrc.transaction'].search_count([
                ('company_id', '=', self.env.company.id),
                ('period_start', '=', record.date_from),
                ('period_end', '=', record.date_to),
                ('state', 'in', ('polling', 'success', 'deleted')),
            ], limit=1))

    @api.model
    def _open_submission_wizard(self, account_return):
        wizard = self.create({'return_id': account_return.id})
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Submit CIS return"),
            'view_mode': 'form',
            'res_model': wizard._name,
            'target': 'new',
            'res_id': wizard.id,
        }

    @api.model
    def action_send_montlhy_return(self, return_id, employment_status, subcontractor_verification, inactivity_indicator, hmrc_cis_password):
        cis_report = self.env.ref('l10n_uk_reports_cis.tax_report_cis')
        account_return = self.env['account.return'].browse(return_id)

        if not self.env.company.l10n_uk_hmrc_unique_taxpayer_reference or not self.env.company.l10n_uk_hmrc_account_office_reference:
            raise RedirectWarning(
                message=_("Please fill the CIS fields on the company."),
                action={
                    'view_mode': 'form',
                    'res_model': 'res.company',
                    'type': 'ir.actions.act_window',
                    'res_id': self.env.company.id,
                    'views': [(False, 'form')],
                },
                button_text=_("Open the company form"),
            )

        # Ensure that `export_mode` is set to `file` so we use default groupby and don't display comparison
        options = cis_report.get_options({
            'export_mode': 'file',
            'date': {
                'date_from': account_return.date_from,
                'date_to': account_return.date_to,
            },
        })

        lines = cis_report._get_lines(options)

        # The report gives us the lines for sales and purchase.
        # The CIS deduction monthly return is a document made by contractor for subcontractors to HMRC.
        # So in this case we only need the purchase part of the report
        cis_purchase_report_line_id = self.env.ref('l10n_uk_reports_cis.account_uk_cis_report_line_purchase').id
        partner_lines = [
            line for line in lines
            if line.groupby == 'move_id'
                and self.env['account.report']._get_res_id_from_line_id(line['id'], 'account.report.line') == cis_purchase_report_line_id
        ]

        document_data = {
            'inactivity_indicator': inactivity_indicator,
            'subcontractor_return_ids': [],
            'subcontractor_ids': [],
            'subcontractor_verification': subcontractor_verification,
            'employment_status': employment_status,
        }

        for partner_line in partner_lines:
            colname_to_idx = {col['expression_label']: idx for idx, col in enumerate(options.get('columns', []))}
            partner_id = cis_report._get_res_id_from_line_id(partner_line['id'], 'res.partner')
            document_data['subcontractor_return_ids'].append({
                'id': partner_id,
                'total_payment_made': partner_line.columns[colname_to_idx['payment']].no_format or 0.0,
                'direct_cost_of_materials': partner_line.columns[colname_to_idx['materials']].no_format or 0.0,
                'total_amount_deducted': partner_line.columns[colname_to_idx['deduction']].no_format or 0.0,
            })
            document_data['subcontractor_ids'].append(partner_id)

        transaction = self.env['l10n_uk.hmrc.transaction'].create({
            'transaction_type': 'cis_monthly_return',
            'period_start': account_return.date_from,
            'period_end': account_return.date_to,
            'company_id': self.env.company.id,
            'sender_user_id': self.env.user.id,
            'return_id': account_return.id,
        })

        transaction.sudo()._submit_cis_mr_transaction(
            credentials={
                'sender_id': self.env.company.l10n_uk_hmrc_sender_id,
                'password': hmrc_cis_password,
                'tax_office_number': self.env.company.l10n_uk_hmrc_tax_office_number,
                'tax_office_reference': self.env.company.l10n_uk_hmrc_tax_office_reference,
            },
            document_data=document_data,
        )
