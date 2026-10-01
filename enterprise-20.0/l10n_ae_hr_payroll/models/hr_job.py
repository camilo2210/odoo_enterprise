from odoo import fields, models


class HrJob(models.Model):
    _inherit = "hr.job"

    l10n_ae_mohre_skill_level = fields.Selection(
        selection=[
            ("1", "Legislators, Senior Officials & Managers"),
            ("2", "Professionals (Science, Technical, Business, etc."),
            ("3", "Technicians & Associate Professionals"),
            ("4", "Clerical Support Workers"),
            ("5", "Service & Sales Workers"),
            ("6", "Skilled Agriculture, Forestry & Fishery Workers"),
            ("7", "Craft & Related Trades Workers"),
            ("8", "Plant & Machine Operators & Assemblers"),
            ("9", "Elementary/Simple Occupations"),
        ],
        string="MOHRE Skill Level",
        help="Employee’s Skill Level as defined by MOHRE regulations under the UAE Labour Law."
            "It is used for Emiratization compliance calculations")
