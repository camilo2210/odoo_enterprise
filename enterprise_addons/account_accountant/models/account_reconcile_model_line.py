from odoo import Command, _, api, models
from odoo.exceptions import RedirectWarning, UserError

import json
import re

from math import copysign


def split_amount_str(amount_str):
    """
    Parse a localized amount string into (int_part, dec_part) as strings
    Detects the number format (European/US) purely from the string structure.
    See the test test_split_amount_string for examples.
    :param amount_str:   The amount string to parse.
    :return: Tuple of (int_part, dec_part) as strings e.g. ('1334', '07') or ('0', '0') for invalid/empty input.
    """
    if not amount_str:
        return ('0', '0')

    # Normalize NBSP and trim
    groupings_re = "[ '\xa0]"
    has_grouping = bool(re.search(groupings_re, amount_str))
    amount_str = re.sub(groupings_re, "", amount_str).strip()
    commas = amount_str.count(',')
    dots = amount_str.count('.')
    last_comma, last_dot = amount_str.rfind(','), amount_str.rfind('.')
    comma_distance = len(amount_str) - 1 - last_comma if last_comma >= 0 else -1
    dot_distance = len(amount_str) - 1 - last_dot if last_dot >= 0 else -1

    def solitary(int_part, distance):
        return (
            not has_grouping
            and distance == 3
            and int_part.isdigit()
            and len(int_part) <= 3
            and int_part != '0'
        )

    match (commas, dots):
        case (0, 0):
            tsep, dsep = ',', '.'  # '1334'
        case (c, 0) if c > 1:
            tsep, dsep = ',', '.'  # '1,334,567'
        case (0, d) if d > 1:
            tsep, dsep = '.', ','   # '1.334.567'
        case (c, 1) if c > 1:
            tsep, dsep = ',', '.'
        case (1, d) if d > 1:
            tsep, dsep = '.', ','
        case (1, 1) if last_comma > last_dot:
            tsep, dsep = '.', ','
        case (1, 1):
            tsep, dsep = ',', '.'
        case (0, 1) if solitary(amount_str[:last_dot], dot_distance):
            tsep, dsep = '.', ','  # best possible assumption
        case (0, 1):
            tsep, dsep = ',', '.'
        case (1, 0) if solitary(amount_str[:last_comma], comma_distance):
            tsep, dsep = ',', '.'  # best possible assumption
        case (1, 0):
            tsep, dsep = '.', ','
        case _:
            return ('0', '0')

    parts = amount_str.replace(tsep, '').split(dsep)
    if len(parts) > 2:
        return ('0', '0')
    return tuple((parts + ['0'])[:2])


