# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class TestAiImageGeneration(models.Model):
    _description = "Test AI Image Generation"
    _name = 'test.ai.image.generation'

    name = fields.Char()
    binary_field = fields.Binary(attachment=True, groups="base.group_system")
