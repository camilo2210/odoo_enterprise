from odoo import api, fields, models


class L10nRoD300SubmissionWizard(models.TransientModel):
    _name = "l10n_ro.d300.submission.wizard"
    _inherit = "account.return.submission.wizard"
    _description = "Romania D300 Submission Wizard"

    l10n_ro_fiscal_address = fields.Char(
        string="Fiscal Domicile Address",
        help="Fiscal address of the organization (if not specified, the address set on company will be used).",
    )
    l10n_ro_declarant_name = fields.Char(string="Name", size=75)
    l10n_ro_declarant_surname = fields.Char(string="Surname", size=75)
    l10n_ro_declarant_role = fields.Char(string="Role", size=50)
    l10n_ro_bank_name = fields.Char(string="Bank Name", size=50)
    l10n_ro_bank_account = fields.Char(string="Bank Account", size=50)
    l10n_ro_caen_code = fields.Char(
        string="CAEN Code",
        size=4,
        help="Enter your 4-digit code (Classification of Activities in the National Economy)",
    )
    l10n_ro_return_period = fields.Selection(
        selection=[
            ("L", "Monthly (L)"),
            ("T", "Quarterly (T)"),
            ("S", "Biannual (S)"),
            ("A", "Annual (A)"),
        ],
        default="L",
        string="Period",
    )
    l10n_ro_pro_rata = fields.Float(string="Pro-rata", default=100.00)
    l10n_ro_request_refund = fields.Boolean(string="Ask VAT Reimbursement")
    l10n_ro_filed_by_representative = fields.Boolean(string="Declared by the Representative of the Single Tax Group")
    l10n_ro_simplified_internal = fields.Boolean(string="Applies Simplified Method (Internal Operations)")
    l10n_ro_post_audit_filing = fields.Boolean(string="Filing after Cancellation of Verification Reserve")
    l10n_ro_sale_cereals = fields.Boolean(string="Sale of Cereals/Technical Plants")
    l10n_ro_sale_mobile_phones = fields.Boolean(string="Sale of Mobile Phones")
    l10n_ro_sale_integrated_circuits = fields.Boolean(string="Sale of Integrated Circuits")
    l10n_ro_sale_consoles_tablets_laptops = fields.Boolean(string="Sale of Consoles, Tablets or Laptops")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            return_id = vals.get("return_id")
            if not return_id:
                continue
            current_return = self.env["account.return"].browse(return_id)
            last_return = self._get_last_d300_return(current_return)
            if not last_return:
                continue
            for wiz_field in self._fields:
                if (
                    wiz_field.startswith("l10n_ro_")
                    and wiz_field in current_return._fields
                    and wiz_field not in vals
                ):
                    value = last_return[wiz_field]
                    if value:
                        vals[wiz_field] = value
        return super().create(vals_list)

    def _get_last_d300_return(self, current_return):
        ro_return_type = self.env.ref("l10n_ro_reports.ro_tax_return_type", raise_if_not_found=False)
        if not ro_return_type:
            return self.env["account.return"]
        domain = [
            ("company_id", "=", current_return.company_id.id),
            ("type_id", "=", ro_return_type.id),
            ("state", "in", ("paid", "reviewed")),
            ("id", "!=", current_return.id),
        ]
        return self.env["account.return"].search(domain, order="date_to desc", limit=1)

    def action_proceed_with_submission(self):
        self.ensure_one()
        self.return_id.write(
            {
                wiz_field: self[wiz_field]
                for wiz_field in self._fields
                if wiz_field.startswith("l10n_ro_") and wiz_field in self.return_id._fields
            }
        )
        options = self.return_id._get_closing_report_options()
        options.update({"return_id": self.return_id})
        self.return_id._add_attachment(self.env["l10n_ro.d300.report.handler"].export_tax_report_to_xml(options))
        return self.return_id._proceed_with_submission()

    def print_xml(self):
        xml_file = self.return_id.attachment_ids.filtered(lambda a: a.mimetype == 'application/xml')
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{xml_file.id}?download=true",
            "target": "download",
        }
