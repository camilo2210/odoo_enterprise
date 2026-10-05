
from odoo import fields, models


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    sign_request_id = fields.Many2one('sign.request', string='Sign Requests', index='btree_not_null')
    sign_template_id = fields.Many2one('sign.template', related="activity_template_id.sign_template_id", string='Sign Templates')

    def _store_activity_fields(self, res):
        super()._store_activity_fields(res)

        res.one(
            "sign_request_id",
            lambda res: (
                res.extend(["id", "need_my_signature", "validity"]),
                res.one("create_uid", lambda res: res.one("partner_id", ["name"])),
                res.attr("template_name", lambda req: req.template_id.name),
                res.attr("signer_names", lambda req: ", ".join(req.request_item_ids.mapped("partner_id.name"))),
            ),
            sudo=True,
        )
        res.one("sign_template_id", ["id", "name"])

    def _compute_can_write(self):
        super()._compute_can_write()
        for record in self.filtered('can_write'):
            if record.sign_request_id and not record.sign_request_id.has_access('read'):
                record.can_write = False
