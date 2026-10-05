# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta
import calendar
import io

from lxml import etree
import re

from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def create_document_from_attachment(self, attachment_ids=None):
        # OVERRIDE
        journal = self or self.browse(self.env.context.get('default_journal_id'))
        if journal.type == 'general':
            attachments = self.env['ir.attachment'].browse(attachment_ids or [])
            if not attachments:
                raise UserError(_("No attachment was provided"))
            if all(journal._l10n_be_check_soda_format(attachment) for attachment in attachments):
                return journal._l10n_be_parse_soda_file(attachments)
        return super().create_document_from_attachment(attachment_ids)

    def _l10n_be_check_soda_format(self, attachment):
        try:
            return (
                (attachment.mimetype in ('application/xml', 'text/xml')
                # XML files sent by email have text/plain as mimetype
                or (attachment.mimetype == 'text/plain' and attachment.name.lower().endswith('.xml')))
                and etree.parse(io.BytesIO(attachment.raw)).getroot().tag == 'SocialDocument'
            )
        except etree.XMLSyntaxError:
            return False

    def _l10n_be_parse_soda_file(self, attachments, skip_wizard=False, move=None):
        self.ensure_one()
        # We keep a dict mapping the SODA reference to a dict with a list of `entries` and an `attachment_id`
        # {
        #     'soda_reference_1': {
        #         'entries': [
        #             {
        #                 'code': '1200',
        #                 'name': 'Line Description',
        #                 'debit': '150.0',
        #                 'credit': '0.0',
        #                 'department': 'DEP',
        #             },
        #             ...
        #         ],
        #         'attachment_id': 'attachment_id_1',
        #     },
        #     ...
        # }
        soda_files = {}
        soda_code_to_name_mapping = {}
        soda_departments = set()
        errors_to_chatter = set()
        for attachment in attachments:
            parsed_attachment = etree.parse(io.BytesIO(attachment.raw))
            # The document VAT number must match the journal's company's VAT number
            journal_company_vat = self.company_id.vat or self.company_id.partner_id._get_additional_identifier('BE_EN')
            journal_company_vat = journal_company_vat and re.sub("[^0-9]", "", journal_company_vat)
            parsed_ent_num = parsed_attachment.find('.//EntNum')
            ent_num = parsed_ent_num.text and re.search(r'\d+', parsed_ent_num.text).group()
            if ent_num != journal_company_vat:
                if len(attachments) == 1:
                    message = _('The imported document doesn\'t seem to correspond to this company\'s VAT number nor company id')
                else:
                    message = _('The company VAT number found in at least one document doesn\'t seem to correspond to this company\'s VAT number nor company id')
                errors_to_chatter.add(message)
            # account.move.ref is SocialNumber+SequenceNumber+AccountPeriodYYYY/AccountPeriodmm : check that this move has not already been imported
            account_period = parsed_attachment.find('.//AccountPeriod').text
            account_period_year, account_period_month = account_period[:4], account_period[4:]
            ref = "%s-%s-%s/%s" % (parsed_attachment.find('.//Source').text, parsed_attachment.find('.//SeqNumber').text, account_period_year, account_period_month)
            if existing_move := self.env['account.move'].search([('ref', '=', ref), ('company_id', '=', self.company_id.id)]):
                if self.env.context.get('raise_no_imported_file', True):
                    raise UserError(self.env._('The entry %(entry)s has already been uploaded (%(existing_entry)s).', entry=ref, existing_entry=existing_move.name))
                else:
                    return

            account_period_date = date(int(account_period_year), int(account_period_month), calendar.monthrange(int(account_period_year), int(account_period_month))[1])
            accounting_date = max(account_period_date, self.company_id._get_user_fiscal_lock_date(self) + timedelta(days=1))
            soda_files[ref] = {
                'entries': [],
                'attachment_id': attachment.id,
                'date': accounting_date.strftime("%Y-%m-%d") or fields.Date.context_today(self).strftime("%Y-%m-%d"),
            }
            # Iterating on TransactionLine elements since we need both Accounting (aml) and Department (analytic) elements
            for transaction_line in parsed_attachment.findall('.//TransactionLine'):
                # Retrieve aml data
                code = transaction_line.find('./Accounting/Account').text
                name = transaction_line.find('./Accounting/Label').text
                soda_code_to_name_mapping[code] = name
                vals = {
                    'code': code,
                    'name': name,
                    'debit': float(transaction_line.find('./Accounting/Amount/Debit').text),
                    'credit': float(transaction_line.find('./Accounting/Amount/Credit').text),
                }

                # Retrieve analytic data
                department = transaction_line.find('./Department')
                if department is not None and department.text:
                    soda_departments.add(department.text)
                    vals['department'] = department.text

                soda_files[ref]['entries'].append(vals)

        wizard = self.env['soda.import.wizard'].create({
            'soda_files': soda_files,
            'soda_code_to_name_mapping': soda_code_to_name_mapping,
            'soda_departments': list(soda_departments),
            'company_id': self.company_id.id,
            'journal_id': self.id,
        })
        if skip_wizard:
            return wizard._action_save_and_import(existing_move=move)
        return {
            'name': _('SODA Import'),
            'type': 'ir.actions.act_window',
            'views': [(False, 'form')],
            'view_mode': 'form',
            'view_id': self.env.ref('l10n_be_soda.soda_import_wizard_view_form').id,
            'res_model': 'soda.import.wizard',
            'res_id': wizard.id,
            'target': 'new',
            'context': {
                'errors': list(errors_to_chatter),
            },
        }
