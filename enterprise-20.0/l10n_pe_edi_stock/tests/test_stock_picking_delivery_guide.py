# -*- coding: utf-8 -*-
from datetime import datetime
from dateutil.relativedelta import relativedelta
from unittest.mock import patch

from odoo.addons.l10n_pe_edi.tests.common import TestPeEdiCommon
from odoo.addons.l10n_pe_edi_stock.models.stock_picking import StockPicking
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPEDeliveryGuideCommon(TestPeEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.new_wh = cls.env['stock.warehouse'].create({
            'name': 'New Warehouse',
            'reception_steps': 'one_step',
            'delivery_steps': 'ship_only',
            'code': 'NWH'
        })
        cls.dest_wh_partner = cls.env['res.partner'].create({
            'name': 'Destination Branch',
            'street': 'Av. Destination 100',
            'l10n_pe_district': cls.env.ref('l10n_pe.district_pe_030102').id,
        })
        cls.dest_wh = cls.env['stock.warehouse'].create({
            'name': 'Destination Warehouse',
            'reception_steps': 'one_step',
            'delivery_steps': 'ship_only',
            'code': 'DWH',
            'partner_id': cls.dest_wh_partner.id,
        })

        cls.customer_location = cls.env.ref('stock.stock_location_customers')

        cls.productA = cls.env['product.product'].create({
            'name': 'Product A',
            'is_storable': True,
            'unspsc_code_id': cls.env.ref('product_unspsc.unspsc_code_01010101').id,
            'weight': 1,
            'barcode': '123456789',
        })

        cls.certificate.write({
            'date_start': datetime.today() - relativedelta(years=1),
            'date_end': datetime.today() + relativedelta(years=1),
        })

        cls.company_data['company'].l10n_pe_edi_stock_client_id = "Company SUNAT ID"
        cls.company_data['company'].partner_id.l10n_pe_district = cls.env.ref('l10n_pe.district_pe_030101')
        cls.company_data['company'].partner_id.street = 'Rocafort 314'

        cls.partner_a = cls.env['res.partner'].create({
            'name': 'Partner A',
            'street_number': '728',
            'street_name': 'Street Calle',
            'city': 'Arteaga',
            'country_id': cls.env.ref('base.pe').id,
            'state_id': cls.env.ref('base.state_pe_15').id,
            'l10n_pe_district': cls.env.ref('l10n_pe.district_pe_030101').id,
            'zip': '25350',
            'vat': '20100105862',
        })

        cls.operator_luigys = cls.env['res.partner'].create({
            'name': "Luigys Toro",
            'additional_identifiers': {'PE_DNI': '70025425'},
            'street': "JESUS VALDES SANCHEZ 728",
            'city': "Chorrillos",
            'country_id': cls.env.ref('base.pe').id,
            'state_id': cls.env.ref('base.state_pe_15').id,
            'l10n_pe_district': cls.env.ref('l10n_pe.district_pe_030101').id,
            'zip': "25350",
            'phone': "+51 912 345 677",
            'l10n_pe_edi_operator_license': "Q40723053",
        })

        cls.vehicle_luigys = cls.env['l10n_pe_edi.vehicle'].create({
            'name': 'PE TRUCK',
            'license_plate': 'ABC123',
            'operator_id':  cls.operator_luigys.id,
        })

        cls.picking = cls._create_pe_picking(
            picking_type_id=cls.new_wh.out_type_id.id,
            location_id=cls.new_wh.lot_stock_id.id,
            location_dest_id=cls.customer_location.id,
            partner_id=cls.partner_a.id,
        )
        cls.internal_picking = cls._create_pe_picking(
            picking_type_id=cls.new_wh.int_type_id.id,
            location_id=cls.new_wh.lot_stock_id.id,
            location_dest_id=cls.dest_wh.lot_stock_id.id,
        )

    @classmethod
    def _create_pe_picking(cls, **picking_vals):
        picking_vals = {
            'l10n_pe_edi_transport_type': '02',
            'l10n_pe_edi_operator_id': cls.operator_luigys.id,
            'l10n_pe_edi_departure_start_date': datetime.today(),
            'state': 'draft',
            'l10n_pe_edi_vehicle_id': cls.vehicle_luigys.id,
            **picking_vals,
        }
        picking = cls.env['stock.picking'].create(picking_vals)
        cls.env['stock.move'].create({
            'product_id': cls.productA.id,
            'product_uom_qty': 10,
            'uom_id': cls.productA.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
            'state': 'confirmed',
            'description_picking': cls.productA.name,
        })
        cls.env['stock.quant']._update_available_quantity(cls.productA, picking.location_id, 10.0)
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids[0].move_line_ids[0].quantity = 10
        picking.move_ids[0].picked = True
        picking._action_done()
        return picking

    def test_generate_delivery_guide(self):
        """ Check the XML in the test delivery is correctly generated """
        self.picking.l10n_latam_document_number = "T001-00000001"
        ubl = self.picking._l10n_pe_edi_create_delivery_guide()
        expected_document = '''
<DespatchAdvice
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:DespatchAdvice-2"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:CustomizationID>2.0</cbc:CustomizationID>
    <cbc:ID>___ignore___</cbc:ID>
    <cbc:IssueDate>___ignore___</cbc:IssueDate>
    <cbc:IssueTime>___ignore___</cbc:IssueTime>
    <cbc:DespatchAdviceTypeCode listAgencyName="PE:SUNAT" listName="Tipo de Documento" listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01">09</cbc:DespatchAdviceTypeCode>
    <cbc:Note>Guía</cbc:Note>
    <cac:DespatchSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID schemeName="Documento de Identidad" schemeAgencyName="PE:SUNAT" schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06" schemeID="6">20557912879</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName>company_1_data</cbc:RegistrationName>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:DespatchSupplierParty>
    <cac:DeliveryCustomerParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID schemeName="Documento de Identidad" schemeAgencyName="PE:SUNAT" schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06" schemeID="6">20100105862</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName>Partner A</cbc:RegistrationName>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:DeliveryCustomerParty>
    <cac:Shipment>
        <cbc:ID>SUNAT_Envio</cbc:ID>
        <cbc:HandlingCode listAgencyName="PE:SUNAT" listName="Motivo de traslado" listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo20">01</cbc:HandlingCode>
        <cbc:HandlingInstructions>Sale</cbc:HandlingInstructions>
        <cbc:GrossWeightMeasure unitCode="KGM">10.000</cbc:GrossWeightMeasure>
        <cac:ShipmentStage>
            <cbc:TransportModeCode listName="Modalidad de traslado" listAgencyName="PE:SUNAT" listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo18">02</cbc:TransportModeCode>
            <cac:TransitPeriod><cbc:StartDate>___ignore___</cbc:StartDate></cac:TransitPeriod>
            <cac:CarrierParty>
               <cac:PartyLegalEntity>
                   <cbc:CompanyID></cbc:CompanyID>
               </cac:PartyLegalEntity>
                   <cac:AgentParty>
                        <cac:PartyLegalEntity>
                            <cbc:CompanyID schemeName="Entidad Autorizadora" schemeAgencyName="PE:SUNAT" schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogoD37"></cbc:CompanyID>
                        </cac:PartyLegalEntity>
                   </cac:AgentParty>
            </cac:CarrierParty>
            <cac:DriverPerson>
                <cbc:ID schemeName="Documento de Identidad" schemeAgencyName="PE:SUNAT" schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06" schemeID="1">70025425</cbc:ID>
                <cbc:FirstName>Luigys Toro</cbc:FirstName>
                <cbc:FamilyName>Luigys Toro</cbc:FamilyName>
                <cbc:JobTitle>Principal</cbc:JobTitle>
                <cac:IdentityDocumentReference>
                    <cbc:ID>Q40723053</cbc:ID>
                </cac:IdentityDocumentReference>
            </cac:DriverPerson>
        </cac:ShipmentStage>
        <cac:Delivery>
            <cac:DeliveryAddress>
                <cbc:ID schemeName="Ubigeos" schemeAgencyName="PE:INEI">030101</cbc:ID>
                <cbc:AddressTypeCode listAgencyName="PE:SUNAT" listName="Establecimientos anexos" listID="20100105862">0</cbc:AddressTypeCode>
                <cac:AddressLine>
                    <cbc:Line>Street Calle 728 Abancay Arteaga Lima</cbc:Line>
                </cac:AddressLine>
            </cac:DeliveryAddress>
            <cac:Despatch>
                <cac:DespatchAddress>
                    <cbc:ID schemeName="Ubigeos" schemeAgencyName="PE:INEI">030101</cbc:ID>
                    <cbc:AddressTypeCode listAgencyName="PE:SUNAT" listName="Establecimientos anexos" listID="20557912879">0</cbc:AddressTypeCode>
                    <cac:AddressLine>
                        <cbc:Line>Rocafort 314 Abancay  </cbc:Line>
                    </cac:AddressLine>
                </cac:DespatchAddress>
            </cac:Despatch>
        </cac:Delivery>
        <cac:TransportHandlingUnit>
            <cac:TransportEquipment>
                <cbc:ID>ABC123</cbc:ID>
                <cac:ShipmentDocumentReference>
                    <cbc:ID schemeName="Entidad Autorizadora" schemeAgencyName="PE:SUNAT"></cbc:ID>
                </cac:ShipmentDocumentReference>
            </cac:TransportEquipment>
        </cac:TransportHandlingUnit>
    </cac:Shipment>
    <cac:DespatchLine>
        <cbc:ID>1</cbc:ID>
        <cbc:DeliveredQuantity unitCodeListID="UN/ECE rec 20" unitCodeListAgencyName="United Nations Economic Commission for Europe" unitCode="NIU">10.0000000000</cbc:DeliveredQuantity>
        <cac:OrderLineReference>
            <cbc:LineID>1</cbc:LineID>
        </cac:OrderLineReference>
        <cac:Item>
            <cbc:Description>Product A</cbc:Description>
            <cac:SellersItemIdentification>
                <cbc:ID>123456789</cbc:ID>
            </cac:SellersItemIdentification>
            <cac:CommodityClassification>
                <cbc:ItemClassificationCode listID="UNSPSC" listAgencyName="GS1 US" listName="Item Classification">01010101</cbc:ItemClassificationCode>
            </cac:CommodityClassification>
            <cac:AdditionalItemProperty>
                <cbc:Name>Indicador de bien regulado por SUNAT</cbc:Name>
                <cbc:NameCode listAgencyName="PE:SUNAT" listName="Propiedad del item" listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo55">123456789</cbc:NameCode>
                <cbc:Value>0</cbc:Value>
            </cac:AdditionalItemProperty>
        </cac:Item>
    </cac:DespatchLine>
</DespatchAdvice>
        '''
        current_etree = self.get_xml_tree_from_string(ubl)
        expected_etree = self.get_xml_tree_from_string(expected_document)
        self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_generate_internal_delivery_guide(self):
        """ Check the XML in the test delivery is correctly generated """
        picking = self.internal_picking
        picking.l10n_latam_document_number = "T001-00000001"
        picking._check_company()
        picking._l10n_pe_edi_check_required_data()
        ubl = picking._l10n_pe_edi_create_delivery_guide()
        expected_document = '''
<DespatchAdvice
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:DespatchAdvice-2"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:CustomizationID>2.0</cbc:CustomizationID>
    <cbc:ID>___ignore___</cbc:ID>
    <cbc:IssueDate>___ignore___</cbc:IssueDate>
    <cbc:IssueTime>___ignore___</cbc:IssueTime>
    <cbc:DespatchAdviceTypeCode listAgencyName="PE:SUNAT" listName="Tipo de Documento" listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01">09</cbc:DespatchAdviceTypeCode>
    <cbc:Note>Guía</cbc:Note>
    <cac:DespatchSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID schemeName="Documento de Identidad" schemeAgencyName="PE:SUNAT" schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06" schemeID="6">20557912879</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName>company_1_data</cbc:RegistrationName>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:DespatchSupplierParty>
    <cac:DeliveryCustomerParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID schemeName="Documento de Identidad" schemeAgencyName="PE:SUNAT" schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06" schemeID="6">20557912879</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName>company_1_data</cbc:RegistrationName>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:DeliveryCustomerParty>
    <cac:Shipment>
        <cbc:ID>SUNAT_Envio</cbc:ID>
        <cbc:HandlingCode listAgencyName="PE:SUNAT" listName="Motivo de traslado" listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo20">04</cbc:HandlingCode>
        <cbc:HandlingInstructions>Transfer between establishments of the same company</cbc:HandlingInstructions>
        <cbc:GrossWeightMeasure unitCode="KGM">10.000</cbc:GrossWeightMeasure>
        <cac:ShipmentStage>
            <cbc:TransportModeCode listName="Modalidad de traslado" listAgencyName="PE:SUNAT" listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo18">02</cbc:TransportModeCode>
            <cac:TransitPeriod><cbc:StartDate>___ignore___</cbc:StartDate></cac:TransitPeriod>
            <cac:CarrierParty>
               <cac:PartyLegalEntity>
                   <cbc:CompanyID></cbc:CompanyID>
               </cac:PartyLegalEntity>
                   <cac:AgentParty>
                        <cac:PartyLegalEntity>
                            <cbc:CompanyID schemeName="Entidad Autorizadora" schemeAgencyName="PE:SUNAT" schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogoD37"></cbc:CompanyID>
                        </cac:PartyLegalEntity>
                   </cac:AgentParty>
            </cac:CarrierParty>
            <cac:DriverPerson>
                <cbc:ID schemeName="Documento de Identidad" schemeAgencyName="PE:SUNAT" schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06" schemeID="1">70025425</cbc:ID>
                <cbc:FirstName>Luigys Toro</cbc:FirstName>
                <cbc:FamilyName>Luigys Toro</cbc:FamilyName>
                <cbc:JobTitle>Principal</cbc:JobTitle>
                <cac:IdentityDocumentReference>
                    <cbc:ID>Q40723053</cbc:ID>
                </cac:IdentityDocumentReference>
            </cac:DriverPerson>
        </cac:ShipmentStage>
        <cac:Delivery>
            <cac:DeliveryAddress>
                <cbc:ID schemeName="Ubigeos" schemeAgencyName="PE:INEI">030102</cbc:ID>
                <cbc:AddressTypeCode listAgencyName="PE:SUNAT" listName="Establecimientos anexos" listID="20557912879">0</cbc:AddressTypeCode>
                <cac:AddressLine>
                    <cbc:Line>Av. Destination 100 Chacoche  </cbc:Line>
                </cac:AddressLine>
            </cac:DeliveryAddress>
            <cac:Despatch>
                <cac:DespatchAddress>
                    <cbc:ID schemeName="Ubigeos" schemeAgencyName="PE:INEI">030101</cbc:ID>
                    <cbc:AddressTypeCode listAgencyName="PE:SUNAT" listName="Establecimientos anexos" listID="20557912879">0</cbc:AddressTypeCode>
                    <cac:AddressLine>
                        <cbc:Line>Rocafort 314 Abancay  </cbc:Line>
                    </cac:AddressLine>
                </cac:DespatchAddress>
            </cac:Despatch>
        </cac:Delivery>
        <cac:TransportHandlingUnit>
            <cac:TransportEquipment>
                <cbc:ID>ABC123</cbc:ID>
                <cac:ShipmentDocumentReference>
                    <cbc:ID schemeName="Entidad Autorizadora" schemeAgencyName="PE:SUNAT"></cbc:ID>
                </cac:ShipmentDocumentReference>
            </cac:TransportEquipment>
        </cac:TransportHandlingUnit>
    </cac:Shipment>
    <cac:DespatchLine>
        <cbc:ID>1</cbc:ID>
        <cbc:DeliveredQuantity unitCodeListID="UN/ECE rec 20" unitCodeListAgencyName="United Nations Economic Commission for Europe" unitCode="NIU">10.0000000000</cbc:DeliveredQuantity>
        <cac:OrderLineReference>
            <cbc:LineID>1</cbc:LineID>
        </cac:OrderLineReference>
        <cac:Item>
            <cbc:Description>Product A</cbc:Description>
            <cac:SellersItemIdentification>
                <cbc:ID>123456789</cbc:ID>
            </cac:SellersItemIdentification>
            <cac:CommodityClassification>
                <cbc:ItemClassificationCode listID="UNSPSC" listAgencyName="GS1 US" listName="Item Classification">01010101</cbc:ItemClassificationCode>
            </cac:CommodityClassification>
            <cac:AdditionalItemProperty>
                <cbc:Name>Indicador de bien regulado por SUNAT</cbc:Name>
                <cbc:NameCode listAgencyName="PE:SUNAT" listName="Propiedad del item" listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo55">123456789</cbc:NameCode>
                <cbc:Value>0</cbc:Value>
            </cac:AdditionalItemProperty>
        </cac:Item>
    </cac:DespatchLine>
</DespatchAdvice>
        '''
        current_etree = self.get_xml_tree_from_string(ubl)
        expected_etree = self.get_xml_tree_from_string(expected_document)
        self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_loading_transport_event_only_public_transport(self):
        """The 'Fecha de entrega de bienes al transportista' (LoadingTransportEvent)
        is required by SUNAT only when the transport modality is public ('01');
        emitting it for private transport ('02') would diverge from the
        validation rules (R. S. N° 108-2026/SUNAT, error 3617)."""
        self.picking.l10n_latam_document_number = "T001-00000001"

        self.picking.l10n_pe_edi_transport_type = '02'
        private_ubl = self.picking._l10n_pe_edi_create_delivery_guide()
        self.assertNotIn(b'LoadingTransportEvent', private_ubl)

        self.picking.l10n_pe_edi_transport_type = '01'
        public_ubl = self.picking._l10n_pe_edi_create_delivery_guide()
        self.assertIn(b'LoadingTransportEvent', public_ubl)
        # The UBL 2.1 ShipmentStage sequence requires LoadingTransportEvent to
        # come after CarrierParty; emitting it before makes SUNAT's schema
        # validation reject the document (cvc-complex-type at cac:CarrierParty).
        self.assertLess(
            public_ubl.index(b'CarrierParty'),
            public_ubl.index(b'LoadingTransportEvent'),
            "LoadingTransportEvent must follow CarrierParty in the UBL sequence",
        )

    def test_outdated_module_error_message(self):
        """When SUNAT rejects with code 3617 (missing 'Fecha de entrega de bienes al
        transportista'), the installed module is out of date. Store an actionable
        message telling the user to update instead of the raw SUNAT rejection."""
        self.picking.l10n_latam_document_number = "T001-00000001"
        sunat_response = {
            'error': 'SUNAT returned an error code. Details: 3617: ...',
            'error_reason': 'outdated_module',
            'error_code': '3617',
        }
        with patch.object(StockPicking, '_l10n_pe_edi_sign', return_value=sunat_response):
            self.picking.action_send_delivery_guide()

        self.assertNotEqual(self.picking.l10n_pe_edi_status, 'sent')
        self.assertIn('l10n_pe_edi_stock', self.picking.l10n_pe_edi_error)
        self.assertIn('3617', self.picking.l10n_pe_edi_error)

    def test_send_delivery_guide(self):
        """Ensure that delivery guide is generated and sent to the SUNAT."""
        self.picking.l10n_latam_document_number = 'T001-%s' % datetime.now().strftime('%H%M%S')

        html = self.env['ir.actions.report']._render_qweb_html('stock.report_deliveryslip', self.picking.ids)[0]
        self.assertNotIn(b'Sender Electronic Delivery Guide', html)

        cdr = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<ar:ApplicationResponse'
            b' xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"'
            b' xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"'
            b' xmlns:ar="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2">'
            b'<cac:DocumentResponse>'
            b'<cac:DocumentReference>'
            b'<cbc:DocumentDescription>TEST_QR_VALUE</cbc:DocumentDescription>'
            b'</cac:DocumentReference>'
            b'</cac:DocumentResponse>'
            b'</ar:ApplicationResponse>'
        )
        with patch.object(StockPicking, '_l10n_pe_edi_sign', lambda *_args, **_kwargs: {'cdr': cdr}):
            self.picking.action_send_delivery_guide()
        self.assertEqual(self.picking.l10n_pe_edi_status, 'sent', self.picking.l10n_pe_edi_error)

        html = self.env['ir.actions.report']._render_qweb_html('stock.report_deliveryslip', self.picking.ids)[0]
        self.assertIn(b'TEST_QR_VALUE', html)
        self.assertIn(b'Sender Electronic Delivery Guide', html)

    def test_address_type_code_omitted_for_reason_18(self):
        """ The AddressTypeCode in the DeliveryAddress must be omitted when the transfer reason is 18."""

        # Try transfer reason 18
        self.picking.l10n_latam_document_number = "T001-00000002"
        self.picking.l10n_pe_edi_reason_for_transfer = '18'
        ubl_reason_18 = self.picking._l10n_pe_edi_create_delivery_guide()
        tree_reason_18 = self.get_xml_tree_from_string(ubl_reason_18)
        namespaces = {
            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        }
        delivery_address_type_code_18 = tree_reason_18.xpath('//cac:Delivery/cac:DeliveryAddress/cbc:AddressTypeCode', namespaces=namespaces)
        self.assertFalse(delivery_address_type_code_18)

        # Try another transfer reason (ex. 01)
        self.picking.l10n_pe_edi_reason_for_transfer = '01'
        ubl_reason_01 = self.picking._l10n_pe_edi_create_delivery_guide()
        tree_reason_01 = self.get_xml_tree_from_string(ubl_reason_01)
        delivery_address_type_code_01 = tree_reason_01.xpath('//cac:Delivery/cac:DeliveryAddress/cbc:AddressTypeCode', namespaces=namespaces)
        self.assertTrue(delivery_address_type_code_01)
