# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MailActivityPlanTemplate(models.Model):
    _inherit = 'mail.activity.plan.template'

    sign_template_id = fields.Many2one(
        'sign.template',
        compute='_compute_sign_template_id',
        store=True,
        readonly=False,
        string='Document to sign'
    )

    @api.constrains('sign_template_id', 'activity_type_id')
    def _check_sign_template_category(self):
        for template in self:
            if template.sign_template_id and template.activity_type_id.category != 'sign_request':
                raise ValidationError(
                    self.env._("You can only set a sign template for activities of type 'Signature'.")
                )

    @api.depends('activity_type_id')
    def _compute_sign_template_id(self):
        for template in self:
            template.sign_template_id = template.activity_type_id.default_sign_template_id

    @api.depends('sign_template_id')
    def _compute_summary(self):
        super()._compute_summary()

        for template in self:
            if template.activity_type_id.category == 'sign_request' and template.sign_template_id:
                if not template.summary:
                    template.summary = template.activity_type_id.name

                template.summary = self.env._("%(summary)s: %(name)s",
                                              summary=template.summary,
                                              name=template.sign_template_id.name)
