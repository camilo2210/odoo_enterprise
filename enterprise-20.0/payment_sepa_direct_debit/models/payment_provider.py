# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.const import REPORT_REASONS_MAPPING
from odoo.addons.payment_sepa_direct_debit import const


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    custom_mode = fields.Selection(selection_add=[("sepa_direct_debit", "SEPA Direct Debit")])

    # === COMPUTE METHODS === #

    def _compute_feature_support_fields(self):
        """Override of `payment` to enable additional features."""
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.custom_mode == "sepa_direct_debit").update({
            "support_tokenization": True
        })

    def _get_supported_currencies(self):
        """Override of `payment` to return EUR as the only supported currency."""
        supported_currencies = super()._get_supported_currencies()
        if self.custom_mode == "sepa_direct_debit":
            supported_currencies = supported_currencies.filtered(lambda c: c.name == "EUR")
        return supported_currencies

    def _get_journal_domain(self):
        """Override of `account_payment` to exclude journals already linked to a SEPA provider."""
        domain = super()._get_journal_domain()
        if self.custom_mode == "sepa_direct_debit":
            domain = Domain.AND([
                domain,
                ["!", ("inbound_payment_method_line_ids.code", "=", "sepa_direct_debit")],
            ])
        return domain

    # === CONSTRAINT METHODS === #

    @api.constrains("is_live", "journal_id")
    def _check_journal_iban_is_valid(self):
        """Check that the bank account of the payment journal is a valid IBAN."""
        for provider in self.filtered(lambda p: p.custom_mode == "sepa_direct_debit" and p.is_live):
            if provider.journal_id.bank_account_id.account_type != "iban":
                raise ValidationError(
                    provider.env._("The bank account of the journal is not a valid IBAN.")
                )

    @api.constrains("is_live", "company_id")
    def _check_has_creditor_identifier(self):
        """Check that the company has a creditor identifier."""
        for provider in self.filtered(lambda p: p.custom_mode == "sepa_direct_debit" and p.is_live):
            if not provider.company_id.sdd_creditor_identifier:
                raise ValidationError(
                    provider.env._(
                        "Your company must have a creditor identifier in order to issue a SEPA"
                        " Direct Debit payment request. It can be set in Accounting settings."
                    )
                )

    @api.constrains("available_country_ids")
    def _check_country_in_sepa_zone(self):
        """Check that all selected countries are in the SEPA zone."""
        sepa_countries = self.env.ref("base.sepa_zone").country_ids
        for provider in self.filtered(lambda p: p.custom_mode == "sepa_direct_debit"):
            non_sepa_countries = provider.available_country_ids - sepa_countries
            if non_sepa_countries:
                raise ValidationError(
                    provider.env._(
                        "Restricted to countries in the SEPA zone. Forbidden countries: %s",
                        ", ".join(non_sepa_countries.mapped("name")),
                    )
                )

    # === CRUD METHODS === #

    def _get_default_payment_method_codes(self):
        """Override of `payment` to return the default payment method codes."""
        self.ensure_one()
        if self.custom_mode != "sepa_direct_debit":
            return super()._get_default_payment_method_codes()
        return const.DEFAULT_PAYMENT_METHOD_CODES

    # === BUSINESS METHODS === #

    @api.model
    def _find_available_providers(self, *args, is_validation=False, report=None, **kwargs):
        """Override of `payment` to unlist SDD providers for validation flows.

        Tokens are created automatically once the direct transaction is confirmed, but cannot be
        created through validation flows.
        """
        providers = super()._find_available_providers(
            *args, is_validation=is_validation, report=report, **kwargs
        )

        if is_validation:
            unfiltered_providers = providers
            providers = providers.filtered(
                lambda p: p.code != "custom" or p.custom_mode != "sepa_direct_debit"
            )
            payment_utils.add_to_report(
                report,
                unfiltered_providers - providers,
                available=False,
                reason=REPORT_REASONS_MAPPING["validation_not_supported"],
            )

        return providers

    def _get_custom_bank_account(self):
        """Override to return the bank account of the selected journal."""
        if self.custom_mode != "sepa_direct_debit":
            return super()._get_custom_bank_account()
        return self.journal_id.bank_account_id

    def _is_tokenization_required(self, **kwargs):
        """Override of payment to hide the "Save my payment details" input in checkout forms.

        :return: Whether the provider is SEPA
        :rtype: bool
        """
        res = super()._is_tokenization_required(**kwargs)
        if len(self) != 1 or self.custom_mode != "sepa_direct_debit":
            return res

        return True

    def _sdd_find_or_create_mandate(self, partner_id, iban):
        """Find or create the SDD mandate verified by the given phone.

        Note: self.ensure_one()

        :param int partner_id: The partner making the transaction, as a `res.partner` id
        :param str iban: The sanitized IBAN number of the partner's bank account
        :return: The SDD mandate
        :rtype: recordset of `sdd.mandate`
        """
        self.ensure_one()

        commercial_partner_id = self.env["res.partner"].browse(partner_id).commercial_partner_id.id
        partner_bank = self._sdd_find_or_create_partner_bank(partner_id, iban)
        mandate = self.env["account.direct.debit.mandate"].search(
            [
                ("mandate_type", "=", "sepa"),
                ("state", "not in", ["closed", "revoked"]),
                ("start_date", "<=", datetime.now()),
                "|",
                ("end_date", ">=", datetime.now()),
                ("end_date", "=", None),
                ("partner_id", "=", commercial_partner_id),
                ("partner_bank_id", "=", partner_bank.id),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )
        if not mandate:
            mandate = self.env["account.direct.debit.mandate"].create({
                "mandate_type": "sepa",
                "partner_id": commercial_partner_id,
                "partner_bank_id": partner_bank.id,
                "start_date": datetime.now(),
                "state": "draft",
                "company_id": self.company_id.id,
            })
        return mandate

    def _sdd_find_or_create_partner_bank(self, partner_id, iban):
        """Find or create the partner bank with the given iban.

        Note: self.ensure_one()

        :param int partner_id: The partner making the transaction, as a `res.partner` id
        :param str iban: The sanitized IBAN number of the partner's bank account
        :return: The partner bank
        :rtype: recordset of `res.partner.bank`
        """
        self.ensure_one()

        commercial_partner = self.env["res.partner"].browse(partner_id).commercial_partner_id
        return self.env["res.partner.bank"]._find_or_create_bank_account(
            account_number=iban,
            partner=commercial_partner,
            company=self.company_id,
            extra_create_vals={"company_id": self.company_id.id},
        )

    def _sdd_create_token_for_mandate(self, partner, mandate):
        """Create a token linked to the mandate with the obfuscated IBAN as name and return it.

        :param res.partner partner: The partner making the transaction.
        :param sdd.mandate mandate: The mandate to link to the token.
        :return: The created token.
        :rtype: payment.token
        :raise AccessError: If the partner is different than the mandate's partner.
        """
        # Since we're in a sudoed env, we need to verify the partner
        if mandate.partner_id != partner.commercial_partner_id:
            raise AccessError(self.env._("The mandate owner and customer do not match."))

        return self.env["payment.token"].create({
            "provider_id": self.id,
            "payment_method_id": self.payment_method_ids[:1].id,
            "payment_details": mandate.partner_bank_id.account_number,
            "partner_id": partner.id,
            "provider_ref": mandate.name,
            "sdd_mandate_id": mandate.id,
        })

    # === SETUP METHODS === #

    def _get_code(self):
        """Override of `payment` to trick the JS into believing the code is 'sepa_direct_debit'."""
        res = super()._get_code()
        if self.code == "custom" and self.custom_mode == "sepa_direct_debit":
            return self.custom_mode
        return res
