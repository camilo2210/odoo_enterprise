from odoo import fields, models


class QualityCheckLabelLayout(models.TransientModel):
    _name = 'quality.check.label.layout'
    _inherit = 'product.label.layout'
    _description = 'Quality Check Label Layout'

    quality_check_id = fields.Many2one('quality.check', required=True)

    def _get_label_template_xml_id(self):
        self.ensure_one()
        return 'mrp_workorder.quality_check_zpl_label' if self.print_format == 'zpl' else 'mrp_workorder.quality_check_4x12_label'

    def _get_label_requests(self):
        self.ensure_one()
        product = self.quality_check_id.product_id
        workorder = self.quality_check_id.workorder_id
        quantity = workorder.qty_producing or workorder.qty_production
        label_uom = workorder.uom_id
        return [{
            'product': product,
            'barcode_value': product.barcode or '',
            'copies': 1,
            'packaging': self.env['uom.uom'],
            'secondary_text': f'{quantity:g} {label_uom.display_name}',
        }]
