# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import api, fields, models, _


class MrpEcoUpdateProductVersion(models.TransientModel):
    _name = 'mrp.eco.update.product.version'
    _description = 'Update Product Versions'

    eco_id = fields.Many2one('mrp.eco', required=True, readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product', readonly=True)
    bom_id = fields.Many2one('mrp.bom', string='BoM', readonly=True)
    used_in_product_tmpl_ids = fields.Many2many('product.template', string="Parent Products", readonly=True)
    used_in_bom_ids = fields.Many2many('mrp.bom', string="Parent BoMs", readonly=True)

    update_product_version = fields.Boolean(default=True)
    update_bom_version = fields.Boolean()
    update_used_in_product_versions = fields.Boolean()
    update_used_in_bom_versions = fields.Boolean()

    product_version_label = fields.Char(readonly=True)
    bom_version_label = fields.Char(readonly=True)
    used_in_product_versions_label = fields.Char(readonly=True)
    used_in_bom_versions_label = fields.Char(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            wizard = self.new(vals)
            vals.update({
                'update_bom_version': bool(wizard.bom_id),
                'product_version_label': wizard._format_version_label(
                    _('Product %(product)s', product=wizard.product_tmpl_id.name),
                    wizard.product_tmpl_id,
                ),
                'bom_version_label': wizard._format_version_label(
                    _('Bill of Materials'),
                    wizard.bom_id,
                ),
                'used_in_product_versions_label': wizard._format_used_in_products_label(
                    len(wizard.used_in_product_tmpl_ids),
                ),
                'used_in_bom_versions_label': wizard._format_used_in_boms_label(
                    len(wizard.used_in_bom_ids),
                ),
            })
        return super().create(vals_list)

    def _format_version_label(self, label, record):
        if not record:
            return False
        return _(
            '%(label)s: %(old_version)s → %(new_version)s',
            label=label,
            old_version=record.version,
            new_version=record.version + 1,
        )

    def _format_used_in_products_label(self, count):
        if count == 1:
            return _('The 1 product using this product')
        return _('The %(count)s products using this product', count=count)

    def _format_used_in_boms_label(self, count):
        if count == 1:
            return _('The 1 BoM using this product')
        return _('The %(count)s BoMs using this product', count=count)

    def _update_versions(self, records):
        version_updates = []
        for record in records:
            old_version = record.version
            record.version += 1
            version_updates.append((record, old_version, record.version))
        return version_updates

    def action_apply(self):
        self.ensure_one()

        version_updates = []
        types_updated = [[], []]
        if self.update_product_version:
            version_updates.extend(self._update_versions(self.product_tmpl_id))
            types_updated[0].append(_("Product"))
        if self.update_bom_version:
            version_updates.extend(self._update_versions(self.bom_id))
            types_updated[1].append(_("BoM"))
        if self.update_used_in_product_versions:
            version_updates.extend(self._update_versions(self.used_in_product_tmpl_ids))
            types_updated[0].append(_("Parent Products"))
        if self.update_used_in_bom_versions:
            version_updates.extend(self._update_versions(self.used_in_bom_ids))
            types_updated[1].append(_("Parent BoMs"))
        if version_updates:
            self.eco_id._log_version_update(types_updated)
            self._log_record_version_updates(version_updates)
        return self.eco_id.action_apply()

    def _log_record_version_updates(self, version_updates):
        for record, old_version, new_version in version_updates:
            record_name = _("Product") if record._name == 'product.template' else _("BoM")
            label = _('%s version has been updated by:', record_name)
            body = Markup('<p><b>%s</b> %s<br/>V%s &rarr; V%s</p>') % (
                label,
                self.eco_id._get_html_link(),
                old_version,
                new_version,
            )
            record.message_post(body=body)
