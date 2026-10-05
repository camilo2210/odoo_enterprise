from freezegun import freeze_time

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools import date_utils

from odoo.addons.l10n_it_reports.tests.test_tax_report import TestItalianTaxReport


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestItalianTaxReportXmlExport(TestItalianTaxReport):

    _test_user_groups = None  # FIXME list needed groups

    def _create_invoice_for_reported_period(self):
        """Helper method to create and post invoices in each month of the reported quarter. Depends on today's date (use freeze_time)."""
        invoices = self.env['account.move'].create([{
            'move_type': 'in_invoice',
            'partner_id': self.l10n_it_tax_report_partner.id,
            'date': date,
            'invoice_date': date,
            'invoice_line_ids': [
                Command.create({
                    'name': 'Product A',
                    'account_id': self.company_data['default_account_revenue'].id,
                    'price_unit': 5 * (10 ** i),
                    'quantity': 10,
                    'tax_ids': self.tax_4a,
                }),
            ],
        } for i, date in enumerate(list(date_utils.date_range(*date_utils.get_quarter(fields.Date.today()))))])
        invoices.action_post()

    def _get_tax_return_xml_document(self, tax_return, wizard_data={}):
        with self.allow_pdf_render():
            action_data = tax_return.action_submit()
        if action_data and action_data.get('tag', '') != 'display_notification':
            self.assertTrue(action_data and 'res_model' in action_data, "No export wizard was returned for the period")
            wizard_context = {**action_data.get('context', {}), 'active_id': tax_return.id}
            wizard = self.env[action_data['res_model']].with_context(wizard_context).create(wizard_data)
            wizard.action_generate_export()

            xml_file = tax_return.attachment_ids.filtered(lambda a: a.mimetype == 'application/xml')
            return xml_file
        return False

    def test_all_settings_tags_in_xml(self):
        self.env.company.account_return_periodicity = 'monthly'
        self.env.company.l10n_it_codice_fiscale = 12345670546

        report = self.env['account.return'].create({
            'name': "Test Return",
            'date_from': '2025-03-01',
            'date_to': '2025-03-31',
            'type_id': self.env.ref('l10n_it_reports.it_tax_return_type').id,
            'company_id': self.env.company.id,
        })
        with self.allow_pdf_render():
            report.action_validate()

        wizard_data = {
            "declarant_fiscal_code": (self.env.company.account_representative_id or self.env.company).l10n_it_codice_fiscale,
            "declarant_role_code": '1',
            "id_sistema": '12345678901',
            "taxpayer_code": self.env.company.l10n_it_codice_fiscale,
            "parent_company_vat_number": '12345678901',
            "company_code": "".join([char for char in self.env.company.vat if char.isdigit()]),
            "intermediary_code": '12345678901',
            "submission_commitment": '1',
            "commitment_date": fields.Date.today(),
            "method": '1',
        }
        xml = self._get_tax_return_xml_document(report, wizard_data=wizard_data)
        self.assertTrue(xml)

        # The following values can only be edited by inputting their value in the wizard.
        file_content = bytes(xml['raw'])
        decoded_file_content = file_content.decode()

        settings_tags = [
            "Intestazione",
            "CodiceFornitura",
            "CodiceFiscaleDichiarante",
            "CodiceCarica",
            "IdSistema",
            "Frontespizio",
            "CodiceFiscale",
            "AnnoImposta",
            "PartitaIVA",
            "PIVAControllante",
            "UltimoMese",
            "CFDichiarante",
            "CodiceCaricaDichiarante",
            "CodiceFiscaleSocieta",
            "FirmaDichiarazione",
            "CFIntermediario",
            "ImpegnoPresentazione",
            "DataImpegno",
            "FirmaIntermediario",
            "FlagConferma",
            "IdentificativoProdSoftware",
        ]

        for tag in settings_tags:
            self.assertIn(f"<iv:{tag}>", decoded_file_content, f"Tag <iv:{tag}> is missing in the XML export.")

    @freeze_time('2025-06-01')
    def test_xml_monthly_export(self):
        self._create_invoice_for_reported_period()
        self.env.company.account_return_periodicity = 'monthly'
        self.env.company.l10n_it_codice_fiscale = 12345670546

        april_return, may_return, june_return = self.env['account.return'].create([{
            'name': name,
            'date_from': date_from,
            'date_to': date_to,
            'type_id': self.env.ref('l10n_it_reports.it_tax_return_type').id,
            'company_id': self.env.company.id,
        } for name, date_from, date_to in [
                ('test April return', '2025-04-01', '2025-04-30'),
                ('test May return', '2025-05-01', '2025-05-31'),
                ('test June return', '2025-06-01', '2025-06-30'),
            ]
        ])

        with self.allow_pdf_render():
            april_return.action_validate()
        self.assertFalse(self._get_tax_return_xml_document(april_return))

        with self.allow_pdf_render():
            may_return.action_validate()
        self.assertFalse(self._get_tax_return_xml_document(may_return))

        with self.allow_pdf_render():
            june_return.action_validate()
        xml = self._get_tax_return_xml_document(june_return)
        self.assertTrue(xml, "XML document was not generated for the period")

        file_content = bytes(xml['raw'])
        decoded_file_content = file_content.decode()

        # If the file doesn't contain the three monthly groups, there is no need to test further
        for i, date in enumerate(date_utils.date_range(*date_utils.get_quarter(fields.Date.today()))):
            self.assertIn(f"<iv:NumeroModulo>{i + 1}</iv:NumeroModulo>", decoded_file_content)
            self.assertIn(f"<iv:Mese>{date.month}</iv:Mese>", decoded_file_content)

        expected_xml = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <iv:Fornitura xmlns:iv="urn:www.agenziaentrate.gov.it:specificheTecniche:sco:ivp" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <iv:Intestazione>
                    <iv:CodiceFornitura>IVP18</iv:CodiceFornitura>
                    <iv:CodiceFiscaleDichiarante>12345670546</iv:CodiceFiscaleDichiarante>
                    <iv:CodiceCarica>1</iv:CodiceCarica>
                </iv:Intestazione>
                <iv:Comunicazione identificativo="00001">
                    <iv:Frontespizio>
                        <iv:CodiceFiscale>12345670546</iv:CodiceFiscale>
                        <iv:AnnoImposta>2025</iv:AnnoImposta>
                        <iv:PartitaIVA>78926680725</iv:PartitaIVA>
                        <iv:UltimoMese>5</iv:UltimoMese>
                        <iv:CFDichiarante>12345670546</iv:CFDichiarante>
                        <iv:CodiceCaricaDichiarante>1</iv:CodiceCaricaDichiarante>
                        <iv:CodiceFiscaleSocieta>78926680725</iv:CodiceFiscaleSocieta>
                        <iv:FirmaDichiarazione>1</iv:FirmaDichiarazione>
                        <iv:FlagConferma>1</iv:FlagConferma>
                        <iv:IdentificativoProdSoftware>ODOO S.A.</iv:IdentificativoProdSoftware>
                    </iv:Frontespizio>
                    <iv:DatiContabili>
                        <iv:Modulo>
                            <iv:NumeroModulo>1</iv:NumeroModulo>
                            <iv:Mese>4</iv:Mese>
                            <iv:TotaleOperazioniPassive>50,00</iv:TotaleOperazioniPassive>
                            <iv:IvaDetratta>2,00</iv:IvaDetratta>
                            <iv:IvaCredito>2,00</iv:IvaCredito>
                            <iv:ImportoACredito>2,00</iv:ImportoACredito>
                        </iv:Modulo>
                        <iv:Modulo>
                            <iv:NumeroModulo>2</iv:NumeroModulo>
                            <iv:Mese>5</iv:Mese>
                            <iv:TotaleOperazioniPassive>500,00</iv:TotaleOperazioniPassive>
                            <iv:IvaDetratta>20,00</iv:IvaDetratta>
                            <iv:IvaCredito>20,00</iv:IvaCredito>
                            <iv:CreditoPeriodoPrecedente>2,00</iv:CreditoPeriodoPrecedente>
                            <iv:ImportoACredito>22,00</iv:ImportoACredito>
                        </iv:Modulo>
                        <iv:Modulo>
                            <iv:NumeroModulo>3</iv:NumeroModulo>
                            <iv:Mese>6</iv:Mese>
                            <iv:TotaleOperazioniPassive>5000,00</iv:TotaleOperazioniPassive>
                            <iv:IvaDetratta>200,00</iv:IvaDetratta>
                            <iv:IvaCredito>200,00</iv:IvaCredito>
                            <iv:CreditoPeriodoPrecedente>22,00</iv:CreditoPeriodoPrecedente>
                            <iv:ImportoACredito>222,00</iv:ImportoACredito>
                        </iv:Modulo>
                    </iv:DatiContabili>
                </iv:Comunicazione>
            </iv:Fornitura>
        """

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(file_content),
            self.get_xml_tree_from_string(expected_xml),
        )

    @freeze_time('2025-06-01')
    def test_xml_quarterly_export(self):
        self._create_invoice_for_reported_period()
        self.env.company.account_return_periodicity = 'trimester'
        self.env.company.l10n_it_codice_fiscale = 12345670546

        q2_return = self.env['account.return'].create({
            'name': 'test Q2 return',
            'date_from': '2025-04-01',
            'date_to': '2025-06-30',
            'type_id': self.env.ref('l10n_it_reports.it_tax_return_type').id,
            'company_id': self.env.company.id,
        })
        with self.allow_pdf_render():
            q2_return.action_validate()

        xml = self._get_tax_return_xml_document(q2_return)
        self.assertTrue(xml, "XML document was not generated for the period")

        file_content = bytes(xml['raw'])
        decoded_file_content = file_content.decode()

        # If the file doesn't contain a single Trimester group, there is no need to test further
        self.assertIn("<iv:NumeroModulo>1</iv:NumeroModulo>", decoded_file_content)
        self.assertIn(f"<iv:Trimestre>{date_utils.get_quarter_number(fields.Date.today())}</iv:Trimestre>", decoded_file_content)

        expected_xml = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <iv:Fornitura xmlns:iv="urn:www.agenziaentrate.gov.it:specificheTecniche:sco:ivp" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
                <iv:Intestazione>
                    <iv:CodiceFornitura>IVP18</iv:CodiceFornitura>
                    <iv:CodiceFiscaleDichiarante>12345670546</iv:CodiceFiscaleDichiarante>
                    <iv:CodiceCarica>1</iv:CodiceCarica>
                </iv:Intestazione>
                <iv:Comunicazione identificativo="00001">
                    <iv:Frontespizio>
                        <iv:CodiceFiscale>12345670546</iv:CodiceFiscale>
                        <iv:AnnoImposta>2025</iv:AnnoImposta>
                        <iv:PartitaIVA>78926680725</iv:PartitaIVA>
                        <iv:UltimoMese>5</iv:UltimoMese>
                        <iv:CFDichiarante>12345670546</iv:CFDichiarante>
                        <iv:CodiceCaricaDichiarante>1</iv:CodiceCaricaDichiarante>
                        <iv:CodiceFiscaleSocieta>78926680725</iv:CodiceFiscaleSocieta>
                        <iv:FirmaDichiarazione>1</iv:FirmaDichiarazione>
                        <iv:FlagConferma>1</iv:FlagConferma>
                        <iv:IdentificativoProdSoftware>ODOO S.A.</iv:IdentificativoProdSoftware>
                    </iv:Frontespizio>
                    <iv:DatiContabili>
                        <iv:Modulo>
                            <iv:NumeroModulo>1</iv:NumeroModulo>
                            <iv:Trimestre>2</iv:Trimestre>
                            <iv:TotaleOperazioniPassive>5550,00</iv:TotaleOperazioniPassive>
                            <iv:IvaDetratta>222,00</iv:IvaDetratta>
                            <iv:IvaCredito>222,00</iv:IvaCredito>
                            <iv:ImportoACredito>222,00</iv:ImportoACredito>
                        </iv:Modulo>
                    </iv:DatiContabili>
                </iv:Comunicazione>
            </iv:Fornitura>
        """

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(file_content),
            self.get_xml_tree_from_string(expected_xml),
        )
