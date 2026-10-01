# pylint: disable=C0326
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import os
from freezegun import freeze_time
from unittest import skipIf
from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.exceptions import RedirectWarning
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestNlTaxReportSBR(TestAccountReportsCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('nl')
    def setUpClass(cls):
        super().setUpClass()

        cls.env.company.write({
            'vat': 'NL123456782B90',
            'l10n_nl_sbr_ob_nummer': '987654321B09',
        })

        products = [cls.product_a, cls.product_b]
        cls.init_invoice('out_invoice', products=products, invoice_date='2026-02-01').action_post()
        cls.init_invoice('in_invoice', products=products, invoice_date='2026-02-01').action_post()

    @classmethod
    def _get_move_create_data(cls, move_data, line_data):
        return {
            'partner_id': cls.partner.id,
            'invoice_date': '2025-04-15',
            'journal_id': cls.company_data['default_journal_sale'].id,
            'invoice_line_ids': [
                Command.create({
                    'name': 'Test',
                    'quantity': 1,
                    **line_data,
                }),
            ],
            **move_data,
        }

    @freeze_time('2026-02-23 18:45')
    def test_xbrl_export(self):
        # Create a new partner for the representative and link it to the company.
        representative = self.env['res.partner'].create({
            'name': 'Fidu NL',
            'street': 'Fidu Street 123',
            'city': 'Amsterdam',
            'zip': '1019',
            'country_id': self.env.ref('base.nl').id,
            'vat': 'NL123456782B90',
            'phone': '+31470123456',
            'email': 'info@fidu.nl',
        })
        self.env.company.account_representative_id = representative.id
        self.env.user.phone = '+31432112345'
        report = self.env.ref('l10n_nl.tax_report')
        date_from = fields.Date.from_string('2026-01-01')
        date_to = fields.Date.from_string('2026-12-31')
        options = self._generate_options(report, date_from, date_to)
        wizard = self.env['l10n_nl_reports.sbr.tax.report.wizard']\
            .with_context(default_date_from=date_from, default_date_to=date_to, options=options)\
            .create({'tax_consultant_number': '123456'})

        # This call will add the wanted values in the options
        wizard.action_download_xbrl_file()
        generated_xbrl = self.get_xml_tree_from_string(self.env['l10n_nl_reports.tax.report.handler'].export_tax_report_to_xbrl(options).get('file_content'))
        expected_xbrl = self.get_xml_tree_from_string('''
            <xbrli:xbrl xmlns:bd-i="http://www.nltaxonomie.nl/nt20/bd/20251210/dictionary/bd-data" xmlns:bd-t="http://www.nltaxonomie.nl/nt20/bd/20251210/dictionary/bd-tuples" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:bd-axes="http://www.nltaxonomie.nl/nt20/bd/20251210/validation/bd-axes" xmlns:bd-domains="http://www.nltaxonomie.nl/nt20/bd/20251210/validation/bd-domains" xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:xbrli="http://www.xbrl.org/2003/instance" xml:lang="nl">
                <link:schemaRef xlink:type="simple" xlink:href="http://www.nltaxonomie.nl/nt20/bd/20251210/entrypoints/bd-rpt-ob-aangifte-2026.xsd"/>
                <xbrli:context id="Msg">
                    <xbrli:entity>
                        <xbrli:identifier scheme="www.belastingdienst.nl/omzetbelastingnummer">987654321B09</xbrli:identifier>
                    </xbrli:entity>
                    <xbrli:period>
                        <xbrli:startDate>2026-01-01</xbrli:startDate>
                        <xbrli:endDate>2026-12-31</xbrli:endDate>
                    </xbrli:period>
                </xbrli:context>
                <xbrli:context id="Msg_PASN1">
                    <xbrli:entity>
                        <xbrli:identifier scheme="www.belastingdienst.nl/omzetbelastingnummer">987654321B09</xbrli:identifier>
                    </xbrli:entity>
                    <xbrli:period>
                        <xbrli:startDate>2026-01-01</xbrli:startDate>
                        <xbrli:endDate>2026-12-31</xbrli:endDate>
                    </xbrli:period>
                    <xbrli:scenario>
                        <xbrldi:typedMember dimension="bd-axes:ProfessionalAssociationSerialNumberDimension">
                            <bd-domains:ProfessionalAssociationSerialNumberDomain>1</bd-domains:ProfessionalAssociationSerialNumberDomain>
                        </xbrldi:typedMember>
                    </xbrli:scenario>
                </xbrli:context>
                <xbrli:unit id="EUR">
                    <xbrli:measure>iso4217:EUR</xbrli:measure>
                </xbrli:unit>
                <bd-i:ContactInitials contextRef="Msg">BIAA</bd-i:ContactInitials>
                <bd-i:ContactPrefix contextRef="Msg">I am</bd-i:ContactPrefix>
                <bd-i:ContactSurname contextRef="Msg">accountman!</bd-i:ContactSurname>
                <bd-i:ContactTelephoneNumber contextRef="Msg">+31432112345</bd-i:ContactTelephoneNumber>
                <bd-i:ContactType contextRef="Msg">BPL</bd-i:ContactType>
                <bd-i:DateTimeCreation contextRef="Msg">202602231845</bd-i:DateTimeCreation>
                <bd-i:MessageReferenceSupplierVAT contextRef="Msg">___ignore___</bd-i:MessageReferenceSupplierVAT>
                <bd-i:ProfessionalAssociationForTaxServiceProvidersName contextRef="Msg_PASN1">NBA</bd-i:ProfessionalAssociationForTaxServiceProvidersName>
                <bd-i:SoftwarePackageName contextRef="Msg">Odoo</bd-i:SoftwarePackageName>
                <bd-i:SoftwarePackageVersion contextRef="Msg">___ignore___</bd-i:SoftwarePackageVersion>
                <bd-i:SoftwareVendorAccountNumber contextRef="Msg">swo02770</bd-i:SoftwareVendorAccountNumber>
                <bd-i:TaxConsultantNumber contextRef="Msg">123456</bd-i:TaxConsultantNumber>
                <bd-i:InstallationDistanceSalesWithinTheEC decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:InstallationDistanceSalesWithinTheEC>
                <bd-i:SuppliesServicesNotTaxed decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:SuppliesServicesNotTaxed>
                <bd-i:SuppliesToCountriesOutsideTheEC decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:SuppliesToCountriesOutsideTheEC>
                <bd-i:SuppliesToCountriesWithinTheEC decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:SuppliesToCountriesWithinTheEC>
                <bd-i:TaxedTurnoverPrivateUse decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:TaxedTurnoverPrivateUse>
                <bd-i:TaxedTurnoverSuppliesServicesGeneralTariff decimals="INF" contextRef="Msg" unitRef="EUR">1200</bd-i:TaxedTurnoverSuppliesServicesGeneralTariff>
                <bd-i:TaxedTurnoverSuppliesServicesOtherRates decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:TaxedTurnoverSuppliesServicesOtherRates>
                <bd-i:TaxedTurnoverSuppliesServicesReducedTariff decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:TaxedTurnoverSuppliesServicesReducedTariff>
                <bd-i:TurnoverFromTaxedSuppliesFromCountriesOutsideTheEC decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:TurnoverFromTaxedSuppliesFromCountriesOutsideTheEC>
                <bd-i:TurnoverFromTaxedSuppliesFromCountriesWithinTheEC decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:TurnoverFromTaxedSuppliesFromCountriesWithinTheEC>
                <bd-i:TurnoverSuppliesServicesByWhichVATTaxationIsTransferred decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:TurnoverSuppliesServicesByWhichVATTaxationIsTransferred>
                <bd-i:ValueAddedTaxOnInput decimals="INF" contextRef="Msg" unitRef="EUR">235</bd-i:ValueAddedTaxOnInput>
                <bd-i:ValueAddedTaxOnSuppliesFromCountriesOutsideTheEC decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:ValueAddedTaxOnSuppliesFromCountriesOutsideTheEC>
                <bd-i:ValueAddedTaxOnSuppliesFromCountriesWithinTheEC decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:ValueAddedTaxOnSuppliesFromCountriesWithinTheEC>
                <bd-i:ValueAddedTaxOwed decimals="INF" contextRef="Msg" unitRef="EUR">294</bd-i:ValueAddedTaxOwed>
                <bd-i:ValueAddedTaxOwedToBePaidBack decimals="INF" contextRef="Msg" unitRef="EUR">59</bd-i:ValueAddedTaxOwedToBePaidBack>
                <bd-i:ValueAddedTaxPrivateUse decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:ValueAddedTaxPrivateUse>
                <bd-i:ValueAddedTaxSuppliesServicesByWhichVATTaxationIsTransferred decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:ValueAddedTaxSuppliesServicesByWhichVATTaxationIsTransferred>
                <bd-i:ValueAddedTaxSuppliesServicesGeneralTariff decimals="INF" contextRef="Msg" unitRef="EUR">294</bd-i:ValueAddedTaxSuppliesServicesGeneralTariff>
                <bd-i:ValueAddedTaxSuppliesServicesOtherRates decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:ValueAddedTaxSuppliesServicesOtherRates>
                <bd-i:ValueAddedTaxSuppliesServicesReducedTariff decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:ValueAddedTaxSuppliesServicesReducedTariff>
            </xbrli:xbrl>
        ''')
        self.assertXmlTreeEqual(generated_xbrl, expected_xbrl)

    def test_suppletie_xbrl_export_and_closing_move(self):
        company_id = self.env.company.id
        tax_21_g_sale = self.env['account.tax'].search(
            [('type_tax_use', '=', 'sale'), ('name', '=', '21% ST'), ('company_id', '=', company_id)],
            limit=1,
        )
        self.env['account.move'].create([
            self._get_move_create_data(
                move_data={'move_type': 'out_invoice'},
                line_data={'price_unit': 1000, 'tax_ids': [Command.link(tax_21_g_sale.id)]},
            ),
        ])._post()

        # Create the regular VAT return for April
        april_return = self.env['account.return'].create({
            'name': "VAT April 2025",
            'date_from': '2025-04-01',
            'date_to': '2025-04-30',
            'type_id': self.env.ref('l10n_nl_reports.nl_tax_return_type').id,
            'company_id': company_id,
        })
        with self.allow_pdf_render():
            april_return.action_validate()

        self.assertRecordValues(
            april_return.closing_move_ids.line_ids,
            [
                {
                    'account_id': tax_21_g_sale.repartition_line_ids.account_id.id,
                    'balance': 210,
                },
                {
                    'account_id': april_return.type_id.with_company(self.env.company).tax_payable_account_id.id,
                    'balance': -210,
                },
            ],
        )

        # Reset tax lock date
        self.company.tax_lock_date = False

        # Add another entry for April
        self.env['account.move'].create([
            self._get_move_create_data(
                move_data={'move_type': 'out_invoice'},
                line_data={'price_unit': 250, 'tax_ids': [Command.link(tax_21_g_sale.id)]},
            ),
        ])._post()

        # Create the suppletie VAT return for April
        april_suppletie_return = self.env['account.return'].create({
            'name': "VAT Correction April 2025",
            'date_from': '2025-04-01',
            'date_to': '2025-04-30',
            'type_id': self.env.ref('l10n_nl_reports.nl_tax_correction_return_type').id,
            'company_id': company_id,
        })

        with self.allow_pdf_render():
            april_suppletie_return.action_validate()

        # Check whether the closing entry is correct
        self.assertRecordValues(
            april_suppletie_return.closing_move_ids.line_ids,
            [
                {
                    'account_id': tax_21_g_sale.repartition_line_ids.account_id.id,
                    'balance': 52.5,
                },
                {
                    'account_id': self.env.company.l10n_nl_rounding_difference_profit_account_id.id,
                    'balance': -0.5,
                },
                {
                    'account_id': april_suppletie_return.type_id.with_company(self.env.company).tax_payable_account_id.id,
                    'balance': -52.0,
                },
            ],
        )

        # Generate the XBRL to check whether it is correct
        report_options = april_suppletie_return._get_closing_report_options()
        wizard = self.env['l10n_nl_reports.sbr.tax.report.wizard'].with_context(
            default_date_from=report_options['date']['date_from'],
            default_date_to=report_options['date']['date_to'],
            options=report_options,
        ).create({})
        wizard.action_download_xbrl_file()
        generated_xbrl = self.get_xml_tree_from_string(self.env['l10n_nl_reports.tax.report.handler'].export_tax_report_to_xbrl(report_options).get('file_content'))
        expected_xbrl = self.get_xml_tree_from_string('''
            <xbrli:xbrl xmlns:bd-i="http://www.nltaxonomie.nl/nt19/bd/20241211/dictionary/bd-data" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:bd-t="http://www.nltaxonomie.nl/nt19/bd/20241211/dictionary/bd-tuples" xml:lang="nl">
                <link:schemaRef xlink:type="simple" xlink:href="http://www.nltaxonomie.nl/nt19/bd/20241211/entrypoints/bd-rpt-ob-suppletie-2025.xsd"/>
                <xbrli:context id="Msg">
                    <xbrli:entity>
                        <xbrli:identifier scheme="www.belastingdienst.nl/omzetbelastingnummer">987654321B09</xbrli:identifier>
                    </xbrli:entity>
                    <xbrli:period>
                        <xbrli:startDate>2025-04-01</xbrli:startDate>
                        <xbrli:endDate>2025-04-30</xbrli:endDate>
                    </xbrli:period>
                </xbrli:context>
                <xbrli:unit id="EUR">
                    <xbrli:measure>iso4217:EUR</xbrli:measure>
                </xbrli:unit>
                <bd-i:ContactInitials contextRef="Msg">___ignore___</bd-i:ContactInitials>
                <bd-i:ContactPrefix contextRef="Msg">___ignore___</bd-i:ContactPrefix>
                <bd-i:ContactSurname contextRef="Msg">___ignore___</bd-i:ContactSurname>
                <bd-i:ContactType contextRef="Msg">___ignore___</bd-i:ContactType>
                <bd-i:DateTimeCreation contextRef="Msg">___ignore___</bd-i:DateTimeCreation>
                <bd-i:InstallationDistanceSalesWithinTheEC decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:InstallationDistanceSalesWithinTheEC>
                <bd-i:MessageReferenceSupplierVAT contextRef="Msg">___ignore___</bd-i:MessageReferenceSupplierVAT>
                <bd-i:SoftwarePackageName contextRef="Msg">Odoo</bd-i:SoftwarePackageName>
                <bd-i:SoftwarePackageVersion contextRef="Msg">___ignore___</bd-i:SoftwarePackageVersion>
                <bd-i:SoftwareVendorAccountNumber contextRef="Msg">swo02770</bd-i:SoftwareVendorAccountNumber>
                <bd-i:SuppliesServicesNotTaxed decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:SuppliesServicesNotTaxed>
                <bd-i:SuppliesToCountriesOutsideTheEC decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:SuppliesToCountriesOutsideTheEC>
                <bd-i:SuppliesToCountriesWithinTheEC decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:SuppliesToCountriesWithinTheEC>
                <bd-i:TaxedTurnoverPrivateUse decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:TaxedTurnoverPrivateUse>
                <bd-i:TaxedTurnoverSuppliesServicesGeneralTariff decimals="INF" contextRef="Msg" unitRef="EUR">1250</bd-i:TaxedTurnoverSuppliesServicesGeneralTariff>
                <bd-i:TaxedTurnoverSuppliesServicesOtherRates decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:TaxedTurnoverSuppliesServicesOtherRates>
                <bd-i:TaxedTurnoverSuppliesServicesReducedTariff decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:TaxedTurnoverSuppliesServicesReducedTariff>
                <bd-i:TurnoverFromTaxedSuppliesFromCountriesOutsideTheEC decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:TurnoverFromTaxedSuppliesFromCountriesOutsideTheEC>
                <bd-i:TurnoverFromTaxedSuppliesFromCountriesWithinTheEC decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:TurnoverFromTaxedSuppliesFromCountriesWithinTheEC>
                <bd-i:TurnoverSuppliesServicesByWhichVATTaxationIsTransferred decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:TurnoverSuppliesServicesByWhichVATTaxationIsTransferred>
                <bd-i:ValueAddedTaxAmountTotalNew decimals="INF" contextRef="Msg" unitRef="EUR">262</bd-i:ValueAddedTaxAmountTotalNew>
                <bd-i:ValueAddedTaxAmountTotalOld decimals="INF" contextRef="Msg" unitRef="EUR">210</bd-i:ValueAddedTaxAmountTotalOld>
                <bd-i:ValueAddedTaxOnInput decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:ValueAddedTaxOnInput>
                <bd-i:ValueAddedTaxOnSuppliesFromCountriesOutsideTheEC decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:ValueAddedTaxOnSuppliesFromCountriesOutsideTheEC>
                <bd-i:ValueAddedTaxOnSuppliesFromCountriesWithinTheEC decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:ValueAddedTaxOnSuppliesFromCountriesWithinTheEC>
                <bd-i:ValueAddedTaxOwed decimals="INF" contextRef="Msg" unitRef="EUR">262</bd-i:ValueAddedTaxOwed>
                <bd-i:ValueAddedTaxPrivateUse decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:ValueAddedTaxPrivateUse>
                <bd-i:ValueAddedTaxSuppliesServicesByWhichVATTaxationIsTransferred decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:ValueAddedTaxSuppliesServicesByWhichVATTaxationIsTransferred>
                <bd-i:ValueAddedTaxSuppliesServicesGeneralTariff decimals="INF" contextRef="Msg" unitRef="EUR">262</bd-i:ValueAddedTaxSuppliesServicesGeneralTariff>
                <bd-i:ValueAddedTaxSuppliesServicesOtherRates decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:ValueAddedTaxSuppliesServicesOtherRates>
                <bd-i:ValueAddedTaxSuppliesServicesReducedTariff decimals="INF" contextRef="Msg" unitRef="EUR">0</bd-i:ValueAddedTaxSuppliesServicesReducedTariff>
                <bd-i:ValueAddedTaxToBePaidAdditionalToBePaidBack decimals="INF" contextRef="Msg" unitRef="EUR">52</bd-i:ValueAddedTaxToBePaidAdditionalToBePaidBack>
            </xbrli:xbrl>
        ''')
        self.assertXmlTreeEqual(generated_xbrl, expected_xbrl)

        with (
            patch.object(self.env.registry['account.return'], '_proceed_with_submission'),
            patch.object(
                self.env.registry['l10n_nl_reports.sbr.tax.report.wizard'],
                '_call_iap_proxy',
                return_value={'kenmerk': 'test-kenmerk', 'access_token': 'test-access-token'},
            ) as call_iap_proxy,
        ):
            wizard.send_xbrl()
        self.assertEqual(call_iap_proxy.call_args.args[1]['report_type'], 'tax_correction')
        status_service = self.env['l10n_nl_reports.sbr.status.service'].search([
            ('account_return_id', '=', april_suppletie_return.id),
        ])
        self.assertEqual(status_service.kenmerk, 'test-kenmerk')
        self.assertEqual(status_service.access_token, 'test-access-token')

    def test_xbrl_identifier(self):
        report = self.env.ref('l10n_nl.tax_report')
        date_from = fields.Date.from_string('2026-02-01')
        date_to = fields.Date.from_string('2026-02-28')

        representative = self.env['res.partner'].create({
            'name': 'Fidu NL',
            'country_id': self.env.ref('base.nl').id,
            'vat': 'NL123456782B90',
        })
        self.env.company.account_representative_id = representative

        # Ensure the identifier comes from the selected VAT source, not from the override field.
        self.env.company.l10n_nl_sbr_ob_nummer = False

        def _get_msg_identifier(options):
            wizard = self.env['l10n_nl_reports.sbr.tax.report.wizard'] \
                .with_context(default_date_from=date_from, default_date_to=date_to, options=options) \
                .create({})
            wizard.action_download_xbrl_file()
            generated_xbrl = self.get_xml_tree_from_string(self.env['l10n_nl_reports.tax.report.handler'].export_tax_report_to_xbrl(options).get('file_content'))
            identifier = generated_xbrl.xpath("//*[local-name()='context' and @id='Msg']/*[local-name()='entity']/*[local-name()='identifier']/text()")
            return identifier[0] if identifier else ''

        # Case 1: company VAT.
        self.env.company.vat = 'NL123456782B90'
        options = self._generate_options(report, date_from, date_to)
        self.assertEqual(_get_msg_identifier(options), '123456782B90')

        # Case 2: fiscal unit VAT.
        company_2 = self.company_data_2['company']
        company_2.currency_id = self.env.company.currency_id
        tax_unit = self.env['account.tax.unit'].create({
            'name': 'NL Tax Unit',
            'country_id': self.env.ref('base.nl').id,
            'vat': 'NL123456782B91',
            'company_ids': [(6, 0, (self.env.company + company_2).ids)],
            'main_company_id': self.env.company.id,
        })
        options = self._generate_options(report, date_from, date_to)
        options['tax_unit'] = tax_unit.id
        self.assertEqual(_get_msg_identifier(options), '123456782B91')

        # Case 2b: Tax Unit VAT must take precedence over the company's ob_nummer.
        self.env.company.l10n_nl_sbr_ob_nummer = '987654321B12'
        options = self._generate_options(report, date_from, date_to)
        options['tax_unit'] = tax_unit.id
        self.assertEqual(_get_msg_identifier(options), '123456782B91')
        self.env.company.l10n_nl_sbr_ob_nummer = False

        # Case 3: no VAT should block export.
        self.env.company.vat = False
        options = self._generate_options(report, date_from, date_to)
        options['tax_unit'] = 'company_only'
        with self.assertRaises(RedirectWarning):
            _get_msg_identifier(options)


@tagged('external_l10n', 'post_install', '-at_install', '-standard', 'external')
@skipIf(not os.getenv("NL_SBR_CERT"), "No SBR certificate")
class TestNlSBRFlow(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('nl')
    def setUpClass(cls):
        super().setUpClass()

        cls.env.company.write({
            'vat': 'NL123456782B90',
            'l10n_nl_sbr_ob_nummer': '987654321B09',
        })

        cls.NL_SBR_CERT = os.getenv("NL_SBR_CERT")
        cls.NL_SBR_PWD = os.getenv("NL_SBR_PWD")

    def test_sbr_flow(self):
        certificate = self.env['certificate.certificate'].create({
            'name': 'SBR NL certificate',
            'content': self.NL_SBR_CERT,
            'pkcs12_password': self.NL_SBR_PWD,
            'company_id': self.env.company.id,
        })
        self.assertTrue(certificate.private_key_id)
        self.env.company.l10n_nl_reports_sbr_cert_id = certificate
        self.env['ir.config_parameter'].sudo().set_str('l10n_nl_reports.sbr_mode', 'test')

        date_from = fields.Date.from_string('2019-01-01')
        date_to = fields.Date.from_string('2019-12-31')
        report = self.env.ref('l10n_nl.tax_report')
        options = self._generate_options(report, date_from, date_to)

        wizard = self.env['l10n_nl_reports.sbr.tax.report.wizard']\
            .with_context(default_date_from=date_from, default_date_to=date_to, options=options)\
            .create({})
        res = wizard.send_xbrl()
        self.assertTrue(res)
