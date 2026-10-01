# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SignItemOption(models.Model):
    _name = 'sign.item.option'
    _description = "Option of a selection Field"
    _rec_name = "value"

    value = fields.Text(string="Option", readonly=True)

    _value_uniq = models.Constraint(
        'unique (value)',
        "Value already exists!",
    )

    def get_selection_ids_from_value(self, options):
        """This method takes a list of text options, checks which options
        already exist in the database, creates the missing ones, and
        returns a list of IDs corresponding to all provided options
        (both existing and newly created).
        """
        options = list(dict.fromkeys(options))

        existing_records = self.search([('value', 'in', options)])
        val_to_id = {rec.value: rec.id for rec in existing_records}

        existing_values = set(val_to_id.keys())
        new_options = [option for option in options if option not in existing_values]
        if new_options:
            created_records = self.create([{'value': option} for option in new_options])
            for rec in created_records:
                val_to_id[rec.value] = rec.id

        return [val_to_id[option] for option in options]
