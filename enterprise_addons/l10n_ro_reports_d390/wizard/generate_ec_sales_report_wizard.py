import json

from odoo import api, fields, models


class L10n_ro_ReportsGenerateEcSalesReport(models.TransientModel):
    """
    Primary purpose of this wizard is to get the Declaration information
    from the user to generate Romanian D390 EC Sales reoprt.
    """
    _name = 'l10n_ro_reports_d390.generate.ec.sales.report.wizard'
    _description = "Romanian EC Sales Report Generation Wizard"

    return_id = fields.Many2one(
        comodel_name='account.return',
        required=True,
    )
    l10n_ro_declarant_name = fields.Char(
        string="Name",
        readonly=False,
    )
    l10n_ro_declarant_surname = fields.Char(
        string="Surname",
        readonly=False,
    )
    l10n_ro_declarant_role = fields.Char(
        string="Job Role",
        readonly=False,
    )
    l10n_ro_fiscal_address = fields.Char(
        string="Fiscal Domicile Address",
        help="Adresă domiciliu fiscal: Fiscal address of the organization (if not specified, the address set on company will be used).",
        readonly=False,
    )
    l10n_ro_fax = fields.Char(
        string="Fax",
        readonly=False,
    )
    l10n_ro_d390_corrective_declaration = fields.Boolean(
        string="Corrective declaration",
        help="Is this return corrected/rectified?",
        default=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        ro_ec_sales_return_type = self.env.ref('l10n_ro_reports_d390.ro_ec_sales_list_return_type')
        for vals in vals_list:
            return_id = vals.get("return_id")
            if not return_id:
                continue
            current_return = self.env["account.return"].browse(return_id)

            # Fetch the latest previous RO EC Sales List return to reuse declaration information.
            previous_return = self.env['account.return'].search([
                ("company_id", "=", current_return.company_id.id),
                ('type_id', '=', ro_ec_sales_return_type.id),
                ('date_to', '<', current_return.date_from),
            ], order='date_to desc', limit=1)

            # Use values from the current return first, because it contains updated values in case,
            # the user reset the return and re-review it; otherwise use values from the previous return.
            for wiz_field in self._fields:
                if (
                    wiz_field.startswith("l10n_ro_")
                    and wiz_field in current_return._fields
                    and wiz_field not in vals
                ):
                    value = current_return[wiz_field] or (previous_return[wiz_field] if previous_return else '')
                    if value:
                        vals[wiz_field] = value
        return super().create(vals_list)

    def generate_xml(self):
        self.ensure_one()
        # Save the declaration information on the respective RO EC Sales List return
        self.return_id.write(
            {
                wiz_field: self[wiz_field]
                for wiz_field in self._fields
                if wiz_field.startswith("l10n_ro_") and wiz_field in self.return_id._fields
            }
        )
        report_gen_options = self.return_id._get_closing_report_options()
        report_gen_options['return_id'] = self.return_id.id

        # Attach RO EC Sales List D390 XML report in the return chatter and proceed with locking
        self.return_id._add_attachment(self.return_id.type_id.report_id.dispatch_report_action(report_gen_options, 'export_to_xml_sales_report'))
        self.return_id._proceed_with_locking()

        # Download RO EC Sales List D390 XML report
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(report_gen_options),
                'file_generator': 'export_to_xml_sales_report',
            },
        }
