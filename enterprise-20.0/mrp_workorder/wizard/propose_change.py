# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.tools import is_html_empty
from odoo.tools.image import image_process
from odoo.tools.mimetypes import guess_mimetype


class ProposeChange(models.TransientModel):
    _name = 'propose.change'
    _description = 'Propose a change in the production'

    workorder_id = fields.Many2one(
        'mrp.workorder', 'Workorder', required=True, ondelete='cascade')
    title = fields.Char('Title')
    step_id = fields.Many2one('quality.check', 'Step to change')
    note = fields.Html('New Instruction')
    comment = fields.Char('Comment')
    picture = fields.Binary('Picture')
    change_type = fields.Selection([
        ('update_step', 'Update Current Step'),
        ('remove_step', 'Remove Current Step'),
        ('set_picture', 'Add Picture')], 'Type of Change')

    @api.model
    def default_get(self, fields):
        defaults = super().default_get(fields)
        if 'step_id' in defaults:
            step = self.env['quality.check'].browse(defaults.get('step_id'))
            defaults['title'] = step.title
            if defaults.get('change_type') == 'update_step':
                defaults['note'] = step.note
        return defaults

    def process(self):
        for wizard in self:
            if wizard.change_type == 'update_step':
                wizard._do_update_step()
            elif wizard.change_type == 'remove_step':
                wizard._do_remove_step()
            elif wizard.change_type == 'set_picture':
                wizard._do_set_picture()

    def _workorder_name(self):
        if self.workorder_id.employee_id:
            return self.workorder_id.employee_id.name
        return self.env.user.name

    def _get_update_step_note(self, original_title=False):
        tl_text = _("New Instruction suggested by %(user_name)s", user_name=self._workorder_name())
        body = Markup("<b>%s</b>") % tl_text
        if self.note and not is_html_empty(self.note):
            body += Markup("<br/><b>%s</b>%s") % (_("Instruction:"), self.note)
        if self.comment:
            body += Markup("<br/><b>%s</b> %s") % (_("Reason:"), self.comment)
        if self.title and self.title != original_title:
            body += Markup("<br/><b>%s %s</b>") % (_("New Title suggested:"), self.title)
        return body

    def _do_update_step(self, notify_bom=True):
        self.ensure_one()
        self.step_id.note = self.note
        if notify_bom and self.workorder_id.production_id.bom_id:
            body = _('BoM feedback %(step)s (%(production)s - %(operation)s)', step=self.step_id.title, production=self.workorder_id.production_id.name, operation=self.workorder_id.operation_id.name)
            body += Markup("<br/>%s") % self._get_update_step_note(self.step_id.title)
            self.workorder_id.production_id.bom_id.sudo().message_post(body=body)
        if self.title and self.title != self.step_id.title:
            self.step_id.title = self.title

    def _get_remove_step_note(self):
        tl_text = _("%(user_name)s suggests to delete this instruction", user_name=self._workorder_name())
        body = Markup("<b>%s</b>") % tl_text
        if self.comment:
            body += Markup("<br/><b>%s</b> %s") % (_("Reason:"), self.comment)
        return body

    def _do_remove_step(self, notify_bom=True):
        self.ensure_one()
        if not self.step_id.point_id and not (self.step_id.test_type.startswith('register_')):
            # remove additionmal step
            self.step_id.workorder_id._change_quality_check('next')
            self.step_id.unlink()
        bom = self.step_id.workorder_id.production_id.bom_id
        if notify_bom and bom:
            body = _('BoM feedback %(step)s (%(production)s - %(operation)s)', step=self.step_id.title, production=self.workorder_id.production_id.name, operation=self.workorder_id.operation_id.name)
            body += Markup("<br/>%s") % self._get_remove_step_note()
            bom.message_post(body=body)

    def _get_set_picture_note(self):
        lt_text = _("%(user_name)s suggests to add this picture to the instruction", user_name=self._workorder_name())
        return Markup('<b>%s</b>') % lt_text

    def _create_picture_markup(self, record):
        picture = image_process(self.picture.content, verify_resolution=True)
        attachment = self.env['ir.attachment'].create({
            'name': self.picture.filename or 'instruction_picture',
            'raw': picture,
            'mimetype': guess_mimetype(picture),
            'res_model': record._name,
            'res_id': record.id,
        })
        return Markup('<p><img class="img-fluid" src="%s"/></p>') % attachment.image_src

    def _do_set_picture(self, notify_bom=True):
        self.ensure_one()
        self.step_id.note = (self.step_id.note or Markup()) + self._create_picture_markup(self.step_id)
        bom = self.step_id.workorder_id.production_id.bom_id
        if notify_bom and bom:
            body = _('BoM feedback %(step)s (%(production)s - %(operation)s)', step=self.step_id.title, production=self.workorder_id.production_id.name, operation=self.workorder_id.operation_id.name)
            body += Markup("<br/>%s") % self._get_set_picture_note()
            bom.message_post(body=body, attachments=[(self.picture.filename or 'instruction_picture', self.picture)])
