import stdnum.uy
from lxml import etree
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import cleanup_xml_node, float_compare, format_amount

from odoo.addons.l10n_uy_edi.models.account_move import UY_EDI_CURRENCIES, VAT_RATE_TO_INDICATOR, format_float
from odoo.addons.l10n_uy_edi.models.res_partner import UY_RUT_DGI_CODE


class PosOrder(models.Model):
    _inherit = "pos.order"

    l10n_uy_edi_document_number = fields.Char(
        string="CFE Number",
        copy=False,
        readonly=True,
        help="Legal serie and number of the CFE assigned by Uruware/DGI.",
    )
    l10n_uy_edi_document_id = fields.Many2one(
        comodel_name="l10n_uy_edi.document",
        string="Uruguay CFE",
        copy=False,
        help="Uruguay: the e-Ticket of this sale, an invoiced order carries its CFE on the invoice.",
    )
    l10n_uy_edi_cfe_state = fields.Selection(related="l10n_uy_edi_document_id.state", store=True)
    l10n_uy_edi_error = fields.Text(string="CFE Error", related="l10n_uy_edi_document_id.message")
    l10n_uy_edi_pdf_attachment_id = fields.Many2one(
        comodel_name="ir.attachment",
        string="CFE PDF",
        copy=False,
        readonly=True,
        ondelete="set null",
        help="Uruguay: the legal PDF representation of the e-Ticket, as Uruware returned it.",
    )

    l10n_uy_edi_is_enabled = fields.Boolean(compute="_compute_l10n_uy_edi_is_enabled")
    l10n_uy_edi_enable_send = fields.Boolean(compute="_compute_l10n_uy_edi_enable_send")

    # Compute methods

    @api.depends("config_id.company_id.country_code", "config_id.journal_id.l10n_uy_edi_type")
    def _compute_l10n_uy_edi_is_enabled(self):
        """ The order issues a CFE itself: a UY point of sale invoicing through an electronic journal """
        for order in self:
            order.l10n_uy_edi_is_enabled = (
                order.company_id.account_fiscal_country_id.code == "UY"
                and order.config_id.journal_id.l10n_uy_edi_type == "electronic"
            )

    @api.depends(
        "state",
        "l10n_uy_edi_is_enabled",
        "l10n_uy_edi_cfe_state",
        "is_singly_invoiced",
        "partner_id.commercial_partner_id.vat",
    )
    def _compute_l10n_uy_edi_enable_send(self):
        """ Only an invoiced RUT order issues its CFE somewhere other than the order itself """
        for order in self:
            order.l10n_uy_edi_enable_send = (
                order.l10n_uy_edi_is_enabled
                and order.state in ("paid", "done")
                and not (order.is_singly_invoiced and order._l10n_uy_edi_partner_has_rut())
                and order.l10n_uy_edi_cfe_state != "accepted"
            )

    # Extend point_of_sale

    @api.model
    def sync_from_ui(self, orders):
        """ Once saved, issue the e-Ticket CFE of every UY order that needs one """
        result = super().sync_from_ui(orders)

        if not orders or not orders[0].get("session_id"):
            return result

        saved_orders = self.browse([order["id"] for order in result["pos.order"]])
        # An invoiced order already issued its CFE while its invoice was generated
        for order in saved_orders.filtered(
            lambda order: order.l10n_uy_edi_enable_send and not order.is_singly_invoiced,
        ):
            order.l10n_uy_edi_action_send_document()

        # The orders were serialized before their CFE was issued, so refresh the payload
        orders_by_id = {order.id: order for order in saved_orders}
        for order_data in result["pos.order"]:
            order = orders_by_id[order_data["id"]]
            order_data["l10n_uy_edi_cfe_state"] = order.l10n_uy_edi_cfe_state
            order_data["l10n_uy_edi_error"] = order.l10n_uy_edi_error

        return result

    def _generate_pos_order_invoice(self):
        # EXTENDS point_of_sale
        if sent := self.filtered(
            lambda order: not order.is_singly_invoiced and order.l10n_uy_edi_cfe_state == "accepted",
        ):
            raise UserError(self.env._(
                "An e-Ticket was already accepted by DGI for %(orders)s. Invoicing it now would"
                " report the same sale twice.",
                orders=", ".join(sent.mapped("name")),
            ))

        uy_orders = self.filtered("l10n_uy_edi_is_enabled")
        if not uy_orders:
            return super()._generate_pos_order_invoice()

        # The invoice PDF is always deferred, rendering it commits mid-request and breaks retries
        invoice = super(PosOrder, self.with_context(generate_pdf=False))._generate_pos_order_invoice()
        for order in uy_orders:
            # A Customer Account payment invoices an order that must still report an e-Ticket
            if order._l10n_uy_edi_partner_has_rut():
                order._l10n_uy_edi_send_invoice()
            elif order.l10n_uy_edi_cfe_state != "accepted":
                order.l10n_uy_edi_action_send_document()
        return invoice

    # Send orchestration

    def _l10n_uy_edi_is_deferred_payment(self):
        """ A Customer Account settles later, which DGI reports as credito on a sale and on a refund """
        self.ensure_one()
        return any(payment.payment_method_id.type == "pay_later" for payment in self.payment_ids)

    def _l10n_uy_edi_partner_has_rut(self):
        """ Whether the customer is RUT identified, the only case reported as an e-Invoice """
        self.ensure_one()
        return self.partner_id.commercial_partner_id._l10n_uy_edi_get_dgi_code() == UY_RUT_DGI_CODE

    def _l10n_uy_edi_get_document_type(self):
        """ e-Ticket (101), or e-Ticket Credit Note (102) when the order gives money back """
        self.ensure_one()
        if self.currency_id.compare_amounts(self.amount_total, 0) == -1:
            return self.env.ref("l10n_uy.dc_cn_e_ticket")
        return self.env.ref("l10n_uy.dc_e_ticket")

    def l10n_uy_edi_action_send_document(self):
        """ Validate and send the e-Ticket CFE to Uruware, recording the outcome on the order """
        self.ensure_one()

        if errors := self._l10n_uy_edi_check_order():
            self._l10n_uy_edi_new_document(
                state="error",
                message=self._l10n_uy_edi_generation_error(errors),
            )
            return

        self._l10n_uy_edi_send()

    def _l10n_uy_edi_generation_error(self, errors):
        """ The message of a CFE that could not even be built, as the error banner shows it. """
        return self.env._(
            "The CFE cannot be generated for this order:\n\t- %(errors)s",
            errors="\n\t- ".join(errors),
        )

    def _l10n_uy_edi_new_document(self, **vals):
        """ Create the CFE document of this order. A retry supersedes the failed attempt. """
        self.ensure_one()
        self.l10n_uy_edi_document_id.filtered(lambda doc: doc.state in ("error", "rejected")).unlink()
        self.l10n_uy_edi_document_id = self.env["l10n_uy_edi.document"].create({
            "pos_order_id": self.id,
            "uuid": self.env["l10n_uy_edi.document"]._get_uuid(self),
            **vals,
        })
        return self.l10n_uy_edi_document_id

    def _l10n_uy_edi_send(self):
        """ Create the CFE document of this order and send it to Uruware. """
        self.ensure_one()
        edi_doc = self._l10n_uy_edi_new_document()
        msg = False
        attachments = self.env["ir.attachment"]

        if self.company_id.l10n_uy_edi_ucfe_env == "demo":
            # Skip DGI and validate in Odoo only, numbering first since the attachment name uses it
            edi_doc.state = "accepted"
            self.l10n_uy_edi_document_number = "DE%07d" % self.id
            attachments = self._l10n_uy_edi_create_xml_attachment()
            msg = self.env._(
                "This CFE has been generated in DEMO Mode. It is considered as accepted and it won't be sent to DGI.",
            )
        else:
            result = edi_doc._send_dgi(
                self._l10n_uy_edi_prepare_req_data(),
                terminal_code=self.config_id.journal_id.l10n_uy_edi_ucfe_terminal_code,
            )
            edi_doc._update_cfe_state(result)
            response = result.get("response")

            if edi_doc.message:
                self.message_post(body=Markup(
                    "<font style='color:Tomato;'><strong>{}:</strong></font> <i>{}</i>",
                ).format(self.env._("ERROR"), edi_doc.message))
            elif edi_doc.state in ("received", "accepted"):
                self.l10n_uy_edi_document_number = (
                    response.findtext(".//{*}Serie") + "%07d" % int(response.findtext(".//{*}NumeroCfe"))
                )
                msg = self.env._(
                    "The %(document_type)s was created successfully",
                    document_type=self._l10n_uy_edi_get_document_type().display_name,
                )
                if server_msg := response.findtext(".//{*}MensajeRta", ""):
                    msg = server_msg + msg

            if response is not None:
                attachments = self._l10n_uy_edi_update_xml_and_pdf_file(response)

        if msg and edi_doc.state in ("received", "accepted"):
            self.message_post(body=msg, attachment_ids=attachments.ids if attachments else False)
        return edi_doc

    def _l10n_uy_edi_prepare_req_data(self):
        """ The 310 request payload: the CFE itself plus its identification. """
        self.ensure_one()
        edi_doc = self.l10n_uy_edi_document_id
        return {
            "Uuid": edi_doc.uuid,
            "TipoCfe": int(self._l10n_uy_edi_get_document_type().code),
            "HoraReq": edi_doc.request_datetime.strftime("%H%M%S"),
            "FechaReq": edi_doc.request_datetime.date().strftime("%Y%m%d"),
            "CfeXmlOTexto": self._l10n_uy_edi_get_xml_content().decode(),
        }

    def _l10n_uy_edi_create_xml_attachment(self, raw=None):
        """ (Re)create the XML attachment: the signed CFE if Uruware returned one, else a preview """
        self.ensure_one()
        edi_doc = self.l10n_uy_edi_document_id
        edi_doc.attachment_id.res_field = False
        attachment = self.env["ir.attachment"].create({
            "res_model": "l10n_uy_edi.document",
            "res_field": "attachment_file",
            "res_id": edi_doc.id,
            "name": edi_doc._get_xml_attachment_name(),
            "type": "binary",
            "raw": raw or self._l10n_uy_edi_get_xml_content(),
        })
        edi_doc.invalidate_recordset(["attachment_id", "attachment_file"])
        return attachment

    def _l10n_uy_edi_update_xml_and_pdf_file(self, response):
        """ Store the signed XML returned by Uruware and attach the legal PDF representation. """
        self.ensure_one()
        edi_doc = self.l10n_uy_edi_document_id
        xml_content = response.findtext(".//{*}XmlCfeFirmado")
        if not xml_content:
            self._l10n_uy_edi_create_xml_attachment()
            return self.env["ir.attachment"]

        res_files = self._l10n_uy_edi_create_xml_attachment(
            raw=xml_content.encode() if edi_doc.state in ("received", "accepted") else None,
        )
        if edi_doc.state and edi_doc.state != "error":
            pdf_result = edi_doc._get_pdf()
            if file_content := pdf_result.get("file_content"):
                res_files |= self._l10n_uy_edi_attach_pdf(file_content)
            if errors := pdf_result.get("errors"):
                msg = self.env._("Error getting the PDF file: %s", errors)
                edi_doc.message = (edi_doc.message or "") + msg
                self.message_post(body=msg)
        return res_files

    def _l10n_uy_edi_send_invoice(self):
        """ Issue the CFE of the invoice of a RUT order, recording the outcome on the invoice """
        self.ensure_one()
        move = self.account_move
        if not move or move.l10n_uy_edi_cfe_state in ("received", "accepted"):
            return

        errors = move._l10n_uy_edi_check_move()
        # _l10n_uy_edi_check_move returns nothing at all on a journal that does not use documents
        if not move.l10n_latam_document_type_id:
            errors.append(self.env._("The invoice has no Uruguayan document type to build a CFE from."))
        elif move.l10n_latam_document_internal_type == "credit_note" and not move._l10n_uy_edi_found_related_cfe():
            errors.append(self.env._("A credit note must reference the CFE of the order it refunds."))
        if errors:
            move.l10n_uy_edi_document_id = self.env["l10n_uy_edi.document"].create({
                "move_id": move.id,
                "uuid": self.env["l10n_uy_edi.document"]._get_uuid(move),
                "state": "error",
                "message": self._l10n_uy_edi_generation_error(errors),
            })
            return

        move._l10n_uy_edi_send()

    def _l10n_uy_edi_attach_pdf(self, file_content):
        """ Attach the legal PDF representation returned by Uruware to the order. """
        self.ensure_one()
        self.l10n_uy_edi_pdf_attachment_id = self.env["ir.attachment"].create({
            "res_model": "pos.order",
            "res_id": self.id,
            "name": (self.l10n_uy_edi_document_number or self.name).replace("/", "_") + ".pdf",
            "type": "binary",
            "raw": file_content,
        })
        return self.l10n_uy_edi_pdf_attachment_id

    def _l10n_uy_edi_get_addenda(self):
        """ The free text sent alongside the CFE, always empty since a POS order carries none. """
        return ""

    def _l10n_uy_edi_get_pdf(self):
        """ The legal PDF representation of the e-Ticket, empty until Uruware returns one. """
        self.ensure_one()
        if self.l10n_uy_edi_cfe_state != "accepted":
            return self.env["ir.attachment"]
        return self.l10n_uy_edi_pdf_attachment_id

    def _l10n_uy_edi_ensure_pdf(self):
        """ Fetch the legal PDF of a processed CFE when the send did not already bring one """
        self.ensure_one()
        edi_doc = self.l10n_uy_edi_document_id
        if edi_doc.state not in ("received", "accepted") or self.company_id.l10n_uy_edi_ucfe_env == "demo":
            return self.env["ir.attachment"]
        if file_content := edi_doc._get_pdf().get("file_content"):
            return self._l10n_uy_edi_attach_pdf(file_content)
        return self.env["ir.attachment"]

    # Pre-send validation

    def _l10n_uy_edi_check_order(self):
        """ POS-relevant subset of account_move._l10n_uy_edi_check_move. """
        self.ensure_one()
        errors = []
        company = self.company_id
        commercial_partner = self.partner_id.commercial_partner_id

        # A stale client must not emit an e-Ticket for a RUT partner (they must be invoiced).
        if self._l10n_uy_edi_partner_has_rut():
            errors.append(self.env._(
                "Orders for a customer identified with a RUT must be invoiced (e-Invoice), not sent as an e-Ticket.",
            ))

        if config_errors := company._l10n_uy_edi_validate_company_data():
            errors.append(self.env._(
                "To create the CFE document first complete your company data (%(company_name)s):\n\t- %(errors)s",
                errors="\n\t- ".join(config_errors),
                company_name=company.name,
            ))

        try:
            self.partner_id._check_vat()
        except ValidationError as exp:
            errors.append(self.env._(
                "Problem with Receiver identification number: %(exp_msg)s", exp_msg=str(exp),
            ))

        for currency_name in (self.currency_id | company.currency_id).mapped("name"):
            if currency_name not in UY_EDI_CURRENCIES:
                errors.append(self.env._("The currency does not exist on DGI currencies table %s", currency_name))
        used_rate = self._l10n_uy_edi_get_used_rate()
        if used_rate is not None and used_rate <= 0.0:
            errors.append(self.env._(
                "Not valid Currency Rate, need to be greater than 0 to be accepted by DGI (%(used_rate)s)",
                used_rate=used_rate,
            ))

        lines = self.lines
        if len(lines) > 700:
            errors.append(self.env._("For e-Ticket and related DN and CN you can only report up to 700 lines"))

        for line in lines.filtered("qty"):
            if line.product_id.l10n_uy_edi_is_non_billable:
                continue
            if len(line.tax_ids.filtered(lambda tax: tax.l10n_uy_tax_category == "vat")) != 1:
                errors.append(self.env._(
                    "All lines should have a VAT tax (only one per line). Check line '%(line_name)s'",
                    line_name=line.product_id.display_name or line.full_product_name,
                ))
        errors += [self.env._(
            "A non-billable product cannot have taxes. Please remove the taxes from"
            " line '%(line_name)s' to continue.",
            line_name=line.product_id.display_name,
        ) for line in lines.filtered(
            lambda line: line.product_id.l10n_uy_edi_is_non_billable
            and line.tax_ids.filtered(lambda tax: tax.country_code == "UY"),
        )]

        if not_supported := lines.tax_ids.filtered(lambda tax: tax.l10n_uy_tax_category != "vat"):
            errors.append(self.env._(
                "Not valid Uruguayan tax, only VAT taxes are supported (%(taxes_name)s)",
                taxes_name=", ".join(not_supported.mapped("name")),
            ))
        price_include = set(lines.tax_ids.filtered(
            lambda tax: tax.l10n_uy_tax_category == "vat",
        ).mapped("price_include"))
        if len(price_include) > 1:
            errors.append(self.env._("You cannot combine included and not included taxes on the same document"))

        # Receptor completeness when required by the threshold
        min_amount = self.env["l10n_uy_edi.document"]._get_minimum_legal_amount(company, self.date_order.date())
        if float_compare(min_amount, 1.0, precision_digits=2) == 0:
            # Without a UYI rate the conversion is a no-op and the minimum legal amount is unusable
            errors.append(self.env._("You need to have the UYI rate before validating documents"))
        if self._l10n_uy_edi_needs_receptor():
            doc_number = commercial_partner._get_preferred_legal_entity_identifier_vals().get("value")
            if not self.partner_id._l10n_uy_edi_get_dgi_code():
                errors.append(self.env._("The customer of the CFE needs to have a valid Uruguayan identification"))
            if not all([
                self.partner_id.street, self.partner_id.city, self.partner_id.state_id,
                self.partner_id.country_id, doc_number,
            ]):
                errors.append(
                    self.env._("You need to fill in the receiver details: address, city, province, country and ID number")
                    + self.env._(
                        "\n\nNOTE: This is required since the e-Ticket exceeds the minimum amount."
                        "\nMinimum amount = 5000 Uruguayan Indexed Unit (>%(min_amount)s)",
                        min_amount=format_amount(self.env, min_amount, company.currency_id),
                    ),
                )

        # A 102 references the original CFE, which may be accepted, pending or never coming
        if self._l10n_uy_edi_get_document_type().internal_type == "credit_note":
            original = self.refunded_order_id
            original_state = self._l10n_uy_edi_get_original_cfe_document().state
            if not original:
                errors.append(self.env._("A credit note e-Ticket needs the original order to be informed."))
            elif original_state == "rejected":
                errors.append(self.env._(
                    "The CFE of the original order was rejected by DGI, so no credit note can reference it."
                    " The sale itself was annulled and needs no credit note.",
                ))
            elif not original.l10n_uy_edi_is_enabled:
                errors.append(self.env._(
                    "The original order was not reported to DGI, so its refund cannot be either."
                    " Refund it outside of the electronic point of sale.",
                ))
            elif original_state != "accepted":
                errors.append(self.env._(
                    "Cannot create a credit note e-Ticket: the original order does not have an accepted CFE yet."
                    " Send the CFE of the original order first.",
                ))

        return errors

    # CFE vals builders

    def _l10n_uy_edi_get_used_rate(self):
        """ A111 TpoCambio: rate against the peso, None when the CFE is already in pesos """
        self.ensure_one()
        if not self.currency_id or self.currency_id.name == "UYU":
            return None
        return self.currency_id._convert(1.0, self.env.ref("base.UYU"), self.company_id, self.date_order.date(), round=False)

    def _l10n_uy_edi_needs_receptor(self):
        """ The receiver block of an e-Ticket is required only above 5000 UYI """
        self.ensure_one()
        min_amount = self.env["l10n_uy_edi.document"]._get_minimum_legal_amount(
            self.company_id, self.date_order.date(),
        )
        return float_compare(abs(self.amount_total), min_amount, precision_digits=2) == 1

    def _l10n_uy_edi_get_base_lines(self):
        """ Rounded per-line tax details, the input of the CFE builders """
        self.ensure_one()
        base_lines = self.lines._prepare_base_lines_for_taxes_computation()
        self.env["account.tax"]._add_tax_details_in_base_lines(base_lines, self.company_id)
        self.env["account.tax"]._round_base_lines_tax_details(base_lines, self.company_id)
        return base_lines

    def _l10n_uy_edi_get_line_nom_and_desc(self, line):
        # B7 NomItem, B8 DscItem
        lang = self.partner_id.lang or self.env.lang
        if not line.product_id:
            name = line.full_product_name or ""
            return (name[:80] or "-"), name[80:]
        display_name = line.product_id.with_context(lang=lang).display_name
        return display_name[:80], display_name[80:]

    def _l10n_uy_edi_get_invoice_indicator(self, line):
        # B4 IndFact (POS subset: no expo, no downpayment)
        if line.product_id.l10n_uy_edi_is_non_billable:
            invoice_ind = 7 if line.price_subtotal < 0.0 else 6  # Non-billable
        # Indicator 7 is only for a discount line within a positive sale, not for refund lines
        elif line.qty < 0 and self.amount_total >= 0:
            invoice_ind = 7  # Discount
        else:
            invoice_ind = VAT_RATE_TO_INDICATOR.get(line.tax_ids.amount, 4)  # 4: Otra Tasa IVA
        tax_included = set(line.tax_ids.mapped("price_include"))
        total = line.price_subtotal_incl if tax_included else line.price_subtotal
        if line.currency_id.is_zero(total):
            invoice_ind = 5  # Entrega Gratuita
        return invoice_ind

    def _l10n_uy_edi_is_global_discount_line(self, base_line):
        """ A negative unit price belongs to section D, unless the line is non-billable """
        return base_line["price_unit"] < 0 and not base_line["product_id"].l10n_uy_edi_is_non_billable

    def _l10n_uy_edi_cfe_A_iddoc(self):
        """ XML Section A (Encabezado / IdDoc) """
        self.ensure_one()
        tax_included = bool(self.lines.tax_ids.filtered(
            lambda tax: tax.l10n_uy_tax_category == "vat" and tax.price_include,
        ))
        fecha = fields.Date.to_string(self.date_order.date())
        is_credit = self._l10n_uy_edi_is_deferred_payment()
        due_date = self.account_move.invoice_date_due if is_credit else False
        return {
            "TipoCFE": int(self._l10n_uy_edi_get_document_type().code),  # A2
            "FchEmis": fecha,  # A5
            "MntBruto": 1 if tax_included else None,  # A10
            "FmaPago": 2 if is_credit else 1,  # A11 (1 contado, 2 credito)
            "FchVenc": fields.Date.to_string(due_date) if due_date else fecha,  # A12
            "ClauVenta": None,  # A13 (expo only)
            "ModVenta": None,  # A14 (expo only)
            "ViaTransp": None,  # A15 (expo only)
            "InfoAdicionalDoc": None,  # A16 (no addenda in POS)
        }

    def _l10n_uy_edi_cfe_A_issuer(self):
        """ XML Section A (Encabezado / Emisor) """
        self.ensure_one()
        company = self.company_id
        return {
            "RUCEmisor": stdnum.uy.rut.compact(company.vat),  # A40
            "RznSoc": company.name[:150],  # A41
            "CdgDGISucur": company.l10n_uy_edi_branch_code,  # A47
            "DomFiscal": company.partner_id._l10n_uy_edi_get_fiscal_address(),  # A48
            "Ciudad": company.city[:30],  # A49
            "Departamento": company.state_id.name[:30],  # A50
            "InfoAdicionalEmisor": None,  # A51 (no addenda in POS)
        }

    def _l10n_uy_edi_cfe_A_receptor(self):
        """ XML Section A (Encabezado / Receptor) """
        self.ensure_one()
        partner = self.partner_id
        commercial_partner = partner.commercial_partner_id
        doc_number = commercial_partner._get_preferred_legal_entity_identifier_vals().get("value", "")
        if not doc_number and not self._l10n_uy_edi_needs_receptor():
            return {}

        doc_type = partner._l10n_uy_edi_get_dgi_code()

        # Available receiver information is always sent, as Uruware does
        return {
            "TipoDocRecep": doc_type or None,  # A60
            "CodPaisRecep": partner.country_id.code or ("UY" if doc_type in [2, 3] else "99"),  # A61
            "DocRecep": doc_number if doc_type in [1, 2, 3] else None,  # A62
            "DocRecepExt": doc_number if doc_type not in [1, 2, 3] else None,  # A62.1
            "RznSocRecep": commercial_partner.name[:150] or None,  # A63
            "DirRecep": partner._l10n_uy_edi_get_fiscal_address() or None,  # A64
            "CiudadRecep": partner.city[:30] if partner.city else None,  # A65
            "DeptoRecep": partner.state_id.name[:30] if partner.state_id else None,  # A66
            "PaisRecep": partner.country_id.name if partner.country_id else None,  # A66.1
            "InfoAdicional": None,  # A68 (no addenda in POS)
            "CompraID": None,  # A70 (a POS order carries no customer reference)
        }

    def _l10n_uy_edi_cfe_B_details(self, base_lines):
        """ XML Section B (Detalle), amounts in the currency of the receipt, not in pesos """
        self.ensure_one()
        res = []
        for k, base_line in enumerate(
            (bl for bl in base_lines if not self._l10n_uy_edi_is_global_discount_line(bl)), 1,
        ):
            line = base_line["record"]
            # A CFE-eligible line carries a single tax, see _l10n_uy_edi_check_order
            taxes_data = base_line["tax_details"]["taxes_data"]
            tax_included = bool(taxes_data) and taxes_data[0]["tax"].price_include

            invoice_ind = self._l10n_uy_edi_get_invoice_indicator(line)
            nom_item, item_description = self._l10n_uy_edi_get_line_nom_and_desc(line)
            total = line.price_subtotal_incl if tax_included else line.price_subtotal
            quantity = base_line["quantity"]
            price_unit = base_line["price_unit"]
            discount = base_line["discount"]
            uom = base_line["product_uom_id"]

            temp = {
                "NroLinDet": k,  # B1
                "IndFact": invoice_ind,  # B4
                "NomItem": nom_item,  # B7
                "DscItem": item_description if item_description else None,  # B8
                "Cantidad": abs(quantity) if invoice_ind == 7 else quantity,  # B9
                "UniMed": uom.name[:4] if uom else "N/A",  # B10
                "PrecioUnitario": abs(price_unit),  # B11
                "DescuentoPct": discount,  # B12
                "DescuentoMonto": (abs(quantity) * abs(price_unit) - abs(total)) if discount else None,  # B13
                "MontoItem": abs(total),  # B24
            }

            if invoice_ind == 5:
                temp.update({}.fromkeys(["PrecioUnitario", "DescuentoMonto", "DescuentoPct"], 0.0))

            res.append(temp)
        return res

    def _l10n_uy_edi_cfe_C_totals(self, base_lines):
        """ XML Section C (SUBTOTALES INFORMATIVOS) """
        self.ensure_one()
        neto = {10.0: 0.0, 22.0: 0.0, 0.0: 0.0}
        base = neto.copy()

        for base_line in base_lines:
            for tax_data in base_line["tax_details"]["taxes_data"]:
                tax_amount = tax_data["tax"].amount
                key = tax_amount if tax_amount in neto else "reduced_tax"
                neto[key] = neto.get(key, 0) + tax_data["base_amount_currency"]
                base[key] = base.get(key, 0) + tax_data["tax_amount_currency"]

        nf_amount = sum(
            self.lines.filtered(lambda line: line.product_id.l10n_uy_edi_is_non_billable).mapped("price_subtotal"),
        )
        # A negative document (a POS refund): the CFE reports its amounts unsigned
        amount_total = abs(self.amount_total)
        total = abs(self.amount_total - nf_amount) if nf_amount else amount_total

        return {
            "TpoMoneda": (self.currency_id or self.company_id.currency_id).name,  # A110
            "TpoCambio": self._l10n_uy_edi_get_used_rate(),  # A111
            "MntExpoyAsim": None,  # A113 (expo only)
            "MntNoGrv": neto[0.0],  # A112
            "MntNetoIvaTasaMin": neto[10.0],  # A116
            "IVATasaMin": 10 if neto[10.0] else None,  # A119
            "MntNetoIVATasaBasica": neto[22.0],  # A117
            "MntNetoIVAOtra": neto.get("reduced_tax"),  # A118
            "IVATasaBasica": 22 if neto[22.0] else None,  # A120
            "MntIVATasaMin": base[10.0],  # A121
            "MntIVATasaBasica": base[22.0],  # A122
            "MntIVAOtra": base.get("reduced_tax"),  # A123
            "MntTotal": total,  # A124
            "CantLinDet": len(self.lines.filtered(  # A126
                lambda line: line.price_unit >= 0 or line.product_id.l10n_uy_edi_is_non_billable,
            )),
            "MontoNF": nf_amount or None,
            "MntPagar": amount_total,  # A130
        }

    def _l10n_uy_edi_cfe_D_global_discount(self, base_lines):
        """ XML Section D (Descuentos y recargos): the lines with a negative unit price """
        self.ensure_one()
        res = []
        for k, base_line in enumerate(
            (bl for bl in base_lines if self._l10n_uy_edi_is_global_discount_line(bl)), 1,
        ):
            line = base_line["record"]
            res.append({
                "NroLinDR": k,  # D1
                "TpoMovDR": "D",  # D2
                "TpoDR": 1,  # D3
                "GlosaDR": (line.full_product_name or "")[:100] or self.env._("Discount"),  # D5
                "ValorDR": abs(base_line["tax_details"]["raw_total_excluded_currency"]),  # D6
                "IndFactDR": self._l10n_uy_edi_get_invoice_indicator(line),  # D7
            })
        return res

    def _l10n_uy_edi_get_original_cfe_document(self):
        """ CFE of the refunded order, taken from the order itself or from its invoice """
        self.ensure_one()
        original = self.refunded_order_id
        return original.l10n_uy_edi_document_id or original.account_move.l10n_uy_edi_document_id

    def _l10n_uy_edi_cfe_F_reference(self):
        """ XML Section F (REFERENCE INFORMATION) - for credit note e-Tickets (refunds). """
        self.ensure_one()
        res = []
        if self._l10n_uy_edi_get_document_type().internal_type == "credit_note":
            original = self.refunded_order_id
            original_doc = self._l10n_uy_edi_get_original_cfe_document()
            cfe_serie, cfe_number = self.env["l10n_uy_edi.document"]._get_doc_parts(original_doc)
            original_currency = original.currency_id or original.company_id.currency_id
            res.append({
                "NroLinRef": 1,  # F1
                "TpoDocRef": int(original_doc.l10n_latam_document_type_id.code),  # F3
                "Serie": cfe_serie,  # F4
                "NroCFERef": cfe_number,  # F5
                "FechaCFEref": original.date_order.date(),  # F7
                "MntCFEref": abs(original.amount_total),  # F8
                "TpoMonedaRef": original_currency.name,  # F9
                "TpoCambioRef": original._l10n_uy_edi_get_used_rate(),  # F10
            })
        return res

    def _l10n_uy_edi_get_xml_content(self):
        """ Create the e-Ticket CFE xml structure of this order.

        :return: bytes, the xml content to send to DGI """
        self.ensure_one()
        base_lines = self._l10n_uy_edi_get_base_lines()
        cfe = self.env["ir.qweb"]._render("l10n_uy_edi.eTck_template", values={
            # l10n_uy_edi_stock guards a few tags on the document type of the CFE being rendered
            "cfe": self.l10n_uy_edi_document_id,
            "IdDoc": self._l10n_uy_edi_cfe_A_iddoc(),
            "emisor": self._l10n_uy_edi_cfe_A_issuer(),
            "receptor": self._l10n_uy_edi_cfe_A_receptor(),
            "item_detail": self._l10n_uy_edi_cfe_B_details(base_lines),
            "totals_detail": self._l10n_uy_edi_cfe_C_totals(base_lines),
            "global_discounts": self._l10n_uy_edi_cfe_D_global_discount(base_lines),
            "referencia_lines": self._l10n_uy_edi_cfe_F_reference(),
            "format_float": format_float,
        })
        return etree.tostring(cleanup_xml_node(cfe))
