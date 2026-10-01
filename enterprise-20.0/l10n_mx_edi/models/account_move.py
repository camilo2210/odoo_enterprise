import logging
import re
from collections import defaultdict
from datetime import datetime
from markupsafe import Markup
from lxml import etree

from odoo import api, fields, models, Command
from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document import (
    CANCELLATION_REASON_SELECTION,
    CANCELLATION_REASON_DESCRIPTION,
    CFDI_CODE_TO_TAX_TYPE,
    CFDI_DATE_FORMAT,
    USAGE_SELECTION,
)
from odoo.exceptions import ValidationError, UserError
from odoo.tools import formatLang
from odoo.tools.float_utils import float_round

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ==== CFDI flow fields ====

    l10n_mx_edi_is_cfdi_needed = fields.Boolean(
        compute='_compute_l10n_mx_edi_is_cfdi_needed',
        store=True,
    )
    # The CFDI documents displayed on the invoice.
    # This is a many2many because a payment could pay multiple invoices.
    l10n_mx_edi_invoice_document_ids = fields.Many2many(
        comodel_name='l10n_mx_edi.document',
        relation='l10n_mx_edi_invoice_document_ids_rel',
        column1='invoice_id',
        column2='document_id',
        copy=False,
        readonly=True,
    )
    # The CFDI documents displayed on the payment.
    l10n_mx_edi_payment_document_ids = fields.One2many(
        comodel_name='l10n_mx_edi.document',
        inverse_name='move_id',
        copy=False,
        readonly=True,
    )
    # The CFDI documents for the view.
    l10n_mx_edi_document_ids = fields.One2many(
        comodel_name='l10n_mx_edi.document',
        compute='_compute_l10n_mx_edi_document_ids',
    )
    l10n_mx_edi_cfdi_state = fields.Selection(
        string="CFDI status",
        selection=[
            ('sent', 'Signed'),
            ('cancel_requested', 'Cancel Requested'),
            ('cancel', 'Cancelled'),
            ('received', 'Received'),
            ('global_sent', 'Signed Global'),
            ('global_cancel', 'Cancelled Global'),
        ],
        store=True,
        copy=False,
        tracking=True,
        compute="_compute_l10n_mx_edi_cfdi_state_and_attachment",
    )
    l10n_mx_edi_cfdi_sat_state = fields.Selection(
        string="SAT status",
        selection=[
            ('valid', "Validated"),
            ('cancelled', "Cancelled"),
            ('not_found', "Not Found"),
            ('not_defined', "Not Defined"),
            ('error', "Error"),
        ],
        store=True,
        copy=False,
        tracking=True,
        compute="_compute_l10n_mx_edi_cfdi_state_and_attachment",
    )
    l10n_mx_edi_cfdi_attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        string="CFDI",
        store=True,
        copy=False,
        index=True,
        compute='_compute_l10n_mx_edi_cfdi_state_and_attachment',
    )
    # Technical field indicating if the "Update Payments" button needs to be displayed on invoice view.
    l10n_mx_edi_update_payments_needed = fields.Boolean(compute='_compute_l10n_mx_edi_update_payments_needed')
    # Technical field indicating if the "Update SAT" button needs to be displayed on invoice/payment view.
    l10n_mx_edi_update_sat_needed = fields.Boolean(compute='_compute_l10n_mx_edi_update_sat_needed')
    l10n_mx_edi_post_time = fields.Datetime(
        string="Posted Time",
        readonly=True,
        copy=False,
        help="Keep empty to use the current México central time",
    )
    l10n_mx_edi_usage = fields.Selection(
        selection=USAGE_SELECTION,
        string="Usage",
        readonly=False,
        store=True,
        compute='_compute_l10n_mx_edi_usage',
        tracking=True,
        help="Used in CFDI to express the key to the usage that will gives the receiver to this invoice. This "
             "value is defined by the customer.\nNote: It is not cause for cancellation if the key set is not the usage "
             "that will give the receiver of the document.",
    )
    l10n_mx_edi_cfdi_origin = fields.Char(
        string="CFDI Origin",
        copy=False,
        index='trigram',
        help="In some cases like payments, credit notes, debit notes, invoices re-signed or invoices that are redone "
             "due to payment in advance will need this field filled, the format is:\n"
             "Origin Type|UUID1, UUID2, ...., UUIDn.\n"
             "Where the origin type could be:\n"
             "- 01: Nota de crédito\n"
             "- 02: Nota de débito de los documentos relacionados\n"
             "- 03: Devolución de mercancía sobre facturas o traslados previos\n"
             "- 04: Sustitución de los CFDI previos\n"
             "- 05: Traslados de mercancias facturados previamente\n"
             "- 06: Factura generada por los traslados previos\n"
             "- 07: CFDI por aplicación de anticipo",
    )
    # When cancelling an invoice, the user needs to provide a valid reason to do so to the SAT.
    l10n_mx_edi_invoice_cancellation_reason = fields.Selection(
        selection=CANCELLATION_REASON_SELECTION,
        string="Cancellation Reason",
        compute='_compute_l10n_mx_edi_cfdi_state_and_attachment',
        store=True,
        help=CANCELLATION_REASON_DESCRIPTION,
    )
    # Indicate the journal entry substituting the current cancelled one.
    # In other words, this is the reason why the current journal entry is cancelled.
    l10n_mx_edi_cfdi_cancel_id = fields.Many2one(
        comodel_name='account.move',
        string="Substituted By",
        compute='_compute_l10n_mx_edi_cfdi_cancel_id',
        index='btree_not_null',
    )

    # ==== CFDI certificate fields ====
    l10n_mx_edi_certificate_id = fields.Many2one(
        comodel_name='certificate.certificate',
        domain=[('is_valid', "=", True)],
        string="Source Certificate")
    l10n_mx_edi_cer_source = fields.Char(
        string='Certificate Source',
        help="Used in CFDI like attribute derived from the exception of certificates of Origin of the "
             "Free Trade Agreements that Mexico has celebrated with several countries. If it has a value, it will "
             "indicate that it serves as certificate of origin and this value will be set in the CFDI node "
             "'NumCertificadoOrigen'.")

    # ==== CFDI attachment fields ====
    l10n_mx_edi_cfdi_uuid = fields.Char(
        string="Fiscal Folio",
        compute='_compute_l10n_mx_edi_cfdi_uuid',
        copy=False,
        store=True,
        tracking=True,
        index='btree_not_null',
        help="Folio in electronic invoice, is returned by SAT when send to stamp.",
    )
    l10n_mx_edi_cfdi_supplier_rfc = fields.Char(
        string="Supplier RFC",
        compute='_compute_cfdi_values',
        help="The supplier tax identification number.",
    )
    l10n_mx_edi_cfdi_customer_rfc = fields.Char(
        string="Customer RFC",
        compute='_compute_cfdi_values',
        help="The customer tax identification number.",
    )
    l10n_mx_edi_cfdi_amount = fields.Monetary(
        string="Total Amount",
        compute='_compute_cfdi_values',
        help="The total amount reported on the cfdi.",
    )

    # ==== Other fields ====
    l10n_mx_edi_payment_method_id = fields.Many2one(
        comodel_name='l10n_mx_edi.payment.method',
        string="Payment Way",
        compute='_compute_l10n_mx_edi_payment_method_id',
        store=True,
        readonly=False,
        init_storage=lambda model: None,  # avoid MemoryError on large databases
        help="Indicates the way the invoice was/will be paid, where the options could be: "
             "Cash, Nominal Check, Credit Card, etc. Leave empty if unkown and the XML will show 'Unidentified'.",
    )
    # Indicate what kind of payment is expected to pay the current invoice.
    # PUE is for a quick payment close to the invoice date paying completely the invoice.
    # In that case, by default, you don't need to sent the payment to the SAT.
    # PPD means you have either a delay, either multiple partial payments to do.
    # In that case, the payment(s) must be sent to the SAT.
    l10n_mx_edi_payment_policy = fields.Selection(
        string="Payment Policy",
        selection=[('PPD', 'PPD'), ('PUE', 'PUE')],
        compute='_compute_l10n_mx_edi_payment_policy',
        store=True,
        readonly=False,
    )
    # Indicate if you send the invoice to the SAT using 'Publico En General' meaning
    # the customer is unknown by the SAT. This is mainly used when the customer doesn't have
    # a VAT number registered to the SAT.
    l10n_mx_edi_cfdi_to_public = fields.Boolean(
        string="CFDI to public",
        compute='_compute_l10n_mx_edi_cfdi_to_public',
        store=True,
        readonly=False,
        help="Send the CFDI with recipient 'publico en general'",
        tracking=True,
    )
    l10n_mx_edi_addenda_ids = fields.Many2many(
        comodel_name='l10n_mx_edi.addenda',
        string="Addendas & Complementos",
        compute='_compute_l10n_mx_edi_addenda_ids',
        store=True,
        readonly=False,
    )
    l10n_mx_edi_partner_address_complete = fields.Boolean(related="partner_id.l10n_mx_edi_partner_address_complete")
    l10n_mx_edi_show_import_totals_alert = fields.Boolean(copy=False, readonly=True)

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _l10n_mx_edi_is_cfdi_document(self):
        """ Helper to know if the current account.move is eligible for the MX CFDI.

        :return: A boolean.
        """
        self.ensure_one()
        return self.country_code == 'MX' and self.company_currency_id.name == 'MXN'

    def _l10n_mx_edi_is_cfdi_invoice(self):
        """ Helper to know if the current account.move is an invoice or not.

        :return: True if the account.move is an invoice, False otherwise.
        """
        self.ensure_one()
        return self._l10n_mx_edi_is_cfdi_document() and self.is_invoice()

    def _l10n_mx_edi_is_cfdi_bill(self):
        """ Helper to know if the current account.move is vendor bill or not.

        :return: True if the account.move is a vendor bill, False otherwise.
        """
        self.ensure_one()
        return self._l10n_mx_edi_is_cfdi_document() and self.is_purchase_document(include_receipts=True)

    def _l10n_mx_edi_is_cfdi_payment(self):
        """ Helper to know if the current account.move is a payment or not.

        :return: True if the account.move is a payment, False otherwise.
        """
        self.ensure_one()
        return self._l10n_mx_edi_is_cfdi_document() and (self.origin_payment_id or self.statement_line_id)

    def _l10n_mx_edi_cfdi_invoice_append_addendas(self, cfdi_str, addendas):
        """ Helper to handle appending Complementos/Addenda before/after sending the CFDI string.
        --- Format of returned dictionary ---
        {
            <optional> 'error' : <string>,
            <required> 'cfdi'  : <bytes>,
        }
        :param cfdi_str: the CFDI XML string to be appended to
        :param l10n_mx_edi.addenda addendas: all the ``l10n_mx_edi.addenda`` records to be appended
        :return: the new CFDI XML string which have been appended with the addenda_ids
        :rtype: dict[str, str | bytes]
        """
        self.ensure_one()
        decoded_data = addendas._decode_multi_addenda_arch()
        if decoded_data.get('errors'):
            return {'errors': decoded_data['errors'], 'cfdi': cfdi_str}

        xml_node = self.env['l10n_mx_edi.addenda']._get_decoded_xml_node(decoded_data)
        addition_values = {'record': self}
        addition_title = 'Complemento' if xml_node == 'complemento' else 'Addenda'
        cfdi_node = etree.fromstring(cfdi_str)
        # Verify if the Addenda node has already been added,
        # if the node exists it is removed to avoid duplicating it in the CFDI.
        if addition_title == 'Addenda':
            existing_addenda = cfdi_node.find("{*}Addenda")
            if existing_addenda is not None:
                cfdi_node.remove(existing_addenda)

        # Create new Comprobante node with the new namespaces required for the addendas
        new_cfdi_node = etree.Element(
            _tag=cfdi_node.tag,
            attrib=cfdi_node.attrib,
            nsmap=cfdi_node.nsmap | decoded_data['comprobante']['nsmap'],
        )
        previous_complemento_node = cfdi_node.find("{*}Complemento")
        need_update_complemento = xml_node == 'complemento' and previous_complemento_node is not None

        # Copy the Complemento/Addenda node without children; or create new one if it's not created yet
        if need_update_complemento:  # Complemento node already exist
            empty_addition_node = etree.Element(
                _tag=previous_complemento_node.tag,
                attrib=previous_complemento_node.attrib,
                nsmap=previous_complemento_node.nsmap | decoded_data[xml_node]['nsmap'],
            )
        else:  # Complemento/Addenda node has not been created yet; create a new empty node
            new_node_tag = etree.QName('http://www.sat.gob.mx/cfd/%s' % cfdi_node.get('Version')[0], addition_title)
            empty_addition_node = etree.Element(new_node_tag, nsmap={'cfdi': "http://www.sat.gob.mx/cfd/4", **decoded_data[xml_node]['nsmap']})

        # Create the new Complemento/Addenda node XML string
        empty_addition_str = etree.tostring(empty_addition_node, method='c14n').decode('utf-8')
        replacer_str_list = ['>', decoded_data[xml_node]['arch']]
        if need_update_complemento:
            for previous_child in previous_complemento_node.getchildren():  # collect all original XML Complemento children as a string
                replacer_str_list.append(etree.tostring(previous_child).decode('utf-8'))
            cfdi_node.remove(previous_complemento_node)
        replacer_str = ''.join(replacer_str_list)
        new_addition_str = empty_addition_str.replace('>', replacer_str, 1)

        for child_node in cfdi_node.getchildren():  # add all previous children to the new empty CFDI root node
            new_cfdi_node.append(child_node)

        # Create the new CFDI XML node string and manually inject the new Complemento/Addenda XML string
        new_cfdi_str: str = etree.tostring(new_cfdi_node).decode('utf-8')
        new_cfdi_str = new_cfdi_str.replace('</cfdi:Comprobante>', new_addition_str + '</cfdi:Comprobante>', 1)

        # Manually inject schema locations
        if schema_locations_str := decoded_data['comprobante']['schema_locations']:
            new_cfdi_str = new_cfdi_str.replace('xsi:schemaLocation="', f'xsi:schemaLocation="{schema_locations_str} ', 1)

        # Render the new XML with QWeb and return the new XML string
        new_cfdi_arch = self.env['ir.qweb']._render(etree.fromstring(new_cfdi_str), values=addition_values).strip()
        new_cfdi_node = etree.fromstring(new_cfdi_arch)
        new_cfdi = self.env['l10n_mx_edi.document']._convert_xml_to_attachment_data(new_cfdi_node)
        return {'cfdi': new_cfdi}

    def _l10n_mx_edi_cfdi_amount_to_text(self, amount=None):
        """Method to transform a float amount to text words
        E.g. 100 - ONE HUNDRED
        :param amount:      Optional amount value to convert to text.
                            If not set, will use the one of the invoice.
        :returns:           Amount transformed to words mexican format for invoices
        :rtype: str
        """
        self.ensure_one()

        currency_name = self.currency_id.name.upper()

        # M.N. = Moneda Nacional (National Currency)
        # M.E. = Moneda Extranjera (Foreign Currency)
        currency_type = 'M.N' if currency_name == 'MXN' else 'M.E.'

        # Split integer and decimal part
        amount = amount if amount is not None else self.amount_total
        amount_i, amount_d = divmod(amount, 1)
        amount_d = round(amount_d, 2)
        amount_d = int(round(amount_d * 100, 2))

        words = self.currency_id.with_context(lang=self.partner_id.lang).amount_to_text(amount_i).upper()
        return '%(words)s %(amount_d)02d/100 %(currency_type)s' % {
            'words': words,
            'amount_d': amount_d,
            'currency_type': currency_type,
        }

    def _l10n_mx_edi_check_invoices_for_global_invoice(self, origin=None):
        """ Ensure the current records are eligible for the creation of a global invoice.

        :param origin: The origin of the GI when cancelling an existing one.
        """
        failed_invoices = self.filtered(lambda x: x.state != 'posted')
        if failed_invoices:
            invoices_str = ", ".join(invoice.name or '/' for invoice in failed_invoices)
            raise UserError(self.env._("Invoices %s are not posted.", invoices_str))
        if len(self.company_id) != 1 or len(self.journal_id) != 1:
            raise UserError(self.env._("You can only process invoices sharing the same company and journal."))
        if len(self.currency_id) != 1:
            raise UserError(self.env._("You can only process invoices sharing the same currency."))

        refunds = self.reversal_move_ids
        invoices = self | refunds
        failed_invoices = invoices.filtered(lambda x: (
            (
                not origin
                and (
                    not x.l10n_mx_edi_is_cfdi_needed
                    or x.l10n_mx_edi_cfdi_state in ('sent', 'global_sent')
                )
            )
            or (x.move_type == 'out_refund' and x.reversed_entry_id not in self)
        ))
        if failed_invoices:
            invoices_str = ", ".join(failed_invoices.mapped('name'))
            raise UserError(self.env._("Invoices %s are already sent or not eligible for CFDI.", invoices_str))
        return invoices

    @api.model
    def _l10n_mx_edi_write_cfdi_origin(self, code, uuids):
        ''' Format the code and uuids passed as parameter in order to fill the l10n_mx_edi_cfdi_origin field.
        The code corresponds to the following types:
            - 01: Nota de crédito
            - 02: Nota de débito de los documentos relacionados
            - 03: Devolución de mercancía sobre facturas o traslados previos
            - 04: Sustitución de los CFDI previos
            - 05: Traslados de mercancias facturados previamente
            - 06: Factura generada por los traslados previos
            - 07: CFDI por aplicación de anticipo

        The generated string must match the following template:
        <code>|<uuid1>,<uuid2>,...,<uuidn>

        :param code:    A valid code as a string between 01 and 07.
        :param uuids:   A list of uuids returned by the government.
        :return:        A valid string to be put inside the l10n_mx_edi_cfdi_origin field.
        '''
        return '%s|%s' % (code, ','.join(uuids))

    def _l10n_mx_edi_get_extra_invoice_report_values(self):
        """ Collect extra values used to render the invoice PDF report containing CFDI information.

        :return: A python dictionary.
        """
        self.ensure_one()
        Document = self.env['l10n_mx_edi.document']
        cfdi_infos = Document._l10n_mx_edi_get_extra_common_report_values(self.l10n_mx_edi_cfdi_attachment_id)
        if not cfdi_infos:
            return cfdi_infos

        def get_tax_values(node, is_withholding=False):
            if node is None:
                return None
            cfdi_code = Document._get_cfdi_value(node, 'Impuesto')
            factor_type = Document._get_cfdi_value(node, 'TipoFactor')
            if cfdi_code not in CFDI_CODE_TO_TAX_TYPE or factor_type not in ('Tasa', 'Cuota', 'Exento'):
                return None

            sign = -1 if is_withholding else 1
            if factor_type == 'Exento':
                rate_or_fee = None
            else:
                factor = 100.0 if factor_type == 'Tasa' else 1.0
                rate_or_fee = sign * float(Document._get_cfdi_value(node, 'TasaOCuota') or '0.0') * factor

            return {
                'cfdi_code': cfdi_code,
                'tax_name': tax_type_names.get(CFDI_CODE_TO_TAX_TYPE[cfdi_code]),
                'factor_type': factor_type,
                'rate_or_fee': rate_or_fee,
                'amount_base': float(Document._get_cfdi_value(node, 'Base') or '0.0'),
                'amount_tax': sign * float(Document._get_cfdi_value(node, 'Importe') or '0.0'),
                'tax_key': (cfdi_code, factor_type, rate_or_fee),
            }

        total_withholding_tax_values = {}
        tax_type_names = dict(self.env['account.tax']._fields['l10n_mx_tax_type']._description_selection(self.env))
        cfdi_node = cfdi_infos['cfdi_node']
        conceptos_node = cfdi_node.xpath("//*[local-name()='Concepto']")
        conceptos_list = []
        # Build conceptos list
        for concepto_node in conceptos_node:
            cuenta_predial_node = Document._get_cfdi_node(concepto_node, "./*[local-name()='CuentaPredial']")
            conceptos_list.append({
                'concepto_node': concepto_node,
                'description': Document._get_cfdi_value(concepto_node, 'Descripcion'),
                'product_service_code': Document._get_cfdi_value(concepto_node, 'ClaveProdServ'),
                'identification_number': Document._get_cfdi_value(concepto_node, 'NoIdentificacion'),
                'quantity': float(Document._get_cfdi_value(concepto_node, 'Cantidad') or '0.0'),
                'unit': Document._get_cfdi_value(concepto_node, 'Unidad'),
                'unit_code': Document._get_cfdi_value(concepto_node, 'ClaveUnidad'),
                'price_unit': float(Document._get_cfdi_value(concepto_node, 'ValorUnitario') or '0.0'),
                'amount': float(Document._get_cfdi_value(concepto_node, 'Importe') or '0.0'),
                'tax_object': Document._get_cfdi_value(concepto_node, 'ObjetoImp'),
                'discount': float(Document._get_cfdi_value(concepto_node, 'Descuento') or '0.0'),
                'predial_account': Document._get_cfdi_value(cuenta_predial_node, 'Numero')
            })
            retencion_nodes = concepto_node.xpath("./*[local-name()='Impuestos']//*[local-name()='Retencion']")

            # Total Withholding node groups all taxes under the same CFDI tax type, so different rate taxes are added together
            # and we don't know how much of each tax was withheld. We take the values of each Conceptos item instead to
            # to know the real rate and tax amount.
            for retencion_node in retencion_nodes:
                tax_values = get_tax_values(retencion_node, is_withholding=True)
                if not tax_values:
                    continue
                if tax_values['tax_key'] in total_withholding_tax_values:
                    total_withholding_tax_values[tax_values['tax_key']]['amount_base'] += tax_values['amount_base']
                    total_withholding_tax_values[tax_values['tax_key']]['amount_tax'] += tax_values['amount_tax']
                else:
                    total_withholding_tax_values[tax_values['tax_key']] = {**tax_values}

        impuestos_list = []
        # Build and traslados info into list
        traslado_nodes = cfdi_node.xpath("./*[local-name()='Impuestos']//*[local-name()='Traslado']")
        for traslado_node in traslado_nodes:
            tax_values = get_tax_values(traslado_node)
            if not tax_values:
                continue
            impuestos_list.append(tax_values)

        impuestos_list.extend(total_withholding_tax_values.values())

        # Build info for local taxes into list
        for element in ('RetencionesLocales', 'TrasladosLocales'):
            sign = -1 if element == 'RetencionesLocales' else 1
            tax_name_attr = 'ImpLocRetenido' if element == 'RetencionesLocales' else 'ImpLocTrasladado'
            xpath = f"./*[local-name()='Complemento']//*[local-name()='{element}']"
            for tax_node in cfdi_node.xpath(xpath):
                impuestos_list.append({
                    'tax_name': Document._get_cfdi_value(tax_node, tax_name_attr),
                    'amount_tax': sign * float(Document._get_cfdi_value(tax_node, 'Importe') or '0.0'),
                    'is_local_tax': True,
                })

        # Other extra data
        payment_way = Document._get_cfdi_value(cfdi_node, 'FormaPago')
        if payment_way == '99':
            payment_way += ' - Por Definir'
        elif payment_way is not None:
            payment_method = self.env['l10n_mx_edi.payment.method'].search([('code', '=', payment_way)], limit=1)
            payment_way += f' - {payment_method.name}'

        cfdi_type_label = None
        if cfdi_infos['receipt_type'] in ('I', 'E'):
            cfdi_type_label = 'I - Income' if cfdi_infos['receipt_type'] == 'I' else 'E - Egress'

        receptor_fiscal_regime_name = dict(self.env['res.partner']._fields['l10n_mx_edi_fiscal_regime']
            ._description_selection(self.env)).get(cfdi_infos['receptor_fiscal_regime']
        )

        usage_desc = dict(self._fields['l10n_mx_edi_usage']._description_selection(self.env)).get(cfdi_infos['usage'])
        total_amount = float(cfdi_infos['amount_total'] or '0.0')
        total_amount_text = self._l10n_mx_edi_cfdi_amount_to_text(amount=total_amount)
        amount_discount = Document._get_cfdi_value(cfdi_node, 'Descuento')

        return {
            **cfdi_infos,
            'amount_subtotal': float(Document._get_cfdi_value(cfdi_node, 'SubTotal') or '0.0'),
            'total_amount': total_amount,
            'total_amount_text': total_amount_text,
            'amount_discount': float(amount_discount or '0.0'),
            'currency_rate': Document._get_cfdi_value(cfdi_node, 'TipoCambio'),
            'usage_desc': usage_desc,
            'receptor_fiscal_regime_name': receptor_fiscal_regime_name,
            'conceptos_list': conceptos_list,
            'impuestos_list': impuestos_list,
            'payment_way': payment_way,
            'cfdi_type_label': cfdi_type_label,
            'has_discount': amount_discount is not None,
            'has_long_desc': any(concepto['description'] and concepto['description'].count('\n') > 30 for concepto in conceptos_list),
            'has_predial': any(concepto['predial_account'] for concepto in conceptos_list),
        }

    def _l10n_mx_edi_get_extra_payment_report_values(self):
        """ Collect extra values used to render the payment PDF report containing CFDI information.

        :return: A python dictionary.
        """
        self.ensure_one()
        cfdi_infos = self.env['l10n_mx_edi.document']._l10n_mx_edi_get_extra_common_report_values(self.l10n_mx_edi_cfdi_attachment_id)
        if not cfdi_infos:
            return cfdi_infos

        node = cfdi_infos['cfdi_node'].xpath("//*[local-name()='Pago']")[0]
        payment_info = cfdi_infos['payment_info'] = {}
        payment_info['from_account_vat'] = node.get('RfcEmisorCtaOrd')
        payment_info['from_account_name'] = node.get('NomBancoOrdExt')
        payment_info['from_account_number'] = node.get('CtaOrdenante')
        payment_info['to_account_vat'] = node.get('RfcEmisorCtaBen')
        payment_info['to_account_number'] = node.get('CtaBeneficiario')

        related_invoices = cfdi_infos['invoices'] = []
        uuids = []
        for node in cfdi_infos['cfdi_node'].xpath("//*[local-name()='DoctoRelacionado']"):
            uuids.append(node.attrib['IdDocumento'])
            related_invoices.append({
                'uuid': node.attrib['IdDocumento'],
                'partiality': node.attrib['NumParcialidad'],
                'previous_balance': float(node.attrib['ImpSaldoAnt']),
                'amount_paid': float(node.attrib['ImpPagado']),
                'balance': float(node.attrib['ImpSaldoInsoluto']),
                'currency': node.attrib['MonedaDR'],
            })
        invoices = self.env['account.move'].search([('l10n_mx_edi_cfdi_uuid', 'in', uuids)])
        invoices_map = {x.l10n_mx_edi_cfdi_uuid: x for x in invoices}
        for invoice_values in related_invoices:
            invoice_values['invoice'] = invoices_map.get(invoice_values['uuid'], self.env['account.move'])

        return cfdi_infos

    def _l10n_mx_edi_get_refund_original_invoices(self):
        """ Get the related invoices for the current refunds.

        :return: The refunded invoices.
        """
        origin_uuids = set()
        for move in self.filtered(lambda x: x.move_type == 'out_refund'):
            cfdi_values = {}
            self.env['l10n_mx_edi.document']._add_document_origin_cfdi_values(cfdi_values, move.l10n_mx_edi_cfdi_origin)
            relationado_data = cfdi_values['cfdi_relationado_data']
            if '01' in relationado_data or '03' in relationado_data:
                origin_uuids.update(relationado_data.get('01', []) + relationado_data.get('03', []))
        if origin_uuids:
            return self.env['account.move'].search([('l10n_mx_edi_cfdi_uuid', 'in', list(origin_uuids))])
        return self.env['account.move']

    def copy_data(self, default=None):
        vals_list = super().copy_data(default)
        for move, vals in zip(self, vals_list):
            if (
                move.move_type == 'out_invoice'
                and vals['move_type'] == 'out_refund'
                and move.country_code == 'MX'
                and move.company_id.l10n_mx_income_return_discount_account_id
            ):
                for orm_command in vals['line_ids']:
                    if orm_command[0] == Command.CREATE and orm_command[2]['display_type'] == 'product':
                        orm_command[2]['account_id'] = move.company_id.l10n_mx_income_return_discount_account_id.id

        return vals_list

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('l10n_mx_edi_cfdi_state', 'l10n_mx_edi_cfdi_cancel_id')
    def _compute_need_cancel_request(self):
        # EXTENDS 'account'
        super()._compute_need_cancel_request()

    @api.depends('country_code')
    def _compute_amount_total_words(self):
        # EXTENDS 'account'
        super()._compute_amount_total_words()
        for move in self:
            if move.country_code == 'MX':
                move.amount_total_words = move._l10n_mx_edi_cfdi_amount_to_text()

    @api.depends('move_type', 'company_currency_id', 'origin_payment_id', 'statement_line_id')
    def _compute_l10n_mx_edi_is_cfdi_needed(self):
        """ Check whatever or not the CFDI is needed on this invoice.
        """
        for move in self:
            move.l10n_mx_edi_is_cfdi_needed = (
                move._l10n_mx_edi_is_cfdi_payment()
                or (move._l10n_mx_edi_is_cfdi_invoice() and move.move_type in ('out_invoice', 'out_refund'))
            )

    @api.depends('l10n_mx_edi_invoice_document_ids.state', 'l10n_mx_edi_invoice_document_ids.sat_state',
                 'l10n_mx_edi_payment_document_ids.state', 'l10n_mx_edi_payment_document_ids.sat_state')
    def _compute_l10n_mx_edi_document_ids(self):
        for move in self:
            if move._l10n_mx_edi_is_cfdi_invoice() or move._l10n_mx_edi_is_cfdi_bill():
                move.l10n_mx_edi_document_ids = [Command.set(move.l10n_mx_edi_invoice_document_ids.ids)]
            elif move._l10n_mx_edi_is_cfdi_payment():
                move.l10n_mx_edi_document_ids = [Command.set(move.l10n_mx_edi_payment_document_ids.ids)]
            else:
                move.l10n_mx_edi_document_ids = [Command.clear()]

    @api.depends('l10n_mx_edi_invoice_document_ids.state', 'l10n_mx_edi_invoice_document_ids.sat_state',
                 'l10n_mx_edi_payment_document_ids.state', 'l10n_mx_edi_payment_document_ids.sat_state')
    def _compute_l10n_mx_edi_cfdi_state_and_attachment(self):
        for move in self:
            move.l10n_mx_edi_cfdi_sat_state = None
            move.l10n_mx_edi_cfdi_state = None
            move.l10n_mx_edi_cfdi_attachment_id = None
            move.l10n_mx_edi_invoice_cancellation_reason = None
            if move._l10n_mx_edi_is_cfdi_invoice() or move._l10n_mx_edi_is_cfdi_bill():
                # Compute the SAT & the PAC states in 2 different loops.
                # In case of a request cancellation that failed, the SAT state needs
                # to be retrieved from the document corresponding to the request cancellation.
                # However, the PAC state needs to be retrieved from the original 'invoice_sent'
                # document.
                documents = move.l10n_mx_edi_invoice_document_ids.sorted()

                # 'l10n_mx_edi_cfdi_sat_state'.
                for doc in documents.filtered(lambda doc: doc.state in {
                    'invoice_sent',
                    'invoice_cancel_requested',
                    'invoice_cancel',
                    'invoice_received',
                    'ginvoice_sent',
                    'ginvoice_cancel',
                    'invoice_received',
                }):
                    if doc.sat_state != 'skip':
                        move.l10n_mx_edi_cfdi_sat_state = doc.sat_state
                        break

                # 'l10n_mx_edi_cfdi_state' / 'l10n_mx_edi_cfdi_attachment_id'.
                for doc in documents:
                    if doc.state == 'invoice_sent':
                        move.l10n_mx_edi_cfdi_state = 'sent'
                        move.l10n_mx_edi_cfdi_attachment_id = doc.attachment_id
                        break
                    elif doc.state == 'invoice_received':
                        move.l10n_mx_edi_cfdi_state = 'received'
                        move.l10n_mx_edi_cfdi_attachment_id = doc.attachment_id
                        break
                    elif doc.state == 'ginvoice_sent':
                        move.l10n_mx_edi_cfdi_state = 'global_sent'
                        move.l10n_mx_edi_cfdi_attachment_id = doc.attachment_id
                        break
                    elif doc.state == 'invoice_cancel_requested' and doc.sat_state == 'not_defined':
                        move.l10n_mx_edi_cfdi_state = 'cancel_requested'
                        move.l10n_mx_edi_cfdi_attachment_id = doc.attachment_id
                        move.l10n_mx_edi_invoice_cancellation_reason = doc.cancellation_reason
                        break
                    elif doc.state == 'invoice_cancel':
                        move.l10n_mx_edi_cfdi_state = 'cancel'
                        move.l10n_mx_edi_cfdi_attachment_id = doc.attachment_id
                        move.l10n_mx_edi_invoice_cancellation_reason = doc.cancellation_reason
                        break
                    elif doc.state == 'ginvoice_cancel' and doc.cancellation_reason != '01':
                        move.l10n_mx_edi_cfdi_state = 'global_cancel'
                        move.l10n_mx_edi_cfdi_attachment_id = doc.attachment_id
                        move.l10n_mx_edi_invoice_cancellation_reason = doc.cancellation_reason
                        break
            elif move._l10n_mx_edi_is_cfdi_payment():
                for doc in move.l10n_mx_edi_payment_document_ids.sorted():
                    if doc.state == 'payment_sent':
                        move.l10n_mx_edi_cfdi_sat_state = doc.sat_state
                        move.l10n_mx_edi_cfdi_state = 'sent'
                        move.l10n_mx_edi_cfdi_attachment_id = doc.attachment_id
                        break
                    elif doc.state == 'payment_cancel':
                        move.l10n_mx_edi_cfdi_sat_state = doc.sat_state
                        move.l10n_mx_edi_cfdi_state = 'cancel'
                        move.l10n_mx_edi_cfdi_attachment_id = doc.attachment_id
                        move.l10n_mx_edi_invoice_cancellation_reason = doc.cancellation_reason
                        break

    @api.depends('l10n_mx_edi_invoice_document_ids.state', 'reconciled_payment_ids.is_reconciled')
    def _compute_l10n_mx_edi_update_payments_needed(self):
        payments_diff = self._origin._l10n_mx_edi_cfdi_invoice_get_payments_diff()
        for move in self:
            move.l10n_mx_edi_update_payments_needed = bool(
                move in payments_diff['to_remove']
                or move in payments_diff['need_update']
                or payments_diff['to_process']
            )

    @api.depends('state', 'l10n_mx_edi_cfdi_state', 'l10n_mx_edi_cfdi_sat_state')
    def _compute_l10n_mx_edi_update_sat_needed(self):
        for move in self:
            if move._l10n_mx_edi_is_cfdi_invoice() or move._l10n_mx_edi_is_cfdi_bill():
                documents = move.l10n_mx_edi_invoice_document_ids
            elif move._l10n_mx_edi_is_cfdi_payment():
                documents = move.l10n_mx_edi_payment_document_ids
            else:
                move.l10n_mx_edi_update_sat_needed = False
                continue
            move.l10n_mx_edi_update_sat_needed = bool(
                # sudo: pos_order_ids might appear in the domain and the accountant user might not have access to PoS
                documents.sudo().filtered_domain(documents._get_update_sat_status_domain(from_cron=False))
            )

    @api.depends('l10n_mx_edi_cfdi_attachment_id')
    def _compute_l10n_mx_edi_cfdi_uuid(self):
        '''Fill the invoice fields from the cfdi values.
        '''
        for move in self:
            if move.l10n_mx_edi_cfdi_attachment_id:
                cfdi_infos = self.env['l10n_mx_edi.document']._decode_cfdi_attachment(
                    move.l10n_mx_edi_cfdi_attachment_id.raw.content)
                move.l10n_mx_edi_cfdi_uuid = cfdi_infos.get('uuid')
            else:
                move.l10n_mx_edi_cfdi_uuid = None

    @api.depends('l10n_mx_edi_cfdi_attachment_id', 'l10n_mx_edi_cfdi_state')
    def _compute_cfdi_values(self):
        '''Fill the invoice fields from the cfdi values.
        '''
        for move in self:
            cfdi_infos = self.env['l10n_mx_edi.document']._decode_cfdi_attachment(
                move.l10n_mx_edi_cfdi_attachment_id.raw.content)
            move.l10n_mx_edi_cfdi_supplier_rfc = cfdi_infos.get('supplier_rfc')
            move.l10n_mx_edi_cfdi_customer_rfc = cfdi_infos.get('customer_rfc')
            move.l10n_mx_edi_cfdi_amount = cfdi_infos.get('amount_total')

    @api.depends('partner_id', 'move_type', 'invoice_date_due', 'invoice_date', 'invoice_payment_term_id')
    def _compute_l10n_mx_edi_payment_policy(self):
        for move in self:
            if not move._l10n_mx_edi_is_cfdi_invoice():
                move.l10n_mx_edi_payment_policy = False
                continue
            if move.is_purchase_document(include_receipts=True):
                continue

            move.l10n_mx_edi_payment_policy = (
                move.move_type == 'out_refund' and 'PUE'
                or move.l10n_mx_edi_payment_policy
                or move.l10n_mx_edi_is_cfdi_needed
                and move.partner_id.l10n_mx_edi_payment_policy
            )
            if (
                not move.l10n_mx_edi_payment_policy
                and move.invoice_date_due
                and move.invoice_date
                and move.l10n_mx_edi_is_cfdi_needed
            ):
                # In CFDI 3.3 - rule 2.7.1.43 which establish that
                # invoice payment term should be PPD as soon as the due date
                # is after the last day of  the month (the month of the invoice date).
                if (
                    move.move_type in ('out_invoice', 'out_refund')
                    and (
                        move.invoice_date_due > move.invoice_date
                        and (
                            move.invoice_date_due.month > move.invoice_date.month
                            or move.invoice_date_due.year > move.invoice_date.year
                            or len(move.invoice_payment_term_id.line_ids) > 1
                        )
                    )
                ):
                    move.l10n_mx_edi_payment_policy = 'PPD'
                else:
                    # By default, PUE means immediate payment and then, no need to send the payments to
                    # the SAT except if you explicitly send them.
                    move.l10n_mx_edi_payment_policy = 'PUE'

    @api.depends('l10n_mx_edi_is_cfdi_needed', 'l10n_mx_edi_cfdi_origin', 'partner_id', 'company_id', 'l10n_mx_edi_partner_address_complete')
    def _compute_l10n_mx_edi_cfdi_to_public(self):
        for move in self:
            if move.country_code != 'MX':
                move.l10n_mx_edi_cfdi_to_public = False
            elif (
                move.partner_id.country_code != 'MX'
                or (
                    move.move_type == 'out_refund'
                    and 'global_sent' in set(move._l10n_mx_edi_get_refund_original_invoices().mapped('l10n_mx_edi_cfdi_state'))
                )
                or (move.partner_id and not move.l10n_mx_edi_partner_address_complete)
            ):
                move.l10n_mx_edi_cfdi_to_public = True
            elif (
                move.l10n_mx_edi_is_cfdi_needed
                and move.partner_id
                and move.company_id
            ):
                cfdi_values = self.env['l10n_mx_edi.document']._get_company_cfdi_values(move.company_id)
                self.env['l10n_mx_edi.document']._add_customer_cfdi_values(
                    cfdi_values,
                    customer=move.partner_id,
                )
                move.l10n_mx_edi_cfdi_to_public = cfdi_values['receptor']['rfc'] == 'XAXX010101000'
            else:
                move.l10n_mx_edi_cfdi_to_public = move.l10n_mx_edi_cfdi_to_public

    @api.depends('partner_id', 'commercial_partner_id')
    def _compute_l10n_mx_edi_addenda_ids(self):
        for move in self:
            partner = move.partner_id or move.commercial_partner_id
            if move.l10n_mx_edi_is_cfdi_needed:
                move.l10n_mx_edi_addenda_ids = partner.l10n_mx_edi_addenda_ids
            else:
                move.l10n_mx_edi_addenda_ids = False

    @api.depends('journal_id', 'statement_line_id', 'partner_id')
    def _compute_l10n_mx_edi_payment_method_id(self):
        transferencia_payment_method = self.env.ref('l10n_mx_edi.payment_method_transferencia', raise_if_not_found=False)
        for move in self:
            if move.country_code != 'MX':
                move.l10n_mx_edi_payment_method_id = False
                continue
            if move.is_invoice(include_receipts=True):
                payment_method = move.partner_id.l10n_mx_edi_payment_method_id or move.l10n_mx_edi_payment_method_id
            else:
                payment_method = move.l10n_mx_edi_payment_method_id or move.partner_id.l10n_mx_edi_payment_method_id
            move.l10n_mx_edi_payment_method_id = (
                payment_method or
                move.journal_id.l10n_mx_edi_payment_method_id or
                bool(move._l10n_mx_edi_is_cfdi_payment()) and transferencia_payment_method
            )

    @api.depends('partner_id')
    def _compute_l10n_mx_edi_usage(self):
        for move in self:
            if move.country_code == 'MX':
                move.l10n_mx_edi_usage = (
                    move.partner_id.l10n_mx_edi_usage or
                    move.l10n_mx_edi_usage or
                    'G03'
                )
            else:
                move.l10n_mx_edi_usage = False

    @api.depends('l10n_mx_edi_cfdi_uuid')
    def _compute_l10n_mx_edi_cfdi_cancel_id(self):
        for move in self:
            if move.company_id and move.l10n_mx_edi_cfdi_uuid:
                move.l10n_mx_edi_cfdi_cancel_id = move.search(
                    [
                        ('l10n_mx_edi_cfdi_origin', '=like', f'04|{move.l10n_mx_edi_cfdi_uuid}%'),
                        ('company_id', '=', move.company_id.id)
                    ],
                    limit=1,
                )
            else:
                move.l10n_mx_edi_cfdi_cancel_id = None

    @api.depends('l10n_mx_edi_cfdi_uuid')
    def _compute_duplicated_ref_ids(self):
        return super()._compute_duplicated_ref_ids()

    @api.depends('l10n_mx_edi_cfdi_state', 'l10n_mx_edi_cfdi_sat_state')
    def _compute_show_reset_to_draft_button(self):
        # EXTENDS 'account'
        # When the PAC approved the cancellation but we are awaiting the SAT confirmation,
        # don't allow to reset draft the invoice.
        super()._compute_show_reset_to_draft_button()
        for move in self:
            if (
                move.show_reset_to_draft_button
                and move.l10n_mx_edi_cfdi_state not in ('cancel', 'received', 'global_cancel', False)
                and move.state == 'posted'
            ):
                move.show_reset_to_draft_button = False

    @api.depends('l10n_mx_edi_show_import_totals_alert')
    def _compute_alerts(self):
        # EXTENDS account
        return super()._compute_alerts()

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------

    @api.constrains('l10n_mx_edi_cfdi_origin')
    def _check_l10n_mx_edi_cfdi_origin(self):
        error_message = self.env._(
            "The following CFDI origin %s is invalid and must match the "
            "<code>|<uuid1>,<uuid2>,...,<uuidn> template.\n"
            "Here are the specification of this value:\n"
            "- 01: Nota de crédito\n"
            "- 02: Nota de débito de los documentos relacionados\n"
            "- 03: Devolución de mercancía sobre facturas o traslados previos\n"
            "- 04: Sustitución de los CFDI previos\n"
            "- 05: Traslados de mercancias facturados previamente\n"
            "- 06: Factura generada por los traslados previos\n"
            "- 07: CFDI por aplicación de anticipo\n"
            "For example: 01|89966ACC-0F5C-447D-AEF3-3EED22E711EE,89966ACC-0F5C-447D-AEF3-3EED22E711EE\n"
            "If there are more than one relation type, it needs to be separated by comma\n"
            "For example: 01|89966ACC-0F5C-447D-AEF3-3EED22E711EE,03|89966ACC-0F5C-447D-AEF3-3EED22E711EE,6fad57a1-bf5b-4e27-a5d3-d84b2f36674c"
        )

        for move in self.filtered('l10n_mx_edi_cfdi_origin'):
            cfdi_values = {}
            self.env['l10n_mx_edi.document']._add_document_origin_cfdi_values(cfdi_values, move.l10n_mx_edi_cfdi_origin)
            if not cfdi_values['cfdi_relationado_data']:
                raise ValidationError(error_message % move.l10n_mx_edi_cfdi_origin)

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------

    def action_invoice_download_cfdi(self):
        if invoices_with_cfdi := self.filtered('l10n_mx_edi_cfdi_attachment_id'):
            return {
                'type': 'ir.actions.act_url',
                'url': f'/account/download_invoice_documents/{",".join(map(str, invoices_with_cfdi.ids))}/cfdi',
                'target': 'download',
            }
        return False

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    def _post(self, soft=False):
        result = super()._post(soft=soft)
        self.filtered(lambda move: move.state == 'posted'
            and move.l10n_mx_edi_show_import_totals_alert
        ).l10n_mx_edi_show_import_totals_alert = False

        return result

    def _l10n_mx_edi_need_cancel_request(self):
        self.ensure_one()
        return (
            self.l10n_mx_edi_cfdi_state == 'sent'
            and self.l10n_mx_edi_cfdi_attachment_id
            and (
                not self.l10n_mx_edi_cfdi_cancel_id
                or self.l10n_mx_edi_cfdi_cancel_id.l10n_mx_edi_cfdi_state
            )
        )

    def _need_cancel_request(self):
        # EXTENDS 'account'
        return super()._need_cancel_request() or self._l10n_mx_edi_need_cancel_request()

    def button_request_cancel(self):
        # Check the CFDI state to restrict this code to MX only.
        if self._l10n_mx_edi_need_cancel_request():
            doc = self.l10n_mx_edi_document_ids.filtered(lambda x: (
                x.attachment_uuid == self.l10n_mx_edi_cfdi_uuid
                and x.state in ('invoice_sent', 'payment_sent')
            ))[0]
            return doc.action_cancel()

        return super().button_request_cancel()

    def button_draft(self):
        Document = self.env['l10n_mx_edi.document']
        for move in self.filtered('l10n_mx_edi_is_cfdi_needed'):
            cfdi_values = Document._get_company_cfdi_values(move.company_id)
            Document._add_customer_cfdi_values(cfdi_values, customer=move.partner_id)
            timezoned_now = Document._get_datetime_now_with_mx_timezone(cfdi_values, journal=move.journal_id)
            timezoned_today = timezoned_now.date()
            if move.l10n_mx_edi_post_time and move.l10n_mx_edi_post_time.date() < timezoned_today:
                move.l10n_mx_edi_post_time = False
        return super().button_draft()

    def _reverse_moves(self, default_values_list=None, cancel=False):
        # OVERRIDE
        # The '01' code is used to indicate the document is a credit note.
        if not default_values_list:
            default_values_list = [{}] * len(self)

        for default_vals, move in zip(default_values_list, self):
            if move.l10n_mx_edi_cfdi_uuid:
                default_vals['l10n_mx_edi_cfdi_origin'] = move._l10n_mx_edi_write_cfdi_origin('01', [move.l10n_mx_edi_cfdi_uuid])
        return super()._reverse_moves(default_values_list, cancel=cancel)

    def _get_mail_thread_data_attachments(self):
        # EXTENDS 'account'
        return super()._get_mail_thread_data_attachments() \
            - self.l10n_mx_edi_payment_document_ids.attachment_id \
            | self.l10n_mx_edi_cfdi_attachment_id

    @api.model
    def get_invoice_localisation_fields_required_to_invoice(self, country_id):
        res = super().get_invoice_localisation_fields_required_to_invoice(country_id)
        if country_id.code == 'MX':
            res.extend([self.env['ir.model.fields']._get(self._name, 'l10n_mx_edi_usage')])
        return res

    def _get_name_invoice_report(self):
        # EXTENDS account
        self.ensure_one()
        if self.l10n_mx_edi_cfdi_state in ('sent', 'cancel') and self.l10n_mx_edi_cfdi_attachment_id and self.l10n_mx_edi_cfdi_uuid:
            return 'l10n_mx_edi.report_invoice_document'
        return super()._get_name_invoice_report()

    def _get_edi_doc_attachments_to_export(self):
        # EXTENDS 'account'
        return super()._get_edi_doc_attachments_to_export() + self.l10n_mx_edi_cfdi_attachment_id

    def _fetch_duplicate_fiscal_folio(self, matching_states=("draft", "posted")):
        """ Fetch duplicate moves having the same folio fiscal.

            :param only_posted: indicates if you want to check only posted duplicates
            :return: a dict mapping original moves to its duplicates according to the folio fiscal
        """
        mx_moves = self.filtered(
            lambda m: (
                (m._l10n_mx_edi_is_cfdi_invoice() or m._l10n_mx_edi_is_cfdi_bill())
                and m.l10n_mx_edi_cfdi_uuid
                and m._origin.id
            )
        )
        if not mx_moves:
            return {}

        self.env["account.move"].flush_model(("company_id", "move_type", "l10n_mx_edi_cfdi_uuid"))

        self.env.cr.execute(
            """
              SELECT move.id AS move_id,
                     ARRAY_AGG(duplicate_move.id) AS duplicate_ids
                FROM account_move AS move
                JOIN account_move AS duplicate_move
                  ON move.company_id = duplicate_move.company_id
                 AND move.move_type = duplicate_move.move_type
                 AND move.id != duplicate_move.id
                 AND move.l10n_mx_edi_cfdi_uuid = duplicate_move.l10n_mx_edi_cfdi_uuid
                 AND duplicate_move.state IN %(matching_states)s
               WHERE move.id IN %(moves)s
                 AND move.l10n_mx_edi_cfdi_state NOT IN ('global_sent', 'global_cancel')
            GROUP BY move.id
            """,
            {
                "matching_states": tuple(matching_states),
                "moves": tuple(mx_moves.ids),
            },
        )
        return {
            self.env["account.move"].browse(res["move_id"]): self.env["account.move"].browse(res["duplicate_ids"])
            for res in self.env.cr.dictfetchall()
        }

    def _fetch_duplicate_reference(self, matching_states=('draft', 'posted')):
        # EXTENDS account
        # We check whether there are moves with the same fiscal folio if we have Mexican bills
        fiscal_folio_duplicates = self._fetch_duplicate_fiscal_folio(matching_states=matching_states)
        move_duplicates = super()._fetch_duplicate_reference(matching_states=matching_states)
        for move, duplicates in fiscal_folio_duplicates.items():
            move_duplicates[move] = move_duplicates.get(move, self.env['account.move']) | duplicates
        return move_duplicates

    def _get_alerts(self):
        # EXTENDS account
        alerts = super()._get_alerts()
        if self.l10n_mx_edi_show_import_totals_alert:
            alerts['import_totals'] = {
                'message': self.env._(
                    "The total amounts of the CFDI do not match the totals of the invoice. \n"
                    "Review the chatter for more information."
                ),
                'level': 'danger',
            }

        return alerts

    # -------------------------------------------------------------------------
    # CFDI Generation: Generic
    # -------------------------------------------------------------------------

    def _l10n_mx_edi_add_common_cfdi_values(self, cfdi_values):
        ''' Populate cfdi values to generate a cfdi for a journal entry. '''
        self.ensure_one()
        Document = self.env['l10n_mx_edi.document']
        Document._add_base_cfdi_values(cfdi_values)
        Document._add_currency_cfdi_values(cfdi_values, self.currency_id)
        Document._add_document_name_cfdi_values(cfdi_values, self.name)
        Document._add_document_origin_cfdi_values(cfdi_values, self.l10n_mx_edi_cfdi_origin)

    # -------------------------------------------------------------------------
    # CFDI Generation: Invoices
    # -------------------------------------------------------------------------

    def _l10n_mx_edi_cfdi_invoice_line_ids(self):
        """ Get the invoice lines to be considered when creating the CFDI.

        :return: A recordset of invoice lines.
        """
        self.ensure_one()
        return self.invoice_line_ids.filtered(lambda line: (
            line.display_type == 'product'
            and not line.currency_id.is_zero(line.price_unit * line.quantity)
        ))

    def _l10n_mx_edi_cfdi_check_invoice_config(self):
        """ Prepare the CFDI xml for the invoice. """
        self.ensure_one()
        Document = self.env['l10n_mx_edi.document']
        errors = []

        # == Check the 'l10n_mx_edi_decimal_places' field set on the currency  ==
        currency_precision = self.currency_id.l10n_mx_edi_decimal_places
        if currency_precision is False:
            errors.append(self.env._(
                "The SAT does not provide information for the currency %s.\n"
                "You must get manually a key from the PAC to confirm the "
                "currency rate is accurate enough.",
                self.currency_id,
            ))

        # == Check the invoice ==
        base_lines, tax_lines = self._l10n_mx_edi_get_invoice_cfdi_base_lines()
        base_lines = Document._add_and_round_tax_details(base_lines, self.company_id, tax_lines=tax_lines)
        dispatched_lines = Document._dispatch_negative_base_lines(base_lines, self.company_id)
        base_lines = dispatched_lines['base_lines']
        nullified_base_lines = dispatched_lines['nullified_base_lines']
        if not base_lines and not nullified_base_lines:
            errors.append(self.env._("The invoice must contain at least one positive line to generate the CFDI."))
        invalid_unspcs_products = self.env['product.product']
        for base_line in base_lines:
            if not base_line['product_unspsc_code']:
                invalid_unspcs_products |= base_line['product_id']
        if invalid_unspcs_products:
            errors.append(self.env._(
                "You need to define an 'UNSPSC Product Category' on the following products: %s",
                ', '.join(invalid_unspcs_products.mapped('display_name')),
            ))
        return errors

    def _l10n_mx_edi_get_invoice_cfdi_base_lines(self, global_invoice=False):
        self.ensure_one()
        base_lines, tax_lines = self._get_rounded_base_and_tax_lines()
        base_lines = [base_line for base_line in base_lines if base_line['special_type'] != 'cash_rounding']
        for base_line in base_lines:
            invl = base_line['record']
            base_line.update({
                'uom_id': invl.product_uom_id,
                'name': invl._l10n_mx_edi_get_cfdi_line_name(),
                'product_unspsc_code': invl._get_product_unspsc_code(),
                'uom_unspsc_code': invl._get_uom_unspsc_code(),
                'tax_objected': invl.l10n_mx_edi_tax_object,
            })
        return base_lines, tax_lines

    def _l10n_mx_edi_add_invoice_cfdi_values(self, cfdi_values):
        self.ensure_one()
        Document = self.env['l10n_mx_edi.document']

        # Manage the negative lines.
        base_lines, tax_lines = self._l10n_mx_edi_get_invoice_cfdi_base_lines()
        base_lines = Document._add_and_round_tax_details(base_lines, self.company_id, tax_lines=tax_lines)
        dispatched_lines = Document._dispatch_negative_base_lines(base_lines, self.company_id)
        remaining_negative_base_lines = dispatched_lines['remaining_negative_base_lines']
        if remaining_negative_base_lines:
            cfdi_values['errors'] = [self.env._("Failed to distribute some negative lines")]
            return
        base_lines = dispatched_lines['base_lines']
        if not base_lines:
            cfdi_values['errors'] = ['empty_cfdi']
            return

        self._l10n_mx_edi_add_common_cfdi_values(cfdi_values)
        cfdi_values['tipo_de_comprobante'] = 'I' if self.move_type == 'out_invoice' else 'E'
        Document._add_customer_cfdi_values(
            cfdi_values,
            customer=self.partner_id,
            usage=self.l10n_mx_edi_usage,
            to_public=self.l10n_mx_edi_cfdi_to_public,
        )
        Document._add_tax_objected_cfdi_values(cfdi_values, base_lines)
        Document._add_base_lines_cfdi_values(cfdi_values, base_lines)
        Document._add_date_cfdi_values(
            cfdi_values,
            self.invoice_date,
            journal=self.journal_id,
            document_post_time=self.l10n_mx_edi_post_time,
        )
        Document._add_payment_policy_cfdi_values(
            cfdi_values,
            payment_policy=self.l10n_mx_edi_payment_policy,
            payment_method=self.l10n_mx_edi_payment_method_id,
        )

        # Payment terms.
        cfdi_values['condiciones_de_pago'] = self.invoice_payment_term_id.name

        # Currency.
        if self.currency_id.name == 'MXN':
            cfdi_values['tipo_cambio'] = None
        else:
            cfdi_values["tipo_cambio"] = 1.0 / self.invoice_currency_rate

        # Additional Addendas and Complementos.
        cfdi_values['addendas'] = self.l10n_mx_edi_addenda_ids.sudo(flag=False)
        cfdi_values['move'] = self.sudo(flag=False)

    def _l10n_mx_edi_get_invoice_cfdi_filename(self):
        """ Get the filename of the CFDI.

        :return: The filename as a string.
        """
        self.ensure_one()
        return f"{self.journal_id.code}-{self.name}-MX-Invoice-4.0.xml".replace('/', '')

    def _get_invoice_report_filename(self, extension='pdf', report=None):
        # EXTENDS 'account'
        return f'{self._l10n_mx_edi_get_invoice_cfdi_filename()[:-4]}.{extension}'\
            if self.l10n_mx_edi_is_cfdi_needed else super()._get_invoice_report_filename(extension=extension, report=report)

    # -------------------------------------------------------------------------
    # CFDI Generation: Payments
    # -------------------------------------------------------------------------

    def _l10n_mx_edi_get_payment_cfdi_pago_values(self, invoice_results, company_currency, payment_method=None):
        """ Returns the values to render the pago20:Pago node in the payment cfdi.

        :param invoice_results:     The amounts to consider for each invoice.
        :param company_currency:    The currency of the company.
        :param payment_method:      The 'l10n_mx_edi.payment.method' record to consider for this payment.
                                    If 'False', will fallback to 'l10n_mx_edi_payment_method_id' of 'self'.
        :return: A dictionary to render a pago20:Pago node.
        """
        self.ensure_one()
        Document = self.env['l10n_mx_edi.document']
        payment_cfdi_values = {}

        total_in_payment_curr = sum(x['payment_amount_currency'] for x in invoice_results)
        total_in_company_curr = sum(x['balance'] + x['payment_exchange_balance'] for x in invoice_results)
        same_currency = self.currency_id == company_currency

        payment_cfdi_values['monto'] = total_in_company_curr if same_currency else total_in_payment_curr

        # Exchange rate.
        # 'tipo_cambio' is a conditional attribute used to express the exchange rate of the currency on the date the
        # payment was made.
        # The value must reflect the number of Mexican pesos that are equivalent to a unit of the currency indicated
        # in the 'moneda' attribute.
        # It is required when the MonedaP attribute is different from MXN.
        payment_cfdi_values['tipo_cambio_dp'] = 6
        if same_currency:
            payment_rate = None
        else:
            delta_foreign_rounding = self.currency_id.rounding / 10 * 5
            delta_comp_rounding = company_currency.rounding / 10 * 5
            num = abs(total_in_company_curr) - delta_comp_rounding
            den = abs(total_in_payment_curr) + delta_foreign_rounding
            raw_payment_rate_lower_bound = num / den if den else 0.0
            num = abs(total_in_company_curr) + delta_comp_rounding
            den = abs(total_in_payment_curr) - delta_foreign_rounding
            raw_payment_rate_upper_bound = num / den if den else 0.0
            expected_rate = self._get_expected_currency_rate_at(self.date)
            theorical_rate = 1 / expected_rate if expected_rate else None
            if (
                theorical_rate and
                raw_payment_rate_lower_bound <= theorical_rate <= raw_payment_rate_upper_bound
            ):
                raw_payment_rate = theorical_rate
            else:
                raw_payment_rate = abs(total_in_company_curr / total_in_payment_curr) if total_in_payment_curr else 0.0
            payment_rate = float_round(raw_payment_rate, precision_digits=payment_cfdi_values['tipo_cambio_dp'])

        payment_cfdi_values.update({
            'tipo_cambio': payment_rate,
            'mxn_digits': company_currency.decimal_places,
            'forma_de_pago': ((payment_method or self.l10n_mx_edi_payment_method_id).code or '').replace('NA', '99')
        })

        def calculate_rate(invoice_amount, payment_amount):
            if not payment_amount:
                return 0.0
            return float_round(abs(invoice_amount / payment_amount), 10)

        # Documents
        dcto_relationado_list = []
        for invoice_values in invoice_results:
            invoice = invoice_values['invoice']

            invoice_cfdi_values = Document._get_company_cfdi_values(invoice.company_id)
            Document._add_certificate_cfdi_values(invoice_cfdi_values)

            invoice._l10n_mx_edi_add_invoice_cfdi_values(invoice_cfdi_values)

            if invoice.amount_total:
                percentage_paid = abs(invoice_values['reconciled_amount'] / invoice.amount_total)
            else:
                percentage_paid = 0.0

            # Update '[local_]retenciones_list' / '[local_]traslados_list' for each base_line based on the % paid.
            base_lines = invoice_cfdi_values['base_lines']
            # Recompute the regular taxes without rounding
            Document._prefill_base_lines_with_regular_taxes_data(base_lines)
            for target_list in ('retenciones_list', 'traslados_list', 'local_retenciones_list', 'local_traslados_list'):
                for base_line in base_lines:
                    for tax_values in base_line['l10n_mx_cfdi_values'][target_list]:
                        for tax_key in ('raw_base', 'raw_importe'):
                            tax_values[tax_key] *= percentage_paid

            # Add '[local_]retenciones_list' / '[local_]traslados_list' for the invoice.
            # Fill 'base' / 'importe' using 6 decimals.
            invoice_cfdi_values.update(Document._prepare_document_taxes_data([x['l10n_mx_cfdi_values'] for x in base_lines]))
            for target_list in ('retenciones_list', 'traslados_list', 'local_retenciones_list', 'local_traslados_list'):
                for tax_values in invoice_cfdi_values[target_list]:
                    tax_values['base'] = float_round(tax_values['raw_base'], precision_digits=6) or 0.000001
                    tax_values['importe'] = float_round(tax_values['raw_importe'], precision_digits=6)

            # 'equivalencia' (rate) is a conditional attribute used to express the exchange rate according to the currency
            # registered in the document related. It is required when the currency of the related document is different
            # from the payment currency.
            # The number of units of the currency must be recorded indicated in the related document that are
            # equivalent to a unit of the currency of the payment.
            if invoice.currency_id == self.currency_id:
                # Same currency.
                computed_rate = None
            elif self.currency_id == company_currency != invoice.currency_id:
                # Adapt the invoice rate to find the reconciled amount of the payment but expressed in invoice currency.
                balance = invoice_values['balance'] + invoice_values['payment_exchange_balance']
                computed_rate = calculate_rate(invoice_values['invoice_amount_currency'], balance)
            else:
                # Both are expressed in different currencies.
                computed_rate = calculate_rate(invoice_values['invoice_amount_currency'], invoice_values['payment_amount_currency'])

            # 'objeto_imp' has to be set on the invoice but is computed for each lines.
            all_tax_objected = {line['objeto_imp'] for line in invoice_cfdi_values['conceptos_list']}
            all_tax_objected.discard('04')
            objeto_imp = all_tax_objected.pop() if len(all_tax_objected) == 1 else '02'

            dcto_relationado_list.append({
                **invoice_cfdi_values,
                'objeto_imp': objeto_imp,
                'id_documento': invoice.l10n_mx_edi_cfdi_uuid,
                'equivalencia': computed_rate,
                'num_parcialidad': invoice_values['number_of_payments'],
                'imp_pagado': invoice_values['reconciled_amount'],
                'imp_saldo_ant': invoice_values['amount_residual_before'],
                'imp_saldo_insoluto': invoice_values['amount_residual_after'],
            })

        payment_cfdi_values['dcto_relationado_list'] = dcto_relationado_list

        return payment_cfdi_values

    def _l10n_mx_edi_add_payment_cfdi_values(self, cfdi_values, pay_results):
        """ Prepare the values to render the payment cfdi.

        :param cfdi_values: Prepared cfdi_values.
        :param pay_results: The amounts to consider for each invoice.
                            See '_l10n_mx_edi_cfdi_payment_get_reconciled_invoice_values'.
        :return: The dictionary to render the xml.
        """
        self.ensure_one()
        Document = self.env['l10n_mx_edi.document']

        self._l10n_mx_edi_add_common_cfdi_values(cfdi_values)
        company = cfdi_values['company']
        company_curr = company.currency_id

        # Misc.
        cfdi_values['exportacion'] = '01'
        cfdi_values['moneda'] = self.currency_id.name
        cfdi_values['num_operacion'] = self.ref

        # Date.
        cfdi_date = datetime.combine(fields.Datetime.from_string(self.date), datetime.strptime('12:00:00', '%H:%M:%S').time())
        cfdi_values['fecha'] = Document._get_datetime_now_with_mx_timezone(cfdi_values, journal=self.journal_id).strftime(CFDI_DATE_FORMAT)
        cfdi_values['fecha_pago'] = cfdi_date.strftime(CFDI_DATE_FORMAT)

        has_factoring = any(results['is_compensation'] for results in pay_results['invoice_results'])
        compensation_payment_method = self.env.ref('l10n_mx_edi.payment_method_17', raise_if_not_found=False)

        # Since factoring payments involves a third party, the payment should have a contact set
        if has_factoring and not self.partner_id:
            if not self.partner_id:
                cfdi_values['errors'] = [self.env._("Missing contact information in factoring payment.")]
                return
            if not compensation_payment_method:
                cfdi_values['errors'] = [self.env._("Failed to generate payment cfdi with factoring. Payment way for compensations was not found.")]
                return

        # Invoice amounts for each payment node
        cfdi_values['payment_list'] = []
        for results in pay_results['invoice_results']:
            payment_values = results['payment_values']
            payment_method = compensation_payment_method if results['is_compensation'] else False
            cfdi_values['payment_list'].append(self._l10n_mx_edi_get_payment_cfdi_pago_values(payment_values, company_curr, payment_method=payment_method))

        # Customer
        customers = [dcto['receptor'] for pay in cfdi_values['payment_list'] for dcto in pay['dcto_relationado_list']]
        rfcs = {x['rfc'] for x in customers}
        if len(rfcs) > 1 and not has_factoring:
            cfdi_values['errors'] = [self.env._("You can't register a payment for invoices having different RFCs.")]
            return

        if not has_factoring:
            customer_values = customers[0]
        else:  # In case of a payment with factoring, the receptor will be the partner selected on the payment
            dummy_cfdi_values = Document._get_company_cfdi_values(company)
            Document._add_customer_cfdi_values(dummy_cfdi_values, customer=self.partner_id)
            customer_values = dummy_cfdi_values['receptor']

        customer = customer_values['customer']
        cfdi_values['receptor'] = customer_values
        cfdi_values['lugar_expedicion'] = cfdi_values['issued_address'].zip

        # Bank information.
        bank_account = customer.bank_ids.filtered(lambda x: x.company_id.id in (False, company.id))[:1]

        if bank_account.country_id and bank_account.country_code != 'MX':
            partner_bank_vat = 'XEXX010101000'
        else:  # if no partner_bank (e.g. cash payment), partner_bank_vat is not set.
            partner_bank_vat = bank_account.l10n_mx_edi_vat

        payment_account_ord = re.sub(r'\s+', '', bank_account.account_number or '') or None
        payment_account_receiver = re.sub(r'\s+', '', self.journal_id.bank_account_id.account_number or '') or None

        total_payment_amount = 0
        for pay in cfdi_values['payment_list']:
            payment_method_code = pay['forma_de_pago']
            is_payment_code_emitter_ok = payment_method_code in ('02', '03', '04', '05', '06', '28', '29', '99')
            is_payment_code_receiver_ok = payment_method_code in ('02', '03', '04', '05', '28', '29', '99')
            is_payment_code_bank_ok = payment_method_code in ('02', '03', '04', '28', '29', '99')

            pay.update({
                'rfc_emisor_cta_ord': is_payment_code_emitter_ok and partner_bank_vat,
                'nom_banco_ord_ext': is_payment_code_bank_ok and bank_account.bank_name,
                'cta_ordenante': is_payment_code_emitter_ok and payment_account_ord,
                'rfc_emisor_cta_ben': is_payment_code_receiver_ok and self.journal_id.bank_account_id.l10n_mx_edi_vat,
                'cta_beneficiario': is_payment_code_receiver_ok and payment_account_receiver,
            })

            total_payment_amount += pay['monto'] if self.currency_id == company_curr else pay['monto'] * pay['tipo_cambio']

        cfdi_values.update({
            'monto_total_pagos': company_curr.round(total_payment_amount),
            'mxn_digits': company_curr.decimal_places,
        })

        base_line_cfdi_values_mx_curr_list = []
        for payment_cfdi_values in cfdi_values['payment_list']:
            pay_rate = payment_cfdi_values['tipo_cambio'] or 1.0
            base_line_cfdi_values_pay_curr_list = []
            for cfdi_inv_values in payment_cfdi_values['dcto_relationado_list']:
                # Rate.
                inv_rate = cfdi_inv_values['equivalencia'] or 1.0
                to_mxn_rate = pay_rate / inv_rate

                # Build a single synthetic entry per invoice for the BaseP aggregation
                base_line_cfdi_values_pay_curr_list.append({
                    **cfdi_inv_values,
                    **{
                        key: [
                            {
                                **tax_details,
                                'raw_base': (tax_details['base'] / inv_rate) if inv_rate else 0.0,
                                'raw_importe': (tax_details['importe'] / inv_rate) if inv_rate else 0.0,
                            }
                            for tax_details in cfdi_inv_values[key]
                        ]
                        for key in (
                            'retenciones_list',
                            'traslados_list',
                            'local_traslados_list',
                            'local_retenciones_list',
                        )
                    },
                })

                base_lines = cfdi_inv_values['base_lines']
                for base_line in base_lines:
                    base_line_cfdi_values_mx_curr_list.append({
                        **base_line['l10n_mx_cfdi_values'],
                        **{
                            key: [
                                {
                                    **tax_details,
                                    'raw_base': tax_details['raw_base'] * to_mxn_rate,
                                    'raw_importe': tax_details['raw_importe'] * to_mxn_rate,
                                }
                                for tax_details in base_line['l10n_mx_cfdi_values'][key]
                            ]
                            for key in (
                                'retenciones_list',
                                'traslados_list',
                                'local_traslados_list',
                                'local_retenciones_list',
                            )
                        },
                    })
            payment_cfdi_values.update(Document._prepare_document_taxes_data(base_line_cfdi_values_pay_curr_list))
            for target_list in ('retenciones_list', 'traslados_list', 'local_retenciones_list', 'local_traslados_list'):
                for tax_values in payment_cfdi_values[target_list]:
                    tax_values['base'] = float_round(tax_values['raw_base'], precision_digits=6) or 0.000001
                    tax_values['importe'] = float_round(tax_values['raw_importe'], precision_digits=6)

        taxes_data_mx_curr = Document._prepare_document_taxes_data(base_line_cfdi_values_mx_curr_list)

        # Total taxes.
        cfdi_values['total_traslados_base_iva0'] = None
        cfdi_values['total_traslados_impuesto_iva0'] = None
        cfdi_values['total_traslados_base_iva_exento'] = None
        cfdi_values['total_traslados_base_iva8'] = None
        cfdi_values['total_traslados_impuesto_iva8'] = None
        cfdi_values['total_traslados_base_iva16'] = None
        cfdi_values['total_traslados_impuesto_iva16'] = None
        cfdi_values['total_retenciones_isr'] = None
        cfdi_values['total_retenciones_iva'] = None
        cfdi_values['total_retenciones_ieps'] = None

        def update_tax_amount(key, amount):
            if cfdi_values[key] is None:
                cfdi_values[key] = 0.0
            cfdi_values[key] += amount

        def check_transferred_tax_values(tax_values, tag, tax_class, amount):
            return (
                tax_values['impuesto'] == tag
                and tax_values['tipo_factor'] == tax_class
                and company_curr.compare_amounts(tax_values['tasa_o_cuota'] or 0.0, amount) == 0
            )

        for key in (
            'retenciones_list',
            'traslados_list',
            'local_traslados_list',
            'local_retenciones_list',
        ):
            for tax_values in taxes_data_mx_curr[key]:
                if key in ('retenciones_list', 'local_retenciones_list'):
                    if tax_values['impuesto'] == '001':
                        update_tax_amount('total_retenciones_isr', tax_values['raw_importe'])
                    elif tax_values['impuesto'] == '002':
                        update_tax_amount('total_retenciones_iva', tax_values['raw_importe'])
                    elif tax_values['impuesto'] == '003':
                        update_tax_amount('total_retenciones_ieps', tax_values['raw_importe'])
                elif key in ('traslados_list', 'local_traslados_list'):
                    if check_transferred_tax_values(tax_values, '002', 'Tasa', 0.0):
                        update_tax_amount('total_traslados_base_iva0', tax_values['raw_base'])
                        update_tax_amount('total_traslados_impuesto_iva0', tax_values['raw_importe'])
                    elif check_transferred_tax_values(tax_values, '002', 'Exento', 0.0):
                        update_tax_amount('total_traslados_base_iva_exento', tax_values['raw_base'])
                    elif check_transferred_tax_values(tax_values, '002', 'Tasa', 0.08):
                        update_tax_amount('total_traslados_base_iva8', tax_values['raw_base'])
                        update_tax_amount('total_traslados_impuesto_iva8', tax_values['raw_importe'])
                    elif check_transferred_tax_values(tax_values, '002', 'Tasa', 0.16):
                        update_tax_amount('total_traslados_base_iva16', tax_values['raw_base'])
                        update_tax_amount('total_traslados_impuesto_iva16', tax_values['raw_importe'])

        for key in (
            'total_traslados_base_iva0',
            'total_traslados_impuesto_iva0',
            'total_traslados_base_iva_exento',
            'total_traslados_base_iva8',
            'total_traslados_impuesto_iva8',
            'total_traslados_base_iva16',
            'total_traslados_impuesto_iva16',
            'total_retenciones_isr',
            'total_retenciones_iva',
            'total_retenciones_ieps',
        ):
            if cfdi_values[key] is not None:
                cfdi_values[key] = company_curr.round(cfdi_values[key])

        # Cleanup attributes for Exento taxes.
        for target_list in ('retenciones_list', 'traslados_list', 'local_retenciones_list', 'local_traslados_list'):
            for payment_cfdi_values in cfdi_values['payment_list']:
                for tax_values in payment_cfdi_values[target_list]:
                    if tax_values['tipo_factor'] == 'Exento':
                        tax_values['importe'] = None
                for cfdi_inv_values in payment_cfdi_values['dcto_relationado_list']:
                    for tax_values in cfdi_inv_values[target_list]:
                        if tax_values['tipo_factor'] == 'Exento':
                            tax_values['importe'] = None

    # -------------------------------------------------------------------------
    # CFDI: DOCUMENTS
    # -------------------------------------------------------------------------

    def _l10n_mx_edi_cfdi_invoice_document_sent_failed(self, error, cfdi_filename=None, cfdi_str=None):
        """ Create/update the invoice document for 'sent_failed'.
        The parameters are provided by '_l10n_mx_edi_prepare_invoice_cfdi'.

        :param error:           The error.
        :param cfdi_filename:   The optional filename of the cfdi.
        :param cfdi_str:        The optional content of the cfdi.
        :return:                The created/updated document.
        """
        self.ensure_one()

        document_values = {
            'company_id': self.company_id.id,
            'move_id': self.id,
            'invoice_ids': [Command.set(self.ids)],
            'state': 'invoice_sent_failed',
            'sat_state': None,
            'message': error,
        }
        if cfdi_filename and cfdi_str:
            document_values['attachment_id'] = {
                'name': cfdi_filename,
                'raw': cfdi_str,
            }
        return self.env['l10n_mx_edi.document']._create_update_invoice_document_from_invoice(self, document_values)

    def _l10n_mx_edi_cfdi_invoice_document_sent(self, cfdi_filename, cfdi_str):
        """ Create/update the invoice document for 'sent'.
        The parameters are provided by '_l10n_mx_edi_prepare_invoice_cfdi'.

        :param cfdi_filename:   The filename of the cfdi.
        :param cfdi_str:        The content of the cfdi.
        :return:                The created/updated document.
        """
        self.ensure_one()

        document_values = {
            'company_id': self.company_id.id,
            'move_id': self.id,
            'invoice_ids': [Command.set(self.ids)],
            'state': 'invoice_sent',
            'sat_state': 'not_defined',
            'message': None,
            'attachment_id': {
                'name': cfdi_filename,
                'raw': cfdi_str,
                'description': "CFDI",
            },
        }
        return self.env['l10n_mx_edi.document']._create_update_invoice_document_from_invoice(self, document_values)

    def _l10n_mx_edi_cfdi_invoice_document_empty(self):
        """ Create/update the invoice document for an empty invoice.

        :return: The created/updated document.
        """
        self.ensure_one()

        document_values = {
            'company_id': self.company_id.id,
            'move_id': self.id,
            'invoice_ids': [Command.set(self.ids)],
            'state': 'invoice_sent',
            'sat_state': 'skip',
            'message': None,
        }
        return self.env['l10n_mx_edi.document']._create_update_invoice_document_from_invoice(self, document_values)

    def _l10n_mx_edi_cfdi_invoice_document_cancel_requested_failed(self, error, cfdi, cancel_reason):
        """ Create/update the invoice document for 'cancel_requested_failed'.

        :param error:           The error.
        :param cfdi:            The source cfdi attachment to cancel.
        :param cancel_reason:   The reason for this cancel.
        :return:                The created/updated document.
        """
        self.ensure_one()

        document_values = {
            'company_id': self.company_id.id,
            'move_id': self.id,
            'invoice_ids': [Command.set(self.ids)],
            'state': 'invoice_cancel_requested_failed',
            'sat_state': None,
            'message': error,
            'attachment_id': cfdi.attachment_id.id,
            'cancellation_reason': cancel_reason,
        }
        return self.env['l10n_mx_edi.document']._create_update_invoice_document_from_invoice(self, document_values)

    def _l10n_mx_edi_cfdi_invoice_document_cancel_requested(self, cfdi, cancel_reason):
        """ Create/update the invoice document for 'cancel_requested'.

        :param cfdi:            The source cfdi attachment to cancel.
        :param cancel_reason:   The reason for this cancel.
        :return:                The created/updated document.
        """
        self.ensure_one()

        document_values = {
            'company_id': self.company_id.id,
            'move_id': self.id,
            'invoice_ids': [Command.set(self.ids)],
            'state': 'invoice_cancel_requested',
            'sat_state': 'not_defined',
            'message': None,
            'attachment_id': cfdi.attachment_id.id,
            'cancellation_reason': cancel_reason,
        }
        return self.env['l10n_mx_edi.document']._create_update_invoice_document_from_invoice(self, document_values)

    def _l10n_mx_edi_cfdi_invoice_document_cancel_failed(self, error, cfdi, cancel_reason):
        """ Create/update the invoice document for 'cancel_failed'.

        :param error:           The error.
        :param cfdi:            The source cfdi attachment to cancel.
        :param cancel_reason:   The reason for this cancel.
        :return:                The created/updated document.
        """
        self.ensure_one()

        document_values = {
            'company_id': self.company_id.id,
            'move_id': self.id,
            'invoice_ids': [Command.set(self.ids)],
            'state': 'invoice_cancel_failed',
            'sat_state': None,
            'message': error,
            'attachment_id': cfdi.attachment_id.id,
            'cancellation_reason': cancel_reason,
        }
        return self.env['l10n_mx_edi.document']._create_update_invoice_document_from_invoice(self, document_values)

    def _l10n_mx_edi_cfdi_invoice_document_cancel(self, cfdi, cancel_reason):
        """ Create/update the invoice document for 'cancel'.

        :param cfdi:            The source cfdi attachment to cancel.
        :param cancel_reason:   The reason for this cancel.
        :return:                The created/updated document.
        """
        self.ensure_one()

        document_values = {
            'company_id': self.company_id.id,
            'move_id': self.id,
            'invoice_ids': [Command.set(self.ids)],
            'state': 'invoice_cancel',
            'sat_state': 'not_defined',
            'message': None,
            'attachment_id': cfdi.attachment_id.id,
            'cancellation_reason': cancel_reason,
        }
        return self.env['l10n_mx_edi.document']._create_update_invoice_document_from_invoice(self, document_values)

    def _l10n_mx_edi_cfdi_payment_document_sent_pue(self, invoices):
        """ Create/update the invoice document for 'sent_pue'.
        The parameters are provided by '_l10n_mx_edi_prepare_invoice_cfdi'.

        :param invoices:    The invoices reconciled with the payment and sent to the government.
        :return:            The created/updated document.
        """
        self.ensure_one()

        document_values = {
            'company_id': self.company_id.id,
            'move_id': self.id,
            'invoice_ids': [Command.set(invoices.ids)],
            'state': 'payment_sent_pue',
            'sat_state': None,
            'message': None,
        }
        return self.env['l10n_mx_edi.document']._create_update_payment_document(self, document_values)

    def _l10n_mx_edi_cfdi_payment_document_sent_failed(self, error, invoices, cfdi_filename=None, cfdi_str=None):
        """ Create/update the invoice document for 'sent_failed'.
        The parameters are provided by '_l10n_mx_edi_prepare_invoice_cfdi'.

        :param error:           The error.
        :param cfdi:            The cancelled cfdi attachment.
        :param invoices:        The invoices reconciled with the payment and sent to the government.
        :param cfdi_filename:   The optional filename of the cfdi.
        :param cfdi_str:        The optional content of the cfdi.
        :return:                The created/updated document.
        """
        self.ensure_one()

        document_values = {
            'company_id': self.company_id.id,
            'move_id': self.id,
            'invoice_ids': [Command.set(invoices.ids)],
            'state': 'payment_sent_failed',
            'sat_state': None,
            'message': error,
        }
        if cfdi_filename and cfdi_str:
            document_values['attachment_id'] = {
                'name': cfdi_filename,
                'raw': cfdi_str,
            }
        return self.env['l10n_mx_edi.document']._create_update_payment_document(self, document_values)

    def _l10n_mx_edi_cfdi_payment_document_sent(self, invoices, cfdi_filename, cfdi_str):
        """ Create/update the invoice document for 'sent'.
        The parameters are provided by '_l10n_mx_edi_prepare_invoice_cfdi'.

        :param invoices:        The invoices reconciled with the payment and sent to the government.
        :param cfdi_filename:   The filename of the cfdi.
        :param cfdi_str:        The content of the cfdi.
        :return:                The created/updated document.
        """
        self.ensure_one()

        document_values = {
            'company_id': self.company_id.id,
            'move_id': self.id,
            'invoice_ids': [Command.set(invoices.ids)],
            'state': 'payment_sent',
            'sat_state': 'not_defined',
            'message': None,
            'attachment_id': {
                'name': cfdi_filename,
                'raw': cfdi_str,
                'description': "CFDI",
            },
        }
        return self.env['l10n_mx_edi.document']._create_update_payment_document(self, document_values)

    def _l10n_mx_edi_cfdi_payment_document_cancel_failed(self, error, cfdi, cancel_reason):
        """ Create/update the payment document for 'cancel_failed'.

        :param error:           The error.
        :param cfdi:            The source cfdi attachment to cancel.
        :param cancel_reason:   The reason for this cancel.
        :return:                The created/updated document.
        """
        self.ensure_one()

        document_values = {
            'company_id': self.company_id.id,
            'move_id': self.id,
            'invoice_ids': [Command.set(cfdi.invoice_ids.ids)],
            'state': 'payment_cancel_failed',
            'sat_state': None,
            'message': error,
            'attachment_id': cfdi.attachment_id.id,
            'cancellation_reason': cancel_reason,
        }
        return self.env['l10n_mx_edi.document']._create_update_payment_document(self, document_values)

    def _l10n_mx_edi_cfdi_payment_document_cancel(self, cfdi, cancel_reason):
        """ Create/update the payment document for 'cancel'.

        :param cfdi:            The source cfdi attachment to cancel.
        :param cancel_reason:   The reason for this cancel.
        :return:                The created/updated document.
        """
        self.ensure_one()

        document_values = {
            'company_id': self.company_id.id,
            'move_id': self.id,
            'invoice_ids': [Command.set(cfdi.invoice_ids.ids)],
            'state': 'payment_cancel',
            'sat_state': 'not_defined',
            'message': None,
            'attachment_id': cfdi.attachment_id.id,
            'cancellation_reason': cancel_reason,
        }
        return self.env['l10n_mx_edi.document']._create_update_payment_document(self, document_values)

    def _l10n_mx_edi_cfdi_global_invoice_document_sent_failed(self, error, cfdi_filename=None, cfdi_str=None):
        """ Create/update the global invoice document for 'sent_failed'.

        :param error:           The error.
        :param cfdi_filename:   The optional filename of the cfdi.
        :param cfdi_str:        The optional content of the cfdi.
        :return:                The created/updated document.
        """
        document_values = {
            'company_id': self[:1].company_id.id,
            'invoice_ids': [Command.set(self.ids)],
            'state': 'ginvoice_sent_failed',
            'sat_state': None,
            'message': error,
        }
        if cfdi_filename and cfdi_str:
            document_values['attachment_id'] = {
                'name': cfdi_filename,
                'raw': cfdi_str,
            }
        return self.env['l10n_mx_edi.document']._create_update_global_invoice_document_from_invoices(self, document_values)

    def _l10n_mx_edi_cfdi_global_invoice_document_sent(self, cfdi_filename, cfdi_str):
        """ Create/update the global invoice document for 'sent'.

        :param cfdi_filename:   The filename of the cfdi.
        :param cfdi_str:        The content of the cfdi.
        :return:                The created/updated document.
        """
        document_values = {
            'company_id': self[:1].company_id.id,
            'invoice_ids': [Command.set(self.ids)],
            'state': 'ginvoice_sent',
            'sat_state': 'not_defined',
            'message': None,
            'attachment_id': {
                'name': cfdi_filename,
                'raw': cfdi_str,
                'description': "CFDI",
            },
        }
        return self.env['l10n_mx_edi.document']._create_update_global_invoice_document_from_invoices(self, document_values)

    def _l10n_mx_edi_cfdi_global_invoice_document_empty(self):
        """ Create/update the global invoice document for an empty cfdi.

        :return:                The created/updated document.
        """
        document_values = {
            'company_id': self[:1].company_id.id,
            'invoice_ids': [Command.set(self.ids)],
            'state': 'ginvoice_sent',
            'sat_state': 'skip',
            'message': None,
        }
        return self.env['l10n_mx_edi.document']._create_update_global_invoice_document_from_invoices(self, document_values)

    def _l10n_mx_edi_cfdi_global_invoice_document_cancel_failed(self, error, cfdi, cancel_reason):
        """ Create/update the invoice document for 'cancel_failed'.

        :param error:           The error.
        :param cfdi:            The source cfdi attachment to cancel.
        :param cancel_reason:   The reason for this cancel.
        :return:                The created/updated document.
        """
        document_values = {
            'company_id': self[:1].company_id.id,
            'invoice_ids': [Command.set(self.ids)],
            'state': 'ginvoice_cancel_failed',
            'sat_state': None,
            'message': error,
            'attachment_id': cfdi.attachment_id.id,
            'cancellation_reason': cancel_reason,
        }
        return self.env['l10n_mx_edi.document']._create_update_global_invoice_document_from_invoices(self, document_values)

    def _l10n_mx_edi_cfdi_global_invoice_document_cancel(self, cfdi, cancel_reason):
        """ Create/update the invoice document for 'cancel'.

        :param cfdi:            The source cfdi attachment to cancel.
        :param cancel_reason:   The reason for this cancel.
        :return:                The created/updated document.
        """
        self.l10n_mx_edi_cfdi_attachment_id.ensure_one()

        document_values = {
            'company_id': self[:1].company_id.id,
            'invoice_ids': [Command.set(self.ids)],
            'state': 'ginvoice_cancel',
            'sat_state': 'not_defined',
            'message': None,
            'attachment_id': cfdi.attachment_id.id,
            'cancellation_reason': cancel_reason,
        }
        return self.env['l10n_mx_edi.document']._create_update_global_invoice_document_from_invoices(self, document_values)

    # -------------------------------------------------------------------------
    # CFDI: FLOWS
    # -------------------------------------------------------------------------

    def _l10n_mx_edi_cfdi_move_post_cancel(self):
        """ Cancel the current move after the document has been cancelled.
        This method is common between invoice & payment:
        """
        self.ensure_one()

        self.message_post(body=self.env._("The CFDI document has been successfully cancelled."))

        cfdi_values = self.env['l10n_mx_edi.document']._get_company_cfdi_values(self.company_id)
        if cfdi_values['root_company'].l10n_mx_edi_pac_test_env:
            try:
                self._check_fiscal_lock_dates()
                self.line_ids._check_tax_lock_date()

                self.button_draft()
                self.button_cancel()
            except UserError as ue:
                _logger.info("Failed automatic cancellation for journal entry %s (id %s) due to exception: %s", self.name, self.id, ue)

    def _l10n_mx_edi_cfdi_move_update_sat_state(self, document, sat_state, error=None):
        """ Update the SAT state of the document for the current move.

        :param document:    The CFDI document to be updated.
        :param sat_state:   The newly fetched state from the SAT
        :param error:       In case of error, the message returned by the SAT.
        """
        self.ensure_one()

        document.message = None
        if sat_state == 'error' and error:
            document.message = error
            self.message_post(body=error)

        # Automatic cancel for production environment.
        if (
            self.l10n_mx_edi_cfdi_state == 'cancel'
            and self.l10n_mx_edi_cfdi_sat_state == 'cancelled'
            and self.state == 'posted'
        ):
            try:
                self._check_fiscal_lock_dates()
                self.line_ids._check_tax_lock_date()

                self.button_draft()
                self.button_cancel()
            except UserError as ue:
                _logger.info("Failed automatic cancellation for journal entry %s (id %s) due to exception: %s", self.name, self.id, ue)

    def _l10n_mx_edi_cfdi_invoice_retry_send(self):
        """ Retry generating the PDF and CFDI for the current invoice. """
        self.ensure_one()
        self.env['account.move.send']._generate_and_send_invoices(self, sending_methods=['manual'], extra_edis=['mx_cfdi'])

    def _l10n_mx_edi_cfdi_invoice_try_send(self):
        """ Try to generate and send the CFDI for the current invoice. """
        self.ensure_one()

        self = self.with_context(lang=self.partner_id.lang)  # noqa: PLW0642

        if self.state != 'posted' or self.l10n_mx_edi_cfdi_state not in (False, 'cancel', 'global_cancel'):
            return

        # == Check the config ==
        errors = self._l10n_mx_edi_cfdi_check_invoice_config()
        if errors:
            self._l10n_mx_edi_cfdi_invoice_document_sent_failed("\n".join(errors))
            return

        # == Set the post time and commit ==
        if not self.l10n_mx_edi_post_time:
            self.l10n_mx_edi_post_time = self.env['l10n_mx_edi.document']._get_min_of_now_and_document_date(
                self.invoice_date,
                self.company_id.partner_id.commercial_partner_id,
                self.journal_id,
            )

            if self.env['l10n_mx_edi.document']._can_commit():
                self.env.cr.commit()

        # == Lock ==
        self.env['res.company']._with_locked_records(self)

        # == Send ==
        def on_populate(cfdi_values):
            self._l10n_mx_edi_add_invoice_cfdi_values(cfdi_values)

        def on_failure(error, cfdi_filename=None, cfdi_str=None):
            if error == 'empty_cfdi':
                self._l10n_mx_edi_cfdi_invoice_document_empty()
            else:
                self._l10n_mx_edi_cfdi_invoice_document_sent_failed(error, cfdi_filename=cfdi_filename, cfdi_str=cfdi_str)

        def on_success(_cfdi_values, cfdi_filename, cfdi_str, populate_return=None):
            if addendas_post_send := self.l10n_mx_edi_addenda_ids._filter_addenda_by_xml_node('addenda'):
                append_values = self._l10n_mx_edi_cfdi_invoice_append_addendas(
                    cfdi_str=cfdi_str,
                    addendas=addendas_post_send,
                )
                if append_values.get('errors'):
                    self.message_post(body=self.env._("Error when decoding the addenda to append after signing:\n%s",
                                             '\n'.join(append_values['errors'])))
                cfdi_str = append_values['cfdi']

            document = self._l10n_mx_edi_cfdi_invoice_document_sent(cfdi_filename, cfdi_str)
            self.message_post(
                    body=self.env._("The CFDI document was successfully created and signed by the government."),
                    attachment_ids=document.attachment_id.ids,
                )

        qweb_template = self.env['l10n_mx_edi.document']._get_invoice_cfdi_template()
        self.env['l10n_mx_edi.document']._send_api(
            self.company_id,
            qweb_template,
            self._l10n_mx_edi_get_invoice_cfdi_filename(),
            on_populate,
            on_failure,
            on_success,
        )
        if (
            (doc := self.l10n_mx_edi_invoice_document_ids.sorted()[0])
            and doc.state == 'invoice_sent'
            and (original_doc := doc._get_original_document())
            and original_doc.state == 'invoice_sent'
            and self.move_type == 'out_invoice'
            and doc.attachment_origin[:3] == '04|'
        ):
            original_doc.move_id._l10n_mx_edi_cfdi_invoice_try_cancel(original_doc, '01')

    def _l10n_mx_edi_cfdi_invoice_post_cancel(self):
        """ Cancel the current invoice and drop a message in the chatter.
        This method is only there to unify the flows since they are multiple
        ways to cancel an invoice:
        - The user can request a cancellation from Odoo.
        - The user can cancel the invoice from the SAT, then update the SAT state in Odoo.
        """
        self._l10n_mx_edi_cfdi_move_post_cancel()

    def _l10n_mx_edi_cfdi_invoice_try_cancel(self, document, cancel_reason):
        """ Try to cancel the CFDI for the current invoice.

        :param document:        The source invoice document to cancel.
        :param cancel_reason:   The reason for the cancellation.
        """
        self.ensure_one()
        if self.state != 'posted' or self.l10n_mx_edi_cfdi_state != 'sent':
            return

        # == Lock ==
        self.env['res.company']._with_locked_records(self)

        cfdi_values = self.env['l10n_mx_edi.document']._get_company_cfdi_values(self.company_id)
        is_test_env = cfdi_values['root_company'].l10n_mx_edi_pac_test_env

        # == Cancel ==
        def on_failure(error):
            if is_test_env:
                self._l10n_mx_edi_cfdi_invoice_document_cancel_failed(error, document, cancel_reason)
            else:
                self._l10n_mx_edi_cfdi_invoice_document_cancel_requested_failed(error, document, cancel_reason)

        def on_success():
            if is_test_env:
                self._l10n_mx_edi_cfdi_invoice_document_cancel(document, cancel_reason)
            else:
                self._l10n_mx_edi_cfdi_invoice_document_cancel_requested(document, cancel_reason)
            self._l10n_mx_edi_cfdi_invoice_post_cancel()

        document._cancel_api(self.company_id, cancel_reason, on_failure, on_success)

    def _l10n_mx_edi_cfdi_invoice_update_sat_state(self, document, sat_state, error=None):
        """ Update the SAT state of the document for the current invoice.

        :param document:    The CFDI document to be updated.
        :param sat_state:   The newly fetched state from the SAT
        :param error:       In case of error, the message returned by the SAT.
        """
        self.ensure_one()

        # The user manually cancelled the document in the SAT portal.
        if document.state in ('invoice_sent', 'invoice_received') and sat_state == 'cancelled':
            if document.sat_state not in ('valid', 'cancelled', 'skip'):
                document.sat_state = 'skip'

            document = self._l10n_mx_edi_cfdi_invoice_document_cancel(
                document,
                CANCELLATION_REASON_SELECTION[1][0],  # Force '02'.
            )
            document.sat_state = sat_state
            self._l10n_mx_edi_cfdi_invoice_post_cancel()

        # The cancellation request has been approved by the SAT.
        elif document.state == 'invoice_cancel_requested' and sat_state == 'cancelled':
            document.sat_state = sat_state
            document = self._l10n_mx_edi_cfdi_invoice_document_cancel(
                document,
                document.cancellation_reason,
            )
            document.sat_state = 'cancelled'
            self._l10n_mx_edi_cfdi_invoice_post_cancel()

        else:
            document.sat_state = sat_state

        self._l10n_mx_edi_cfdi_move_update_sat_state(document, sat_state, error=error)

    def _l10n_mx_edi_cfdi_invoice_get_reconciled_payments_values(self):
        """ Compute the residual amounts before/after each payment reconciled with the current invoices.

        :return: A mapping invoice => dictionary containing:
            * payment:                      The account.move of the payment.
            * payment_values:               A dictionary containing:
                * reconciled_amount:            The reconciled amount.
                * amount_residual_before:       The residual amount before reconciliation.
                * amount_residual_after:        The residual_amount after reconciliation.
                * and other information
            * compensation_payment_values:  A dictionary similar to payment_values but for the compensation
                                            amounts for each payment.
        """
        # Only consider the invoices already signed.
        invoices = self\
            .filtered(lambda x: x._l10n_mx_edi_is_cfdi_invoice() and x.l10n_mx_edi_cfdi_state == 'sent')\
            .sorted()

        # Collect the reconciled amounts.
        reconciliation_values = {}
        default_amount_values = {
            'invoice_amount_currency': 0.0,
            'balance': 0.0,
            'payment_amount_currency': 0.0,
        }
        for invoice in invoices:
            pay_rec_lines = invoice.line_ids\
                .filtered(lambda line: line.account_type in ('asset_receivable', 'liability_payable'))

            # Track the reconciliation to each payment because they have to be sent too.
            reconciliation_values[invoice] = {
                'payments': defaultdict(lambda: {
                    'payment': dict(**default_amount_values),
                    'compensation': dict(**default_amount_values),
                    'other_residual': 0.0,
                }),
            }

            # If a reconciliation has been made with something that is not a payment like a credit note, it has to be taken into account
            # when computing the residual amounts before and after.
            other_residual = 0.0
            for counterpart_field, field in (('credit', 'debit'), ('debit', 'credit')):
                for partial in pay_rec_lines[f'matched_{counterpart_field}_ids'].sorted(lambda x: (
                    x[f'{counterpart_field}_move_id'].invoice_date or x[f'{counterpart_field}_move_id'].date,
                    x[f'{counterpart_field}_move_id'].id,
                )):
                    counterpart_line = partial[f'{counterpart_field}_move_id']
                    counterpart_move = counterpart_line.move_id

                    if counterpart_move._l10n_mx_edi_is_cfdi_payment():
                        # Special case when a 'counterpart_line' is set as a compensation for factoring payments. In this cases
                        # we put the amounts on a separate dict from the normal payment lines
                        pay = reconciliation_values[invoice]['payments'][counterpart_move]
                        pay['other_residual'] += other_residual
                        other_residual = 0.0

                        if counterpart_line.l10n_mx_edi_factoring_type == 'compensation':
                            pay_results = pay['compensation']
                        else:
                            pay_results = pay['payment']
                        pay_results['invoice_amount_currency'] += partial[f'{field}_amount_currency']
                        stmt_line = counterpart_line.statement_line_id
                        if stmt_line and stmt_line.currency_id != counterpart_line.currency_id:
                            result = stmt_line._get_accounting_amounts_and_currencies()
                            journal_amount = result[2]
                            company_amount = result[4]
                            rate = abs(journal_amount) / abs(company_amount) if company_amount else 0.0
                            pay_results['payment_amount_currency'] += partial[f'{counterpart_field}_amount_currency'] * rate
                        else:
                            pay_results['payment_amount_currency'] += partial[f'{counterpart_field}_amount_currency']
                        pay_results['balance'] += partial.amount

                    else:
                        other_residual += partial[f'{field}_amount_currency']

        # Compute the chain of payments.
        results = {}
        for invoice, invoice_values in reconciliation_values.items():
            number_of_payments = 1
            payment_values = invoice_values['payments']
            invoice_results = results[invoice] = []
            residual = invoice.amount_total
            for pay, pay_results in sorted(list(payment_values.items()), key=lambda x: x[0].date):
                payment = pay_results['payment']
                reconciled_invoice_amount = payment['invoice_amount_currency']

                residual -= pay_results['other_residual']
                payment_vals = {
                    'payment': pay,
                    'payment_values': {
                        **payment,
                        'invoice': invoice,
                        'number_of_payments': number_of_payments,
                        'reconciled_amount': reconciled_invoice_amount,
                        'amount_residual_before': residual,
                        'amount_residual_after': residual - reconciled_invoice_amount,
                    }
                }
                number_of_payments += 1
                residual -= reconciled_invoice_amount

                if not invoice.currency_id.is_zero(pay_results['compensation']['invoice_amount_currency']):
                    compensation = pay_results['compensation']
                    compensation_rec_amount = compensation['invoice_amount_currency']
                    payment_vals['compensation_values'] = {
                        **compensation,
                        'invoice': invoice,
                        'number_of_payments': number_of_payments,
                        'reconciled_amount': compensation_rec_amount,
                        'amount_residual_before': residual,
                        'amount_residual_after': residual - compensation_rec_amount,
                    }
                    number_of_payments += 1
                    residual -= compensation_rec_amount

                invoice_results.append(payment_vals)

        return results

    def _l10n_mx_edi_cfdi_payment_get_reconciled_invoice_values(self):
        """ Compute the amounts to send to the PAC from the current payments.

        :return: A mapping payment => dictionary containing:
            * invoices:                 The reconciled invoices.
            * invoice_results:          A list of dicts containing:
                'is_compensation':          Boolean parameter that defines if this group of payment values
                                            should be considered compensations or not.
                'payment_values':           A list of payment values, that could be normal payment values or
                                            compensation payment values.
                                            See '_l10n_mx_edi_cfdi_invoice_get_reconciled_payments_values'.
        """
        # Find all invoices linked to the current payments.
        results = {}
        payments = self.filtered(lambda x: x._l10n_mx_edi_is_cfdi_payment() and x.l10n_mx_edi_cfdi_state != 'cancel')
        all_invoices = self.env['account.move']
        exchange_move_map = {}
        exchange_move_balances = defaultdict(lambda: defaultdict(lambda: {'payment': 0.0, 'compensation': 0.0}))
        for payment in payments:
            # Only the fully reconciled payments need to be sent. We ignore the line for factoring costs in case this payment contains factoring.
            pay_rec_lines = payment.line_ids\
                .filtered(lambda line: line.account_type in ('asset_receivable', 'liability_payable') and line.l10n_mx_edi_factoring_type != 'factoring_cost')
            if (
                any(not x.reconciled for x in pay_rec_lines)
                or False in payment.line_ids.statement_line_id.mapped('is_reconciled')
                or False in payment.origin_payment_id.mapped('is_reconciled')
            ):
                continue

            # The payments must only be sent when all reconciled invoices are sent.
            skip = False
            invoices = self.env['account.move']
            for counterpart_field, field in (('debit', 'credit'), ('credit', 'debit')):
                for partial in pay_rec_lines[f'matched_{counterpart_field}_ids'].sorted(lambda x: not x.exchange_move_id):
                    counterpart_line = partial[f'{counterpart_field}_move_id']
                    counterpart_move = counterpart_line.move_id

                    if counterpart_move in exchange_move_map:
                        is_compensation = partial[f'{field}_move_id'].l10n_mx_edi_factoring_type == 'compensation'
                        exchange_payment_type = 'compensation' if is_compensation else 'payment'
                        exchange_move_balances[payment][exchange_move_map[counterpart_move]][exchange_payment_type] += partial.amount
                        continue

                    if not counterpart_move.is_invoice() or not counterpart_move.l10n_mx_edi_cfdi_state:
                        skip = True
                        break

                    if partial.exchange_move_id:
                        exchange_move_map[partial.exchange_move_id] = counterpart_move

                    invoices |= counterpart_move

            if skip:
                continue

            all_invoices |= invoices

            reconciled_amls = pay_rec_lines.matched_debit_ids.debit_move_id \
                              + pay_rec_lines.matched_credit_ids.credit_move_id
            invoices = reconciled_amls.move_id.filtered(lambda x: x._l10n_mx_edi_is_cfdi_invoice())
            if any(
                not invoice.l10n_mx_edi_cfdi_state
                for invoice in invoices
            ):
                continue

            all_invoices |= invoices
            results[payment] = {
                'invoices': invoices,
                'invoice_results': [],
            }

        # Compute the amounts to send for each invoice.
        reconciled_invoice_values = all_invoices._l10n_mx_edi_cfdi_invoice_get_reconciled_payments_values()

        # We need to diferentiate between what is a payment and what is a compensation
        values_by_payment = defaultdict(lambda: {
            'payments': [],
            'compensations': []
        })
        for invoice, pay_results_list in reconciled_invoice_values.items():
            for pay_results in pay_results_list:
                payment = pay_results['payment']
                if payment not in results:
                    continue

                pay_results['payment_values']['payment_exchange_balance'] = exchange_move_balances[payment][invoice]['payment']
                values_by_payment[payment]['payments'].append(pay_results['payment_values'])
                if pay_results.get('compensation_values'):
                    pay_results['compensation_values']['payment_exchange_balance'] = exchange_move_balances[payment][invoice]['compensation']
                    values_by_payment[payment]['compensations'].append(pay_results['compensation_values'])

        for payment, values in values_by_payment.items():
            if values['payments']:
                results[payment]['invoice_results'].append({
                    'is_compensation': False,
                    'payment_values': values['payments']
                })
            # We put the compensation payment values last as they should be at the end on the generated CFDI
            if values['compensations']:
                results[payment]['invoice_results'].append({
                    'is_compensation': True,
                    'payment_values': values['compensations']
                })

        return results

    def l10n_mx_edi_cfdi_invoice_try_update_payment(self, pay_results):
        """ Update the CFDI state of the current payment.

        :param pay_results: The amounts to consider for each invoice.
                            See '_l10n_mx_edi_cfdi_payment_get_reconciled_invoice_values'.
        """
        self.ensure_one()

        last_document = self.l10n_mx_edi_payment_document_ids.sorted()[:1]
        invoices = pay_results['invoices']

        # == Check PUE/PPD ==
        if (
            not last_document
            and 'PPD' not in set(invoices.mapped('l10n_mx_edi_payment_policy'))
        ):
            self._l10n_mx_edi_cfdi_payment_document_sent_pue(invoices)
            return

        # == Retry a cancellation flow ==
        if last_document.state == 'payment_cancel_failed':
            last_document._action_retry_payment_try_cancel()
            return

        qweb_template = self.env['l10n_mx_edi.document']._get_payment_cfdi_template()

        # == Lock ==
        self.env['res.company']._with_locked_records(self + invoices)

        # == Send ==
        def on_populate(cfdi_values):
            pay_results['invoices'] = pay_results['invoices'].filtered(lambda m: m.l10n_mx_edi_payment_policy != 'PUE')
            for invoice_result in pay_results['invoice_results']:
                invoice_result['payment_values'] = list(filter(lambda x: x['invoice'] in pay_results['invoices'], invoice_result['payment_values']))
            pay_results['invoice_results'] = [r for r in pay_results['invoice_results'] if r['payment_values']]
            self._l10n_mx_edi_add_payment_cfdi_values(cfdi_values, pay_results)

        def on_failure(error, cfdi_filename=None, cfdi_str=None):
            self._l10n_mx_edi_cfdi_payment_document_sent_failed(error, invoices, cfdi_filename=cfdi_filename, cfdi_str=cfdi_str)

        def on_success(_cfdi_values, cfdi_filename, cfdi_str, populate_return=None):
            self._l10n_mx_edi_cfdi_payment_document_sent(invoices, cfdi_filename, cfdi_str)

        cfdi_filename = f'{self.journal_id.code}-{self.name}-MX-Payment-20.xml'.replace('/', '')
        self.env['l10n_mx_edi.document']._send_api(
            self.company_id,
            qweb_template,
            cfdi_filename,
            on_populate,
            on_failure,
            on_success,
        )
        if (
            (new_doc := self.l10n_mx_edi_payment_document_ids.sorted()[0])
            and new_doc.state == 'payment_sent'
            and (original_doc := new_doc._get_original_document())
            and original_doc.state == 'payment_sent'
        ):
            original_doc.move_id._l10n_mx_edi_cfdi_invoice_try_cancel_payment(original_doc)

    def _l10n_mx_edi_cfdi_payment_post_cancel(self):
        """ Cancel the current payment and drop a message in the chatter.
        This method is only there to unify the flows since they are multiple
        ways to cancel a payment:
        - The user can request a cancellation from Odoo.
        - The user can cancel the payment from the SAT, then update the SAT state in Odoo.
        """
        self._l10n_mx_edi_cfdi_move_post_cancel()

    def _l10n_mx_edi_cfdi_invoice_try_cancel_payment(self, document):
        """ Cancel the CFDI payment document passed as parameter

        :param document: The source payment document to cancel.
        """
        self.ensure_one()
        substitution_doc = document._get_substitution_document()
        cancel_uuid = substitution_doc.attachment_uuid
        cancel_reason = '01' if cancel_uuid else '02'

        # == Lock ==
        self.env['res.company']._with_locked_records(self + document.invoice_ids)

        # == Cancel ==
        def on_failure(error):
            self._l10n_mx_edi_cfdi_payment_document_cancel_failed(error, document, cancel_reason)

        def on_success():
            self._l10n_mx_edi_cfdi_payment_document_cancel(document, cancel_reason)
            self._l10n_mx_edi_cfdi_payment_post_cancel()

        document._cancel_api(self.company_id, cancel_reason, on_failure, on_success)

    def _l10n_mx_edi_cfdi_invoice_get_payments_diff(self):
        results = {
            'to_remove': defaultdict(list),
            'to_process': [],
            'need_update': set(),
        }

        # Find the payments reconciled with the current invoices.
        reconciled_invoice_values = self._l10n_mx_edi_cfdi_invoice_get_reconciled_payments_values()

        # Collect the reconciled invoices for each payment that have been sent to the SAT.
        sat_sent_payments = defaultdict(set)

        # All payments currently reconciled with the current invoices.
        all_payments = self.env['account.move']
        for invoice, pay_results_list in reconciled_invoice_values.items():
            payments = self.env['account.move']
            for pay_results in pay_results_list:
                if pay_results['payment'].date <= fields.Date.context_today(self):
                    payments |= pay_results['payment']
            all_payments |= payments

            commands = []
            for doc in invoice.l10n_mx_edi_invoice_document_ids:
                # Collect the payments that are no longer reconciled with the invoices.
                if (
                    doc.state.startswith('payment_')
                    and doc.state not in ('payment_sent', 'payment_cancel')
                    and doc.move_id not in payments
                ):
                    commands.append(Command.delete(doc.id))

                # Track the payment previously sent to the SAT.
                if doc.move_id not in sat_sent_payments and doc.state in ('payment_sent', 'payment_sent_pue', 'payment_cancel'):
                    sat_sent_payments[doc.move_id] = set(doc.invoice_ids)
            if commands:
                results['to_remove'][invoice] = commands

        # Update the payments.
        reconciled_payment_values = all_payments._l10n_mx_edi_cfdi_payment_get_reconciled_invoice_values()
        for payment, pay_results in reconciled_payment_values.items():
            last_document = payment.l10n_mx_edi_payment_document_ids.sorted()[:1]
            invoices = pay_results['invoices']

            if last_document.state == 'payment_sent_pue':
                continue

            # Check if a reconciliation is missing.
            if set(invoices) != sat_sent_payments[payment]:
                for invoice in sat_sent_payments[payment]:
                    results['need_update'].add(invoice)

            invoices = invoices.filtered(lambda move: move.l10n_mx_edi_payment_policy != 'PUE')
            # Check if something changed in the already sent payment.
            if last_document.state == 'payment_sent':
                current_uuids = set(invoices.mapped('l10n_mx_edi_cfdi_uuid'))
                previous_uuids = set()
                if not last_document.attachment_id.raw:
                    _logger.warning(
                        "Payment document (id %s) has an empty attachment (id %s)",
                        last_document.id,
                        last_document.attachment_id.id,
                    )
                    continue
                cfdi_node = etree.fromstring(last_document.attachment_id.raw.content)
                for node in cfdi_node.xpath("//*[local-name()='DoctoRelacionado']"):
                    previous_uuids.add(node.attrib['IdDocumento'])
                if current_uuids == previous_uuids:
                    continue

            results['to_process'].append((payment, pay_results))

        return results

    def l10n_mx_edi_cfdi_invoice_try_update_payments(self):
        """ Try to update the state of payments for the current invoices. """
        payments_diff = self._l10n_mx_edi_cfdi_invoice_get_payments_diff()

        # Cleanup the payments that are no longer reconciled with the invoices.
        for invoice, commands in payments_diff['to_remove'].items():
            invoice.l10n_mx_edi_invoice_document_ids = commands

        # Update the payments.
        for payment, pay_results in payments_diff['to_process']:
            payment.l10n_mx_edi_cfdi_invoice_try_update_payment(pay_results)

    def _l10n_mx_edi_cfdi_payment_try_send(self):
        """ Sending of the current payment.
        """
        self.ensure_one()
        reconciled_payment_values = self._l10n_mx_edi_cfdi_payment_get_reconciled_invoice_values()
        for payment, pay_results in reconciled_payment_values.items():
            payment.l10n_mx_edi_cfdi_invoice_try_update_payment(pay_results)

    def _l10n_mx_edi_cfdi_payment_update_sat_state(self, document, sat_state, error=None):
        """ Update the SAT state of the document for the current payment.

        :param document:    The CFDI document to be updated.
        :param sat_state:   The newly fetched state from the SAT
        :param error:       In case of error, the message returned by the SAT.
        """
        self.ensure_one()

        # The user manually cancelled the document in the SAT portal.
        if document.state == 'payment_sent' and sat_state == 'cancelled':
            if document.sat_state not in ('valid', 'cancelled', 'skip'):
                document.sat_state = 'skip'

            document = self._l10n_mx_edi_cfdi_payment_document_cancel(
                document,
                CANCELLATION_REASON_SELECTION[1][0],  # Force '02'.
            )
            document.sat_state = sat_state
            self._l10n_mx_edi_cfdi_payment_post_cancel()

        else:
            document.sat_state = sat_state

        self._l10n_mx_edi_cfdi_move_update_sat_state(document, sat_state, error=error)

    def _l10n_mx_edi_cfdi_global_invoice_try_send(self, document_date, periodicity='04', origin=None):
        """ Create a CFDI global invoice for multiple invoices.

        :param periodicity:     The value to fill the 'Periodicidad' value.
        :param origin:          The origin of the GI when cancelling an existing one.
        """
        AccountTax = self.env['account.tax']
        Document = self.env['l10n_mx_edi.document']

        # == Check the config ==
        errors = []
        invoices = self._l10n_mx_edi_check_invoices_for_global_invoice(origin=origin)
        for invoice in invoices:
            errors += invoice._l10n_mx_edi_cfdi_check_invoice_config()
        if errors:
            invoices._l10n_mx_edi_cfdi_global_invoice_document_sent_failed("\n".join(set(errors)))
            return

        # == Set the post time and commit ==
        invoices_without_post_time = self.filtered(lambda m: not m.l10n_mx_edi_post_time)
        if invoices_without_post_time:
            for invoice in invoices_without_post_time:
                invoice.l10n_mx_edi_post_time = self.env['l10n_mx_edi.document']._get_min_of_now_and_document_date(
                    invoice.invoice_date,
                    invoice.company_id.partner_id.commercial_partner_id,
                    invoice.journal_id,
                )
            if self.env['l10n_mx_edi.document']._can_commit():
                self.env.cr.commit()

        # == Lock ==
        self.env['res.company']._with_locked_records(invoices)

        # == Send ==
        def on_populate(cfdi_values):
            all_base_lines = []
            for invoice in invoices:
                # The refund are managed by the invoice.
                if invoice.reversed_entry_id:
                    continue

                # Dispatch the negative lines on the invoice itself.
                base_lines, tax_lines = invoice._l10n_mx_edi_get_invoice_cfdi_base_lines()
                base_lines = Document._add_and_round_tax_details(base_lines, self.company_id, tax_lines=tax_lines)
                dispatched_lines = Document._dispatch_negative_base_lines(base_lines, self.company_id)
                if dispatched_lines['remaining_negative_base_lines']:
                    cfdi_values['errors'] = [self.env._("Failed to distribute some negative lines")]
                    return

                base_lines = dispatched_lines['base_lines']
                for base_line in base_lines:
                    base_line['document_name'] = invoice.name

                # Manage the refunds.
                for refund in invoice.reversal_move_ids:

                    # Dispatch the positive lines on the refund itself.
                    refund_base_lines, refund_tax_lines = refund._l10n_mx_edi_get_invoice_cfdi_base_lines()
                    refund_base_lines = Document._add_and_round_tax_details(refund_base_lines, self.company_id, tax_lines=refund_tax_lines)
                    refund_dispatched_lines = Document._dispatch_negative_base_lines(refund_base_lines, self.company_id)
                    if refund_dispatched_lines['remaining_negative_base_lines']:
                        cfdi_values['errors'] = [self.env._("Failed to distribute some negative lines")]
                        return

                    # Dispatch the remaining negative lines from the refund on the invoice.
                    refund_base_lines = AccountTax._turn_base_lines_is_refund_flag_off(refund_dispatched_lines['base_lines'])
                    dispatched_lines = Document._dispatch_negative_base_lines(base_lines + refund_base_lines, self.company_id)
                    if dispatched_lines['remaining_negative_base_lines']:
                        cfdi_values['errors'] = [self.env._("Failed to distribute some negative lines")]
                        return

                    base_lines = dispatched_lines['base_lines']
                all_base_lines += base_lines

            # Nothing left. Everything is refunded or empty.
            base_lines = [x for x in all_base_lines if not x['currency_id'].is_zero(x['tax_details']['raw_total_excluded_currency'])]
            if not base_lines:
                cfdi_values['errors'] = ['empty_cfdi']
                return

            AccountTax._round_base_lines_tax_details(base_lines, cfdi_values['company'])
            _biggest_amount_total, biggest_used_payment_method = max(
                [
                    (sum(sub_invoices.mapped('amount_total')), payment_method)
                    for payment_method, sub_invoices in invoices.grouped('l10n_mx_edi_payment_method_id').items()
                ],
                key=lambda x: x[0],
            )
            Document._add_payment_policy_cfdi_values(cfdi_values, payment_method=biggest_used_payment_method)

            # issued address
            journal = invoices.journal_id
            if (
                'l10n_mx_address_issued_id' in journal._fields
                and journal.l10n_mx_address_issued_id
            ):
                cfdi_values['issued_address'] = journal.l10n_mx_address_issued_id

            Document._add_global_invoice_cfdi_values(
                cfdi_values,
                base_lines,
                document_date,
                periodicity=periodicity,
                origin=origin,
            )

            self.env['res.company']._with_locked_records(cfdi_values['sequence'])
            return cfdi_values['sequence']

        def on_failure(error, cfdi_filename=None, cfdi_str=None):
            if error == 'empty_cfdi':
                self._l10n_mx_edi_cfdi_global_invoice_document_empty()
            else:
                self._l10n_mx_edi_cfdi_global_invoice_document_sent_failed(error, cfdi_filename=cfdi_filename, cfdi_str=cfdi_str)

        def on_success(cfdi_values, cfdi_filename, cfdi_str, populate_return=None):
            # Consume the next sequence number.
            self.env['l10n_mx_edi.document']._consume_global_invoice_cfdi_sequence(populate_return, int(cfdi_values['folio']))

            # Create the document.
            document = self._l10n_mx_edi_cfdi_global_invoice_document_sent(cfdi_filename, cfdi_str)

            # Chatters.
            for invoice in self:
                invoice.message_post(
                    body=self.env._("The Global CFDI document was successfully created and signed by the government."),
                    attachment_ids=document.attachment_id.ids,
                )

        qweb_template = self.env['l10n_mx_edi.document']._get_invoice_cfdi_template()
        cfdi_filename = f"{self.journal_id.code}-MX-Global-Invoice-4.0.xml".replace('/', '')
        self.env['l10n_mx_edi.document']._send_api(
            self.company_id,
            qweb_template,
            cfdi_filename,
            on_populate,
            on_failure,
            on_success,
        )
        if (
            origin
            and (new_doc := invoices[0].l10n_mx_edi_invoice_document_ids.sorted()[0])
            and new_doc.state == 'ginvoice_sent'
            and (original_doc := new_doc._get_original_document())
            and original_doc.state == 'ginvoice_sent'
        ):
            original_doc.invoice_ids._l10n_mx_edi_cfdi_global_invoice_try_cancel(original_doc, '01')

    def _l10n_mx_edi_cfdi_global_invoice_post_cancel(self):
        """ Cancel the current payment and drop a message in the chatter.
        This method is only there to unify the flows since they are multiple
        ways to cancel a payment:
        - The user can request a cancellation from Odoo.
        - The user can cancel the payment from the SAT, then update the SAT state in Odoo.
        """

        for record in self:
            record.message_post(body=self.env._("The Global CFDI document has been successfully cancelled."))

    def _l10n_mx_edi_cfdi_global_invoice_try_cancel(self, document, cancel_reason):
        """ Create a CFDI global invoice for multiple invoices.

        :param document:        The Global invoice document to cancel.
        :param cancel_reason:   The reason for the cancellation.
        """
        # == Lock ==
        self.env['res.company']._with_locked_records(self)

        # == Cancel ==
        def on_failure(error):
            self._l10n_mx_edi_cfdi_global_invoice_document_cancel_failed(error, document, cancel_reason)

        def on_success():
            self._l10n_mx_edi_cfdi_global_invoice_document_cancel(document, cancel_reason)
            self._l10n_mx_edi_cfdi_global_invoice_post_cancel()

        document._cancel_api(self.company_id, cancel_reason, on_failure, on_success)

    def _l10n_mx_edi_cfdi_global_invoice_update_document_sat_state(self, document, sat_state, error=None):
        """ Update the SAT state of the document for the current global invoice.

        :param document:    The CFDI document to be updated.
        :param sat_state:   The newly fetched state from the SAT
        :param error:       In case of error, the message returned by the SAT.
        """
        # The user manually cancelled the document in the SAT portal.
        if document.state == 'ginvoice_sent' and sat_state == 'cancelled':
            if document.sat_state not in ('valid', 'cancelled', 'skip'):
                document.sat_state = 'skip'

            document = self._l10n_mx_edi_cfdi_global_invoice_document_cancel(
                document,
                CANCELLATION_REASON_SELECTION[1][0],  # Force '02'.
            )
            document.sat_state = sat_state
            self._l10n_mx_edi_cfdi_global_invoice_post_cancel()
        else:
            document.sat_state = sat_state

        document.message = None
        if sat_state == 'error' and error:
            document.message = error
            self.invoice_ids._message_log_batch(bodies={invoice.id: error for invoice in self.invoice_ids})

    def l10n_mx_edi_action_create_global_invoice(self):
        """ Action to open the wizard allowing to create a global invoice CFDI document for the
        selected invoices.

        :return: An action to open the wizard.
        """
        if self.env.company.country_code != "MX":
            raise UserError(self.env._("You cannot create a global invoice as your company is not Mexican."))

        return {
            'name': self.env._("Create Global Invoice"),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'l10n_mx_edi.global_invoice.create',
            'target': 'new',
            'context': {'default_move_ids': [Command.set(self.ids)]},
        }

    def l10n_mx_edi_cfdi_try_sat(self):
        self.ensure_one()
        if self._l10n_mx_edi_is_cfdi_invoice() or self._l10n_mx_edi_is_cfdi_bill():
            documents = self.l10n_mx_edi_invoice_document_ids
        elif self._l10n_mx_edi_is_cfdi_payment():
            documents = self.l10n_mx_edi_payment_document_ids
        else:
            return

        # sudo: pos_order_ids might appear in the domain and the accountant user might not have access to PoS
        documents = documents.sudo().filtered_domain(documents._get_update_sat_status_domain(from_cron=False)).sudo(flag=False)
        for document in documents:
            document._update_sat_state()

    # -------------------------------------------------------------------------
    # CFDI: IMPORT
    # -------------------------------------------------------------------------

    def _l10n_mx_edi_import_cfdi_check_can_import(self, invoice, cfdi_vals):
        """Validate if CFDI can be imported into invoice"""
        if invoice.l10n_mx_edi_cfdi_attachment_id:
            return self.env._("Current document is already associated with a CFDI.")

        if not cfdi_vals or cfdi_vals['cfdi_node'].get("TipoDeComprobante") not in ('I', 'E'):
            return self.env._("The imported file is not a valid CFDI Invoice.")

        if invoice.journal_id.type not in ("sale", "purchase"):
            return self.env._("Import of CFDI Invoice documents is only supported on purchase or sale journals.")

        is_outgoing_invoice = invoice.journal_id.type == 'sale'
        rfc = cfdi_vals['supplier_rfc'] if is_outgoing_invoice else cfdi_vals['customer_rfc']
        if not rfc:
            return self.env._("Couldn't find the institution RFC on the imported CFDI.")

        root_company = invoice.company_id.sudo().parent_ids[::-1].filtered("partner_id.vat")[:1] or invoice.company_id
        rfc, _country_code = root_company.partner_id._run_vat_checks(root_company.country_id, rfc, validation='setnull')
        if root_company.partner_id.vat != rfc:
            return Markup("<br>").join([
                self.env._("The RFC doesn't match with document's company VAT."),
                self.env._("Verify if you are importing it on the correct company or journal."),
            ])

    def _l10n_mx_edi_import_cfdi_retrieve_customer_search_plan(self, import_values):
        ResPartner = self.env['res.partner']
        return [
            ResPartner._import_retrieve_customer_from_vat,
            ResPartner._import_retrieve_customer_from_name,
        ]

    def _l10n_mx_edi_import_cfdi_retrieve_customer(self, import_values):
        customer_values = import_values['customer_values'] = {}
        cfdi_values = import_values['cfdi_values']
        is_sale_invoice = import_values['journal_type'] == 'sale'

        # Collect Customer values
        customer_data = cfdi_values['receptor_data'] if is_sale_invoice else cfdi_values['emisor_data']
        rfc = cfdi_values['customer_rfc'] if is_sale_invoice else cfdi_values['supplier_rfc']
        num_reg_id_trib = customer_data['num_reg_id_trib']
        customer_values.update({
            'name': customer_data['name'],
            'rfc': rfc,
            'num_reg_id_trib': num_reg_id_trib,
            'vat': num_reg_id_trib if is_sale_invoice and rfc in ('XEXX010101000', 'XAXX010101000') else rfc,
            'zip': customer_data['zip_code'],
        })

        self.env['res.partner']._import_retrieve_customer(
            search_plan=self._l10n_mx_edi_import_cfdi_retrieve_customer_search_plan(import_values),
            company=import_values['company'],
            customer_values_list=[customer_values],
        )

        if customer := customer_values.get('customer'):
            import_values['invoice_values']['partner_id'] = customer.id

    def _l10n_mx_edi_import_cfdi_create_or_update_customer(self, import_values):
        customer_values = import_values['customer_values']
        customer = customer_values.get('customer')
        zip_code = customer_values['zip']
        rfc = customer_values['rfc']
        is_generic_rfc = rfc in ('XEXX010101000', 'XAXX010101000')
        if customer:
            if not customer.zip and zip_code and not is_generic_rfc:
                customer.write({'zip': zip_code})
            return

        if not import_values['customer_values']['name']:
            import_values['messages'].append(self.env._("Failed to find/create partner from given invoice CFDI."))
            return

        country_id = rfc != 'XEXX010101000' and self.env.ref('base.mx', raise_if_not_found=False).id
        create_vals = {'name': customer_values['name'], 'country_id': country_id}

        if zip_code and not is_generic_rfc:
            create_vals['zip'] = zip_code
        if not is_generic_rfc:
            create_vals['vat'] = rfc
        elif rfc == 'XEXX010101000':
            export_fiscal_position = import_values['company']._l10n_mx_edi_get_foreign_customer_fiscal_position()
            create_vals['property_account_position_id'] = export_fiscal_position.id

        customer_values['customer'] = self.env['res.partner'].create(create_vals)
        import_values['invoice_values']['partner_id'] = customer_values['customer'].id
        import_values['messages'].append(self.env._('Created new contact for %s from invoice CFDI', customer_values['customer'].name))

    def _l10n_mx_edi_import_cfdi_add_total_taxes_values(self, import_values):
        total_taxes_values = import_values['total_taxes_values'] = {}
        cfdi_values = import_values['cfdi_values']

        type_tax_use = 'sale' if import_values['journal_type'] == 'sale' else 'purchase'

        for total_tax_values in cfdi_values['total_taxes_values']:
            factor_type, amount, amount_type, tax_type = total_tax_values['tax_key']
            values = total_taxes_values.setdefault(total_tax_values['tax_key'], {
                'type_tax_use': type_tax_use,
                'l10n_mx_factor_type': factor_type,
                'amount': amount,
                'amount_type': amount_type,
                'l10n_mx_tax_type': tax_type,
                'base_amount_currency': 0,
                'tax_amount_currency': 0,
                'related_taxes_values': []
            })
            values['base_amount_currency'] += total_tax_values['base_amount_currency']
            values['tax_amount_currency'] += total_tax_values['tax_amount_currency']

    def _l10n_mx_edi_import_cfdi_add_invoice_lines_values(self, import_values):
        invoice_lines_values = import_values['invoice_lines_values'] = []
        currency = import_values['currency']
        for concepto in import_values['cfdi_values']['conceptos']:
            discount_amount = concepto['discount_amount']
            gross_before_discount = concepto['subtotal_before_discount']
            discount_percent = 0
            if not currency.is_zero(discount_amount) and gross_before_discount:
                discount_percent = discount_amount / gross_before_discount * 100

            invoice_line_values = {
                **import_values,
                'line_values': {
                    'name': " | ".join(filter(None, (concepto['description'], concepto['code']))),
                    'quantity': concepto['quantity'],
                    'price_unit': concepto['price_unit'],
                    'discount': discount_percent,
                    'l10n_mx_edi_tax_object': concepto['tax_object'],
                },
                'concepto_values': {**concepto},
            }
            self._l10n_mx_edi_import_cfdi_invoice_line_add_product_values(invoice_line_values)
            self._l10n_mx_edi_import_cfdi_invoice_line_add_taxes_values(invoice_line_values)
            if any(
                tax_data.get('missing_from_totals')
                for tax_data in invoice_line_values['concepto_values']['concepto_taxes_data']
            ):
                import_values['are_taxes_complete'] = False
            invoice_lines_values.append(invoice_line_values)

    def _l10n_mx_edi_import_cfdi_invoice_line_add_product_values(self, invoice_line_values):
        concepto_values = invoice_line_values['concepto_values']
        partner = invoice_line_values['customer_values'].get('customer')
        invoice_line_values['product_values'] = {
            'name': concepto_values['product_name'],
            'default_code': concepto_values['code'],
            'unspsc_code': concepto_values['unspsc_code'],
            **({'partner_id': partner.id} if partner else {}),
        }

    @api.model
    def _l10n_mx_edi_import_cfdi_format_tax_name(self, tax_key):
        factor_type, amount, amount_type, tax_type = tax_key
        unknown_label = self.env._('Unknown')
        if factor_type == 'Exento':
            amount_str = 'Exento'
        elif factor_type in ('Tasa', 'Cuota') and amount:
            amount_str = str(amount) + ('%' if amount_type == 'percent' else '')
        else:
            amount_str = unknown_label

        return self.env._('%(tax_type)s tax with %(amount)s rate',
            tax_type=(tax_type or '').upper() or unknown_label,
            amount=amount_str,
        )

    def _l10n_mx_edi_import_cfdi_invoice_line_add_taxes_values(self, invoice_line_values):
        concepto_values = invoice_line_values['concepto_values']
        taxes_values = invoice_line_values['taxes_values'] = []
        total_taxes_values = invoice_line_values['total_taxes_values']
        type_tax_use = 'sale' if invoice_line_values['journal_type'] == 'sale' else 'purchase'
        missing_from_totals_taxes = set()
        for tax_data in concepto_values['concepto_taxes_data']:
            tax_key = tax_data['tax_key']
            factor_type, amount, amount_type, tax_type = tax_data['tax_key']
            tax_values = {
                'type_tax_use': type_tax_use,
                'l10n_mx_factor_type': factor_type,
                'amount': amount,
                'amount_type': amount_type,
                'l10n_mx_tax_type': tax_type,
                'tax_key': tax_key,
                'base_amount_currency': tax_data['base_amount_currency'],
                'tax_amount_currency': tax_data['tax_amount_currency'],
            }
            taxes_values.append(tax_values)
            if tax_key in total_taxes_values:
                total_taxes_values[tax_key]['related_taxes_values'].append(tax_values)
            # Exento taxes are not included in the totals
            elif factor_type != 'Exento':
                tax_values['missing_from_totals'] = True
                missing_from_totals_taxes.add(tax_key)

        if missing_from_totals_taxes:
            tax_messages = [
                Markup("<li>%s</li>") % self._l10n_mx_edi_import_cfdi_format_tax_name(tax_key)
                for tax_key in missing_from_totals_taxes
            ]
            tax_missing_items = Markup("<ul>%s</ul>") % Markup().join(tax_messages)
            invoice_line_values['messages'].append(Markup().join([
                self.env._("The following taxes were not found in the CFDI's tax totals."),
                tax_missing_items
            ]))

    def _l10n_mx_edi_import_cfdi_retrieve_products_search_plan(self, import_values):
        ProductProduct = self.env['product.product']
        search_plans = [
            *ProductProduct._get_retrieval_product_search_plan(),
            *(
                ProductProduct._l10n_mx_edi_get_bill_retrieval_product_search_plan()
                if import_values['journal_type'] == 'purchase' else []
            ),
        ]

        return [method[1] for method in sorted(search_plans)]

    def _l10n_mx_edi_import_cfdi_retrieve_products(self, import_values):
        product_values_list = [
            invoice_line_values['product_values']
            for invoice_line_values in import_values['invoice_lines_values']
        ]
        search_plan = self._l10n_mx_edi_import_cfdi_retrieve_products_search_plan(import_values)
        self.env['product.product']._import_retrieve_product(
            search_plan=search_plan,
            company=import_values['company'],
            product_values_list=product_values_list,
        )

        lines_to_retry = []
        for invoice_line_values in import_values['invoice_lines_values']:
            if product := invoice_line_values['product_values'].get('product'):
                invoice_line_values['line_values']['product_id'] = product.id
            else:
                values_without_unspsc_code = {**invoice_line_values['product_values']}
                del values_without_unspsc_code['unspsc_code']
                lines_to_retry.append((invoice_line_values, values_without_unspsc_code))

        # Retry without unspsc_code
        if lines_to_retry:
            self.env['product.product']._import_retrieve_product(
                search_plan=search_plan,
                company=import_values['company'],
                product_values_list=[line[1] for line in lines_to_retry],
            )

            for invoice_line_values, values_without_unspsc_code in lines_to_retry:
                if product := values_without_unspsc_code.get('product'):
                    invoice_line_values['line_values']['product_id'] = product.id
                    invoice_line_values['product_values']['product'] = product
                else:
                    invoice_line_values['line_values']['product_id'] = False

    def _l10n_mx_edi_import_cfdi_retrieve_taxes_search_plan(self, import_values):
        return [
            self.env['account.tax']._l10n_mx_edi_import_retrieve_tax_from_l10n_mx_identifiers,
        ]

    def _l10n_mx_edi_import_cfdi_retrieve_taxes(self, import_values):
        taxes_values_list = []
        for invoice_line_values in import_values['invoice_lines_values']:
            taxes_values_list += invoice_line_values['taxes_values']

        self.env['account.tax']._import_retrieve_tax(
            search_plan=self._l10n_mx_edi_import_cfdi_retrieve_taxes_search_plan(import_values),
            company=import_values['company'],
            tax_values_list=taxes_values_list,
        )

        missing_taxes = set()
        for invoice_line_values in import_values['invoice_lines_values']:
            tax_ids_commands = invoice_line_values['tax_ids'] = [Command.set([])]
            for tax_values in invoice_line_values['taxes_values']:
                if tax := tax_values.get('tax'):
                    tax_ids_commands[0][2].append(tax.id)
                    continue

                missing_taxes.add(tax_values['tax_key'])

        if missing_taxes:
            import_values['are_taxes_complete'] = False

        tax_messages = [
            Markup("<li>%s</li>") % self.env._('Could not retrieve %(tax_name)s.',
                tax_name=self._l10n_mx_edi_import_cfdi_format_tax_name(tax_key))
            for tax_key in missing_taxes
        ]
        if tax_messages:
            tax_missing_items = Markup("<ul>%s</ul>") % Markup().join(tax_messages)
            import_values['messages'].append(Markup().join(
                [self.env._("The following ocurred while trying to retrieve taxes: "), tax_missing_items]
            ))

    def _l10n_mx_edi_import_cfdi_add_local_tax_invoice_lines_values(self, import_values):
        local_tax_invoice_lines_values = import_values['local_tax_invoice_lines_values'] = []
        cfdi_values = import_values['cfdi_values']
        if not cfdi_values['local_taxes']:
            return

        type_tax_use = 'sale' if import_values['journal_type'] == 'sale' else 'purchase'
        local_tax = self.env['account.chart.template'].with_company(import_values['company'])\
            .ref(f'l10n_mx_edi_tax_local_{type_tax_use}', raise_if_not_found=False)
        if not local_tax:
            import_values['messages'].append(self.env._(
                "Failed to import local taxes. Generic local tax is missing from this document's company."
                "Reload Company's CoA to regenerate the tax."
            ))
            return

        for local_tax_values in cfdi_values['local_taxes']:
            rate = local_tax_values['rate']
            name = ' '.join(filter(None, (local_tax_values['name'], f'({rate})' if rate else None)))
            local_tax_invoice_lines_values.append({
                **import_values,
                'taxes_values': [{'tax': local_tax}],
                'line_values': {
                    'quantity': 1.0,
                    'price_unit': local_tax_values['price_unit'],
                    'name': name,
                    'discount': 0,
                }
            })

    def _l10n_mx_edi_import_cfdi_get_base_line_kwargs(self, invoice_line_values):
        invoice = invoice_line_values['invoice']
        taxes = self.env['account.tax']
        for tax_values in invoice_line_values['taxes_values']:
            taxes |= tax_values.get('tax', self.env['account.tax'])

        line_values = invoice_line_values['line_values']
        base_line_kwargs = {
            'sign': invoice.direction_sign,
            'is_refund': invoice.move_type in ('out_refund', 'in_refund'),
            'currency_id': invoice_line_values['currency'],
            'rate': invoice_line_values['invoice_values'].get('invoice_currency_rate', 1),
            'special_mode': 'total_excluded',
            'tax_ids': taxes,
            'quantity': line_values['quantity'],
            'price_unit': line_values['price_unit'],
            'discount': line_values['discount'],
            '_create_values': {**line_values},
        }

        if partner := invoice_line_values['customer_values'].get('customer'):
            base_line_kwargs['partner_id'] = partner
        if product := invoice_line_values.get('product_values', {}).get('product'):
            base_line_kwargs['product_id'] = product

        return base_line_kwargs

    def _l10n_mx_edi_import_cfdi_add_base_lines(self, import_values):
        AccountTax = self.env['account.tax']
        base_lines = import_values['base_lines'] = []
        company = import_values['company']

        for invoice_line_values in import_values['invoice_lines_values']:
            base_line_kwargs = self._l10n_mx_edi_import_cfdi_get_base_line_kwargs(invoice_line_values)
            base_lines.append(AccountTax._prepare_base_line_for_taxes_computation(
                record=None,
                **base_line_kwargs,
            ))

        for local_tax_invoice_line_values in import_values['local_tax_invoice_lines_values']:
            base_line_kwargs = self._l10n_mx_edi_import_cfdi_get_base_line_kwargs(local_tax_invoice_line_values)
            base_lines.append(AccountTax._prepare_base_line_for_taxes_computation(
                record=None,
                **base_line_kwargs,
            ))

        AccountTax._add_tax_details_in_base_lines(base_lines, company)
        AccountTax._round_base_lines_tax_details(base_lines, company)

    def _l10n_mx_edi_import_cfdi_collect_invoice_values(self, import_values):
        cfdi_values = import_values['cfdi_values']
        invoice_values = import_values['invoice_values'] = {}
        journal_type = import_values['journal_type']

        doc_type = "refund" if cfdi_values['receipt_type'] == "E" else "invoice"
        doc_prefix_type = "out_" if journal_type == "sale" else "in_"
        move_type = doc_prefix_type + doc_type
        # Collect general Invoice/CFDI Info
        invoice_values.update({
            'move_type': move_type,
            'l10n_mx_edi_cfdi_to_public': journal_type == 'sale' and cfdi_values['customer_rfc'] in ('XAXX010101000', 'XEXX010101000'),
            'l10n_mx_edi_payment_method_id': self.env['l10n_mx_edi.payment.method'].search([('code', '=', cfdi_values['forma_pago'])], limit=1).id,
            'l10n_mx_edi_payment_policy': cfdi_values['metodo_pago'],
            'l10n_mx_edi_usage': cfdi_values['usage'] if cfdi_values['usage'] in dict(self._fields['l10n_mx_edi_usage'].selection) else False,
            'l10n_mx_edi_cfdi_uuid': cfdi_values['uuid'],
            'ref': cfdi_values['uuid'] if journal_type == 'purchase' else False,
            'invoice_date': cfdi_values['emission_date_str'] and datetime.strptime(cfdi_values['emission_date_str'], '%Y-%m-%d %H:%M:%S').date()
        })

        # Collect currency info
        currency = self.env['res.currency'].search([('name', '=', cfdi_values['moneda'])], limit=1)
        if not currency:
            import_values['messages'].append(self.env._("Unknown currency %s was not found. Falling back to the company's currency", cfdi_values['moneda']))
            import_values['currency'] = import_values['company'].currency_id
        else:
            import_values['currency'] = currency
            invoice_values['currency_id'] = currency.id
            if cfdi_values['tipo_cambio']:
                invoice_values['invoice_currency_rate'] = 1 / float(cfdi_values['tipo_cambio'])

        # Retrieve or Create partner and update missing info
        self._l10n_mx_edi_import_cfdi_retrieve_customer(import_values)
        self._l10n_mx_edi_import_cfdi_create_or_update_customer(import_values)
        self._l10n_mx_edi_import_cfdi_add_total_taxes_values(import_values)
        # Prepare invoice lines
        self._l10n_mx_edi_import_cfdi_add_invoice_lines_values(import_values)
        self._l10n_mx_edi_import_cfdi_retrieve_products(import_values)
        self._l10n_mx_edi_import_cfdi_retrieve_taxes(import_values)

        # Prepare local tax invoice lines
        self._l10n_mx_edi_import_cfdi_add_local_tax_invoice_lines_values(import_values)
        # Prepare base lines
        self._l10n_mx_edi_import_cfdi_add_base_lines(import_values)

    def _l10n_mx_edi_import_cfdi_write_invoice_values(self, import_values):
        invoice = import_values['invoice']

        base_lines = import_values['base_lines']

        invoice_values = import_values['invoice_values']
        invoice_line_create_commands = []
        for base_line in base_lines:
            create_values = {
                **base_line['_create_values'],
                'quantity': base_line['quantity'],
                'price_unit': base_line['price_unit'],
                'discount': base_line.get('discount', 0),
                'tax_ids': [Command.set(base_line['tax_ids'].ids)]
            }
            invoice_line_create_commands.append(Command.create(create_values))

        # skip force onchange name predictive
        container = {'records': invoice}
        with (
            invoice._check_balanced(container),
            invoice._disable_discount_precision(),
            invoice._sync_dynamic_lines(container),
        ):
            invoice.write(invoice_values)
            # Create invoice lines separately to avoid recompute of fields when setting invoice fields.
            # (e.g. l10n_mx_edi_tax_object when setting partner_id or l10n_mx_edi_cfdi_to_public)
            invoice.write({'invoice_line_ids': invoice_line_create_commands})

    def _l10n_mx_edi_import_cfdi_fix_taxes_amounts(self, import_values):
        AccountTax = self.env['account.tax']
        invoice = import_values['invoice']
        tax_total_values = import_values['total_taxes_values']
        currency = import_values['currency']

        tax_to_taxes = {}
        taxes_to_tax_amount_currency = {}
        for tax_key, global_tax_values in tax_total_values.items():
            taxes = self.env['account.tax']
            for related_tax_values in global_tax_values['related_taxes_values']:
                taxes |= related_tax_values['tax']

            for tax in taxes:
                tax_to_taxes[tax] = taxes
            taxes_to_tax_amount_currency[taxes] = global_tax_values['tax_amount_currency']

        # Fix the base lines.
        def grouping_function(_base_line, tax_data):
            return tax_data and tax_to_taxes.get(tax_data['tax'])

        base_lines, tax_lines = invoice._get_rounded_base_and_tax_lines()
        base_lines_aggregated_values = AccountTax._aggregate_base_lines_tax_details(base_lines, grouping_function)
        values_per_grouping_key = AccountTax._aggregate_base_lines_aggregated_values(base_lines_aggregated_values)

        # Compare each tax expected cfdi amount by what we have computed
        tax_mismatches = []
        for tax, values in values_per_grouping_key.items():
            if not tax:
                continue

            target_tax_amount_currency = taxes_to_tax_amount_currency[tax]
            if currency.compare_amounts(values['tax_amount_currency'], target_tax_amount_currency) == 0:
                continue

            tax_mismatches.append((tax, values['tax_amount_currency'], target_tax_amount_currency))
            target_factors = [
                {
                    'factor': tax_data['raw_tax_amount_currency'],
                    'tax_data': tax_data,
                }
                for _base_line, taxes_data in values['base_line_x_taxes_data']
                for tax_data in taxes_data
            ]
            amounts_to_distribute = AccountTax._distribute_delta_amount_smoothly(
                precision_digits=currency.decimal_places,
                delta_amount=target_tax_amount_currency,
                target_factors=target_factors,
            )
            for target_factor, amount_to_distribute in zip(target_factors, amounts_to_distribute):
                tax_data = target_factor['tax_data']
                tax_data['tax_amount_currency'] = amount_to_distribute

        if not tax_mismatches:
            return

        mismatch_messages = [
            Markup("<li>%s</li>") % self.env._(
                'Before %(tax_name)s: %(computed_amount)s  |  After %(tax_name)s: %(cfdi_amount)s',
                tax_name=', '.join(taxes.mapped('name')),
                cfdi_amount=formatLang(self.env, cfdi_amount, currency_obj=currency),
                computed_amount=formatLang(self.env, computed_amount, currency_obj=currency),
            )
            for taxes, computed_amount, cfdi_amount in tax_mismatches
        ]
        import_values['messages'].append(Markup().join([
            self.env._("The following tax amounts where fixed while importing CFDI:"),
            Markup("<ul>%s</ul>") % Markup().join(mismatch_messages),
        ]))

        AccountTax._add_accounting_data_in_base_lines_tax_details(base_lines, invoice.company_id, include_caba_tags=invoice.always_tax_exigible)
        tax_results = AccountTax._prepare_tax_lines(base_lines, invoice.company_id, tax_lines=tax_lines)

        line_ids_commands = []
        for tax_line_vals, _grouping_key, to_update in tax_results['tax_lines_to_update']:
            line_ids_commands.append(Command.update(tax_line_vals['record'].id, {
                'amount_currency': to_update['amount_currency'],
                'balance': to_update['balance'],
            }))

        # skip force onchange name predictive
        container = {'records': invoice}
        with (
            invoice._check_balanced(container),
            invoice._disable_discount_precision(),
            invoice._sync_dynamic_lines(container),
        ):
            invoice.line_ids = line_ids_commands

    def _l10n_mx_edi_import_cfdi_fix_untaxed_amount(self, import_values):
        invoice = import_values['invoice']
        currency = import_values['currency']
        cfdi_values = import_values['cfdi_values']
        expected_untaxed_amount = cfdi_values['amount_subtotal'] - cfdi_values['amount_discount']
        difference = currency.round(expected_untaxed_amount - invoice.amount_untaxed)
        if currency.is_zero(difference):
            return

        # skip force onchange name predictive
        container = {'records': invoice}
        with (
            invoice._check_balanced(container),
            invoice._disable_discount_precision(),
            invoice._sync_dynamic_lines(container),
        ):
            invoice.invoice_line_ids = [
                Command.create({
                    'display_type': 'product',
                    'name': self.env._("Rounding"),
                    'quantity': 1,
                    'price_unit': difference,
                    'tax_ids': [],
                }),
            ]

    def _l10n_mx_edi_import_cfdi_post_process(self, import_values):
        self._l10n_mx_edi_import_cfdi_add_import_totals_results(import_values)
        invoice = import_values['invoice']
        if not import_values['are_taxes_complete'] or any(
            import_values['currency'].compare_amounts(cfdi_amount, invoice_amount) != 0
            for cfdi_amount, invoice_amount, _result_label in import_values['import_totals_results']
        ):
            invoice.review_state = 'anomaly'
            invoice.l10n_mx_edi_show_import_totals_alert = True

        totals_message = self._l10n_mx_edi_import_cfdi_get_import_totals_message(import_values)
        invoice.message_post(body=Markup().join([totals_message] + import_values['messages']))

    def _l10n_mx_edi_import_cfdi_invoice(self, invoice, file_data, new=False):
        """Import a CFDI XML file into an invoice record."""
        # Collect import values from CFDI XML
        cfdi_values = self.env['l10n_mx_edi.document']._import_cfdi_collect_invoice_cfdi_values(file_data['xml_tree'])

        # Check if possible to import
        if message := self._l10n_mx_edi_import_cfdi_check_can_import(invoice, cfdi_values):
            invoice.review_state = 'anomaly'
            return message

        # Don't fill the invoice if it already has lines, simply give it the cfdi info
        if invoice.state == "draft" and not invoice.invoice_line_ids:

            import_values = {
                'invoice': invoice,
                'company': invoice.company_id,
                'journal_type': invoice.journal_id.type,
                'cfdi_values': cfdi_values,
                'are_taxes_complete': True,
                'messages': [],
                'import_totals_results': []
            }
            self._l10n_mx_edi_import_cfdi_collect_invoice_values(import_values)
            self._l10n_mx_edi_import_cfdi_write_invoice_values(import_values)
            # Doesn't make sense to fix taxes if taxes are not completed
            if import_values['are_taxes_complete']:
                self._l10n_mx_edi_import_cfdi_fix_taxes_amounts(import_values)
                self._l10n_mx_edi_import_cfdi_fix_untaxed_amount(import_values)
            self._l10n_mx_edi_import_cfdi_post_process(import_values)

        # 'out_receipt' is not handled by the CFDI computes
        if invoice.move_type == 'out_receipt':
            return self.env._("Importing a CFDI on a sales receipt is not supported.")

        in_import_documents = invoice.l10n_mx_edi_invoice_document_ids.filtered(
            lambda document: document.state.startswith('to_import')
        )
        in_import_documents._create_update_document(
            invoice,
            {
                'company_id': invoice.company_id.id,
                'move_id': invoice.id,
                'invoice_ids': [Command.set(invoice.ids)],
                'state': 'invoice_sent' if invoice.is_sale_document() else 'invoice_received',
                'sat_state': 'not_defined',
                'attachment_id': file_data['origin_attachment'].id,
            },
            lambda document: document.state.startswith('to_import'),
        )

    def _l10n_mx_edi_import_cfdi_get_import_totals_message(self, import_values):
        currency = import_values['currency']

        totals_message = []
        for cfdi_amount, invoice_amount, result_label in import_values['import_totals_results']:
            message = self.env._(
                'CFDI %(result_label)s: %(cfdi_amount)s  |  Invoice %(result_label)s: %(invoice_amount)s',
                result_label=result_label,
                cfdi_amount=formatLang(self.env, cfdi_amount, currency_obj=currency),
                invoice_amount=formatLang(self.env, invoice_amount, currency_obj=currency),
            )
            totals_message.append(Markup('<li>%s</li>') % message)

        return Markup().join([
            self.env._("Import amounts results:"),
            Markup("<ul>%s</ul>") % Markup().join(totals_message)
        ])

    def _l10n_mx_edi_import_cfdi_add_import_totals_results(self, import_values):
        cfdi_values = import_values['cfdi_values']
        invoice = import_values['invoice']
        sign = -1 if invoice.move_type in ('out_invoice', 'in_refund') else 1

        local_taxes_amount = amount_withholding = 0
        tax_amounts = {}
        for line in invoice.line_ids:
            amount_currency = sign * line.amount_currency
            if not line.tax_line_id:
                continue
            tax = line.tax_line_id
            if tax.l10n_mx_tax_type == 'local':
                local_taxes_amount += amount_currency
                continue
            if invoice.currency_id.compare_amounts(amount_currency, 0) < 0:
                amount_withholding += amount_currency
                continue
            tax_key = (tax.l10n_mx_factor_type, tax.amount, tax.amount_type, tax.l10n_mx_tax_type)
            if tax_key in tax_amounts:
                tax_amounts[tax_key] += amount_currency
            else:
                tax_amounts[tax_key] = amount_currency

        tax_totals_results = []
        for tax_key, values in import_values['total_taxes_values'].items():
            factor_type, amount, _amount_type, tax_type = tax_key
            if amount < 0:
                continue
            invoice_tax_amount = tax_amounts.get(tax_key, 0.0)

            tax_label = self.env._('Total %s Tax', (tax_type or '').upper() or self.env._('Unknown'))
            if factor_type != 'Exento':
                tax_label += f' {formatLang(self.env, amount)}{"%" if factor_type == "Tasa" else self.env._(" fee")}'

            tax_totals_results.append((values['tax_amount_currency'], invoice_tax_amount, tax_label))

        amount_subtotal_with_discount = cfdi_values['amount_subtotal'] - cfdi_values['amount_discount']
        import_values['import_totals_results'] = [
            (amount_subtotal_with_discount, invoice.amount_untaxed, self.env._('Subtotal With Discount')),
            (cfdi_values['amount_local_taxes'], local_taxes_amount, self.env._('Total Local Taxes')),
            *tax_totals_results,
            (cfdi_values['amount_withholding'], amount_withholding, self.env._('Total Withholding')),
            (cfdi_values['amount_total'], invoice.amount_total, self.env._('Total')),
        ]

    def _get_import_file_type(self, file_data):
        """ Identify CFDIs. """
        # EXTENDS 'account'
        if file_data['xml_tree'] is not None and file_data['xml_tree'].prefix == 'cfdi':
            return 'l10n_mx.cfdi'
        return super()._get_import_file_type(file_data)

    def _get_edi_decoder(self, file_data, new=False):
        # EXTENDS 'account'
        if file_data['import_file_type'] == 'l10n_mx.cfdi':
            return {
                'priority': 20,
                'decoder': self._l10n_mx_edi_import_cfdi_invoice,
            }
        return super()._get_edi_decoder(file_data, new)

    def _get_invoice_legal_documents(self, filetype, allow_fallback=False):
        # EXTENDS account
        if filetype == 'cfdi':
            if cfdi_attachment := self.l10n_mx_edi_cfdi_attachment_id:
                return [{
                    'filename': cfdi_attachment.name,
                    'filetype': 'xml',
                    'content': cfdi_attachment.raw,
                }]
        return super()._get_invoice_legal_documents(filetype, allow_fallback=allow_fallback)

    def get_extra_print_items(self):
        print_items = super().get_extra_print_items()
        if self.l10n_mx_edi_cfdi_attachment_id:
            print_items.append({
                'key': 'download_xml_cfdi',
                'description': self.env._('XML CFDI'),
                **self.action_invoice_download_cfdi(),
            })
        return print_items

    def _get_bank_transaction_receipt_report_values(self):
        """ Get the extra values when rendering the Payment Receipt PDF report from a bank transaction.

        :return: A dictionary:
            * display_invoices: Display the invoices table.
            * display_payment_method: Display the payment method value.
            * cfdi: A dict with all cfdi datas from the record.
        """
        self.ensure_one()
        return {
            'display_invoices': False,
            'display_payment_method': False,
            'cfdi': self._l10n_mx_edi_get_extra_payment_report_values(),
        }

    def _get_document_partner_ident_line(self):
        return (
            f"RFC: {self.l10n_mx_edi_cfdi_customer_rfc}"
            if self.l10n_mx_edi_cfdi_customer_rfc else
            super()._get_document_partner_ident_line()
        )
