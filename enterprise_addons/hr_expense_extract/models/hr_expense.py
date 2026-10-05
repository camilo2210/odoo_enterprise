# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.tools import is_html_empty
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT

OCR_VERSION = 133


class HrExpense(models.Model):
    _name = 'hr.expense'
    _inherit = ['extract.mixin.with.words', 'hr.expense']
    # We want to see the records that are just processed by OCR at the top of the list
    _order = "extract_state_processed desc, date desc, id desc"

    sample = fields.Boolean(help='Expenses created from sample receipt')

    @api.depends('state')
    def _compute_is_in_extractable_state(self):
        for expense in self:
            expense.is_in_extractable_state = expense.state == 'draft' and not expense.split_expense_origin_id

    @api.depends('extract_state', 'state')
    def _compute_extract_state_processed(self):
        # Overrides 'iap_extract'
        for expense in self:
            expense.extract_state_processed = expense.extract_state == 'waiting_extraction' and expense.state == 'draft'

    @api.model
    def _get_ocr_api_version(self):
        return OCR_VERSION

    @api.model
    def _get_api_route(self):
        return 'api/extract/expense/2'

    def _filter_preprocess_skipped_ocr(self):
        """ If the hr_expense_stripe module is installed we want to skip the OCR """
        if 'is_card_expense' not in self._fields:
            return self

        stripe_expenses = self.filtered('is_card_expense')
        stripe_expenses.write({'extract_state': 'done'})
        for expense in stripe_expenses:
            expense.message_post(body=self.env._("Receipt not digitized: the expense already includes Stripe data."))

        return self - stripe_expenses

    def _upload_to_extract(self):
        to_extract = self._filter_preprocess_skipped_ocr()
        if to_extract:
            super(HrExpense, to_extract)._upload_to_extract()

    def _autosend_for_digitization(self):
        to_extract = self.filtered(lambda e:
            e.company_id.expense_extract_show_ocr_option_selection == 'auto_send'
            and e.extract_can_show_send_button
        )._filter_preprocess_skipped_ocr()
        if to_extract:
            to_extract._send_batch_for_digitization()

    def _message_set_main_attachment_id(self, attachments, force=False, filter_xml=True):
        super()._message_set_main_attachment_id(attachments, force=force, filter_xml=filter_xml)
        if not self.sample and attachments:
            self._autosend_for_digitization()

    def _get_validation(self, field):
        text_to_send = {}
        if field == "total":
            text_to_send["content"] = self.price_unit
        elif field == "date":
            text_to_send["content"] = str(self.date) if self.date else False
        elif field == "description":
            text_to_send["content"] = self.name
        elif field == "currency":
            text_to_send["content"] = self.currency_id.name
        return text_to_send

    def action_submit(self, **kwargs):
        self._validate_ocr()
        res = super().action_submit(**kwargs)
        return res

    def _fill_document_with_results(self, ocr_results):
        if ocr_results is not None and self.state == "draft":
            vals = {}
            description_ocr = self._get_ocr_selected_value(ocr_results, 'description', "")
            total_ocr = self._get_ocr_selected_value(ocr_results, 'total', 0.0)
            date_ocr = self._get_ocr_selected_value(ocr_results, 'date', fields.Date.context_today(self).strftime(DEFAULT_SERVER_DATE_FORMAT))
            currency_ocr = self._get_ocr_selected_value(ocr_results, 'currency', self.env.company.currency_id.name)

            if not self.name:
                predicted_product_id = self._predict_product(description_ocr)
                if predicted_product_id:
                    vals['product_id'] = predicted_product_id
                else:
                    fallback_product = (
                        self.env['product.product'].search([('default_code', '=', 'EXP_GEN'), ('can_be_expensed', '=', True)], limit=1)
                        or self.env['product.product'].search([('can_be_expensed', '=', True)], limit=1)
                    )
                    if fallback_product:
                        vals['product_id'] = fallback_product.id

                vals['name'] = description_ocr

            context_create_date = fields.Date.context_today(self, self.create_date)
            if not self.date or self.date == context_create_date:
                vals['date'] = date_ocr

            product_id = vals.get('product_id', self.product_id.id)
            product_price = product_id and self.env['product.product'].with_company(self.company_id).browse(product_id).standard_price
            if product_price:
                vals['price_unit'] = product_price
                vals['total_amount_currency'] = product_price
                vals['total_amount'] = product_price
            else:
                vals['total_amount_currency'] = total_ocr
                vals['quantity'] = 1  # Always the case for expense that are not using a flat rate
                vals['price_unit'] = total_ocr
                current_currency = self.currency_id
                if not self.currency_id or self.currency_id == self.env.company.currency_id:
                    for comparison in ['=ilike', 'ilike']:
                        matched_currency = self.env["res.currency"].with_context(active_test=False).search([
                            '|', '|',
                            ('currency_unit_label', comparison, currency_ocr),
                            ('name', comparison, currency_ocr),
                            ('symbol', comparison, currency_ocr),
                        ])
                        if len(matched_currency) == 1:
                            current_currency = matched_currency

                vals['currency_id'] = current_currency.id
                if current_currency and current_currency != self.company_currency_id:
                    vals['total_amount'] = current_currency._convert(
                        total_ocr,
                        self.company_currency_id,
                        company=self.company_id,
                        date=vals.get('date', self.date),
                    )
                else:
                    vals['total_amount'] = total_ocr

            self.write(vals)

    @api.model
    def get_empty_list_help(self, help_message):
        if self.env.user.has_group('base.group_user'):
            has_expenses = bool(self.search_count([('employee_id', 'in', self.env.user.employee_ids.ids)]))
            if is_html_empty(help_message):
                help_message = Markup("""
                    <p class="o_view_nocontent_expense_receipt">
                        <div class="o_view_pink_overlay">
                            <p class="o_view_nocontent_expense_receipt_image"/>
                            <h2 class="d-md-block">
                                {title}
                            </h2>
                        </div>
                    </p>""").format(title=_("Upload or drop an expense receipt"))
            # add hint for extract if not already present and user might now have already used it
            extract_txt = _("try a sample receipt")
            if not has_expenses and extract_txt not in help_message:
                action_id = self.env.ref('hr_expense_extract.action_expense_sample_receipt').id
                help_message += Markup(
                    "<p class='text-muted mt-4'>Or <a type='action' name='%(action_id)s' class='o_select_sample'>%(extract_txt)s</a></p>"
                ) % {
                    'action_id': action_id,
                    'extract_txt': extract_txt,
                }

        return super().get_empty_list_help(help_message)

    def _get_ocr_module_name(self):
        return 'hr_expense_extract'

    def _get_ocr_option_can_extract(self):
        ocr_option = self.env.company.expense_extract_show_ocr_option_selection
        return ocr_option and ocr_option != 'no_send'

    def _get_validation_fields(self):
        return ['total', 'date', 'description', 'currency']

    def _get_user_error_invalid_state_message(self):
        return _("You cannot send a expense that is not in draft state!")

    def _upload_to_extract_success_callback(self):
        super()._upload_to_extract_success_callback()
        if 'isMobile' in self.env.context and self.env.context['isMobile']:
            for record in self:
                timer = 0
                while record.extract_state != 'waiting_validation' and timer < 10:
                    timer += 1
                    time.sleep(1)
                    record._check_ocr_status()

    @api.ondelete(at_uninstall=False)
    def _unlink_except_approved(self):
        super(HrExpense, self - self.filtered('sample'))._unlink_except_approved()

    def _do_approve(self):
        # If we're dealing with sample expenses (demo data) then we should NEVER create any account.move
        # EXTENDS account
        today = fields.Date.context_today(self)
        samples = self.filtered('sample')
        for expense in samples.filtered(lambda s: s.state in {'submitted', 'draft'}):
            expense.write(
                {
                    'approval_state': 'approved',
                    'manager_id': (expense.manager_id or self.env.user).id,
                    'approval_date': today,
                }
            )
            expense.update_activities_and_mails()
        for expense in samples:
            expense.state = 'paid'

        return super(HrExpense, self - samples)._do_approve()
