# -*- coding: utf-8 -*-
from odoo import api, models


class L10n_Mx_EdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    @api.model
    def _get_cfdi_values(self, cfdi_node):
        # EXTENDS 'l10n_mx_edi'
        cfdi_values = super()._get_cfdi_values(cfdi_node)
        external_trade_node = self._get_cfdi_node(cfdi_node, "//*[local-name()='ComercioExterior']")
        if external_trade_node is None:
            return cfdi_values

        cfdi_values.update({
            'ext_trade_node': external_trade_node,
            'ext_trade_certificate_key': external_trade_node.get('ClaveDePedimento', ''),
            'ext_trade_certificate_source': external_trade_node.get('CertificadoOrigen', '').replace('0', 'No').replace('1', 'Si'),
            'ext_trade_nb_certificate_origin': external_trade_node.get('CertificadoOrigen', ''),
            'ext_trade_certificate_origin': external_trade_node.get('NumCertificadoOrigen', ''),
            'ext_trade_nb_reliable_exporter': external_trade_node.get('NumeroExportadorConfiable', ''),
            'ext_trade_incoterm': external_trade_node.get('Incoterm', ''),
            'ext_trade_rate_usd': external_trade_node.get('TipoCambioUSD', ''),
            'ext_trade_total_usd': external_trade_node.get('TotalUSD', ''),
        })
        return cfdi_values
