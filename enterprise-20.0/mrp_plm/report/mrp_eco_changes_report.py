from odoo import models


class ReportMrpPlmEcoChanges(models.AbstractModel):
    _name = 'report.mrp_plm.eco_changes'
    _description = 'ECO Changes Summary Report'

    def _get_report_context(self, eco):
        """Return extra display context for the ECO changes report."""

        return {
            'display_description':
                any(c.description for c in eco.routing_change_ids)
                or any(l.description for l in eco.bom_change_ids),
            'show_uom': self.env.user.has_group('uom.group_uom'),
        }

    def _get_report_values(self, docids, data=None):
        docs = self.env['mrp.eco'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'mrp.eco',
            'docs': docs,
            'eco_contexts': {eco.id: self._get_report_context(eco) for eco in docs},
        }
