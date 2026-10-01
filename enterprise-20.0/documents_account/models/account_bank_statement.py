# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountBankStatement(models.Model):
    _name = 'account.bank.statement'
    _inherit = ['account.bank.statement']
