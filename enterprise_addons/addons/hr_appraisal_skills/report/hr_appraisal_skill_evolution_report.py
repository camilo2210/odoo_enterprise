# Part of Odoo. See LICENSE file for full copyright and licensing licensing details.

from odoo import fields, models, tools


class HrAppraisalSkillEvolutionReport(models.BaseModel):
    _name = 'hr.appraisal.skill.evolution.report'
    _auto = False
    _description = 'Appraisal Skill Evolution Report'
    _order = 'date desc, skill_type_id asc, skill_id asc'

    id = fields.Id()
    date = fields.Date(string='Date', readonly=True)
    skill_id = fields.Many2one('hr.skill', string='Skill', readonly=True)
    skill_type_id = fields.Many2one('hr.skill.type', string='Skill Type', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    department_id = fields.Many2one('hr.department', readonly=True)
    level_progress_average = fields.Float(string="Average Progress (%)", readonly=True, aggregator='avg')
    level_progress_count = fields.Integer(string="Total Assessed", readonly=True, aggregator='sum')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
        """CREATE OR REPLACE VIEW %s AS (
            WITH
                dates AS (
                    SELECT DISTINCT date
                    FROM (
                        SELECT valid_from as date FROM hr_employee_skill
                        UNION
                        SELECT valid_to as date FROM hr_employee_skill WHERE valid_to IS NOT NULL
                    )
                    ORDER BY date ASC
                ),
                active_employees AS (
                    SELECT id, company_id, current_version_id
                    FROM hr_employee
                    WHERE active IS TRUE
                ),
                skill_history AS (
                    SELECT DISTINCT ON(d.date, e.id, es.skill_id)
                        d.date,
                        e.company_id,
                        v.department_id,
                        e.id AS employee_id,
                        st.id AS skill_type_id,
                        es.skill_id,
                        sl.level_progress
                    FROM dates AS d
                    CROSS JOIN active_employees AS e
                    INNER JOIN hr_version AS v ON v.id = e.current_version_id
                    INNER JOIN hr_employee_skill AS es ON es.employee_id = e.id
                    INNER JOIN hr_skill_level AS sl ON sl.id = es.skill_level_id
                    INNER JOIN hr_skill_type AS st ON st.id = es.skill_type_id
                    WHERE d.date >= es.valid_from AND (es.valid_to IS NULL OR d.date <= es.valid_to)
                    ORDER BY d.date, e.id, es.skill_id, es.valid_from DESC
                )
            SELECT
                row_number() OVER () AS id,
                h.date,
                h.company_id,
                h.department_id,
                h.employee_id,
                h.skill_type_id,
                h.skill_id,
                h.level_progress as level_progress_average,
                1 as level_progress_count
            FROM skill_history AS h
        )""" % (self._table, ))