class AccountReconcileModelLine(models.Model):
    _inherit = 'account.reconcile.model.line'

    def _get_aml_name(self):
        """ Return the label to write on the journal item created from this reconcile model line.

        'label' is a translatable field, so its value depends on the language of whoever applies
        the model: a user working in another language, or the auto-reconciliation cron, which runs
        as OdooBot. The same model then writes a different label depending on who applied it. The
        journal item belongs to the company, so the company language is used to read the label.

        :return: The label, in the language of the company.
        """
        self.ensure_one()
        lang = self.company_id.partner_id.lang
        return self.with_context(lang=lang).label if lang else self.label

    def _prepare_aml_vals(self, partner):
        """ Prepare a dictionary that will be used later to create a new journal item (account.move.line) for the
        given reconcile model line.

        :param partner: The partner to be linked to the journal item.
        :return:        A python dictionary.
        """
        self.ensure_one()

        taxes = self.tax_ids or self.account_id.tax_ids
        if taxes and partner:
            fiscal_position = self.env['account.fiscal.position']._get_fiscal_position(partner)
            if fiscal_position:
                taxes = fiscal_position.map_tax(taxes)

        values = {
            'name': self._get_aml_name(),
            'partner_id': partner.id,
            'analytic_distribution': self.analytic_distribution,
            'reconcile_model_id': self.model_id.id,
        }
        if taxes:
            values['tax_ids'] = [Command.set(taxes.ids)]
        if self.account_id:
            values['account_id'] = self.account_id.id
        return values

    def _apply_in_manual_widget(self, residual_amount_currency, residual_balance, partner, st_line):
        """ Prepare a dictionary that will be used later to create a new journal item (account.move.line) for the
        given reconcile model line used by the manual reconciliation widget.

        :param residual_amount_currency:    The current amount currency expressed in the account's currency.
        :param residual_balance:            The current balance expressed in the company currency.
        :param partner:                     The partner to be linked to the journal item.
        :param st_line:                     The statement line.
        :return:                            A python dictionary.
        """
        self.ensure_one()

        currency = st_line.foreign_currency_id or st_line.journal_id.currency_id or st_line.company_currency_id
        if self.amount_type == 'percentage':
            amount_currency = currency.round(residual_amount_currency * (self.amount / 100.0))
            balance = st_line.company_currency_id.round(residual_balance * (self.amount / 100.0))
        elif self.amount_type == 'fixed':
            sign = 1 if residual_amount_currency > 0.0 else -1
            amount_currency = currency.round(self.amount * sign)
            balance = st_line.company_currency_id.round(self.amount * sign)
        else:
            raise UserError(_("This reconciliation model can't be used in the manual reconciliation widget because its "
                              "configuration is not adapted"))

        return {
            **self._prepare_aml_vals(partner),
            'currency_id': currency.id,
            'balance': balance,
            'amount_currency': amount_currency,
        }

    def _apply_in_bank_widget(self, residual_amount_currency, residual_balance, partner, st_line):
        """ Prepare a dictionary that will be used later to create a new journal item (account.move.line) for the
        given reconcile model line used by the bank reconciliation widget.

        :param residual_amount_currency:    The current amount currency expressed in the statement line's currency.
        :param residual_balance:            The current balance expressed in the company currency.
        :param partner:                     The partner to be linked to the journal item.
        :param st_line:                     The statement line mounted inside the bank reconciliation widget.
        :return:                            A python dictionary.
        """
        self.ensure_one()
        currency = st_line.foreign_currency_id or st_line.journal_id.currency_id or st_line.company_currency_id

        aml_values = {'currency_id': currency.id}

        if self.amount_type == 'percentage_st_line':
            _transaction_amount, _transaction_currency, journal_amount, journal_currency, company_amount, company_currency \
                = st_line._get_accounting_amounts_and_currencies()
            aml_values['amount_currency'] = currency.round(-journal_amount * self.amount / 100.0)
            aml_values['balance'] = company_currency.round(-company_amount * self.amount / 100.0)
            aml_values['currency_id'] = journal_currency.id
        elif self.amount_type == 'regex':
            aml_values['amount_currency'] = self._get_amount_currency_by_regex(st_line, residual_amount_currency, self.amount_string)
            aml_values['balance'] = currency._convert(aml_values['amount_currency'], st_line.company_currency_id, st_line.company_id, st_line.date)

        if 'amount_currency' not in aml_values or 'balance' not in aml_values:
            aml_values.update(self._apply_in_manual_widget(
                residual_amount_currency=residual_amount_currency,
                residual_balance=residual_balance,
                partner=partner,
                st_line=st_line,
            ))
        else:
            aml_values.update(self._prepare_aml_vals(partner))

        if not aml_values.get('name', False):
            aml_values['name'] = st_line.payment_ref

        return aml_values

    @api.model
    def _get_amount_currency_by_regex(self, st_line, residual_amount_currency, amount_string):
        sign = 1 if residual_amount_currency > 0.0 else -1
        transaction_details = json.dumps(st_line.transaction_details) if st_line.transaction_details else False
        for target_field in (st_line.payment_ref, transaction_details, st_line.narration):
            if not target_field:
                continue
            if match := re.search(amount_string, target_field):
                try:
                    # If there is only one capturing group in the regex, extract the amount from it.
                    # If there are two capturing groups, then first group have integer part and second group have decimal part of the amount.
                    groups = match.groups()
                    if len(groups) >= 2:
                        group_iter = iter(groups)
                        int_part = str(next(group_iter) or '0').replace('.', '').replace(',', '')
                        dec_part = next(group_iter, None)
                        dec_part = dec_part if dec_part and dec_part.isdigit() else '0'
                        extracted_balance = float(f'{int_part}.{dec_part}')
                    else:
                        extracted_match_group = re.search(r"\d[\d\s.,'\xa0]*", match.group(1))
                        int_part, dec_part = split_amount_str(extracted_match_group.group())
                        extracted_balance = float(f"{int_part}.{dec_part}")
                    return copysign(extracted_balance * sign, residual_amount_currency)
                except IndexError:         # from .group(1) if the regex doesn't contain a parenthesis part
                    raise RedirectWarning(_("The regular expression for capturing the counterpart amount appears to be incorrectly formatted.\n"
                        "Please make sure that the part of the regex capturing the amount is the first (or only) one in parentheses, for example: BRT: ([\\d,.]+)."),
                        self.model_id._get_records_action(),
                        _("Open reconcile model")
                    )
                except AttributeError:     # from an inconclusive search -> None.group().replace(...)
                    raise RedirectWarning(_("The regular expression for capturing the counterpart amount appears to be incorrectly formatted.\n"
                        "Please make sure that the part of the regex capturing the amount (in parentheses) cannot capture an empty value (usually by an incorrect use of ? or *) "
                        "or any value with no digit. For example: BRT: ([\\d,.]+)."),
                        self.model_id._get_records_action(),
                        _("Open reconcile model")
                    )
        return 0.0
