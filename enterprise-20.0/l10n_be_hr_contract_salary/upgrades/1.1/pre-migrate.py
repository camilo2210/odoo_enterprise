# Part of Odoo. See LICENSE file for full copyright and licensing details.

def migrate(cr, version):
    cr.execute("""
        UPDATE hr_contract_salary_benefit b
           SET source = 'field',
               salary_rule_id = NULL,
               res_field_id = f.id,
               cost_res_field_id = f.id
          FROM ir_model_data d,
               ir_model_fields f
         WHERE d.res_id = b.id
           AND d.module = 'l10n_be_hr_contract_salary'
           AND d.name = 'l10n_be_representation_fees'
           AND f.model = 'hr.version'
           AND f.name = 'representation_fees'
        """)
