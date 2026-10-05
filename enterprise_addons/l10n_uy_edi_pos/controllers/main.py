from odoo import http
from odoo.http import request
from odoo.tools import format_amount

from odoo.addons.point_of_sale.controllers.main import PosController


class L10nUyPosController(PosController):

    @http.route()
    def show_ticket_validation_screen(self, access_token="", **kwargs):
        """ EXTENDS point_of_sale: serve the CFE of a UY e-Ticket instead of the invoice form """
        order = access_token and request.env["pos.order"].sudo().search(
            [("access_token", "=", access_token)], limit=1,
        )
        if order and not order.is_singly_invoiced and order.l10n_uy_edi_is_enabled:
            pdf = order._l10n_uy_edi_get_pdf() or order._l10n_uy_edi_ensure_pdf()
            return request.render("l10n_uy_edi_pos.ticket_cfe_screen", {
                "pos_order": order,
                "pdf_url": pdf and "/web/content/%s?access_token=%s&download=true" % (
                    pdf.id, pdf.generate_access_token()[0],
                ),
                "format_amount": format_amount,
                "env": request.env,
            })

        return super().show_ticket_validation_screen(access_token=access_token, **kwargs)
