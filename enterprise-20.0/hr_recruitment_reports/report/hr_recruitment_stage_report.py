# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools.sql import drop_view_if_exists, SQL


class HrRecruitmentStageReport(models.Model):
    _name = 'hr.recruitment.stage.report'
    _description = 'Recruitment Stage Analysis'
    _auto = False

    applicant_id = fields.Many2one('hr.applicant', readonly=True)
    name = fields.Char('Applicant Name', readonly=True)
    stage_id = fields.Many2one('hr.recruitment.stage', readonly=True)
    job_id = fields.Many2one('hr.job', readonly=True)
    days_in_stage = fields.Float(readonly=True, aggregator='avg', string="Average Days in Stage")

    state = fields.Selection([
        ('is_hired', 'Hired'),
        ('in_progress', 'In Progress'),
        ('refused', 'Refused'),
        ('archived', 'Archived'),
    ], readonly=True)

    company_id = fields.Many2one('res.company', readonly=True)
    date_begin = fields.Date('Start Date', readonly=True)
    date_end = fields.Date('End Date', readonly=True)

    def init(self):
        drop_view_if_exists(self.env.cr, self._table)
        query = """
WITH application_by_stage AS (
    SELECT a.id,
           a.create_date,
           a.date_closed,
           CASE
               WHEN s.hired_stage THEN a.date_closed
               ELSE a.create_date
                    + (SUM(step.duration::int)
                       OVER (PARTITION BY a.id ORDER BY s.sequence))
                      * INTERVAL '1 second'
           END AS date_end,
           step.stage_id::int AS stage_id,
           step.duration::int AS duration,
           s.sequence
    FROM hr_applicant a
         CROSS JOIN LATERAL jsonb_each(
             (a.duration_tracking - 'd' - 's')
             || jsonb_build_object(
                    a.duration_tracking->>'s',
                    EXTRACT(EPOCH
                            FROM (now()
                                  - (a.duration_tracking->>'d')::timestamptz))::int
                    + COALESCE(
                          a.duration_tracking->>(
                              a.duration_tracking->>'s'),
                          '0')::int))
             AS step(stage_id, duration)
         JOIN hr_recruitment_stage s
              ON s.id = step.stage_id::int
    WHERE s.hired_stage IS NOT TRUE
      AND a.job_id IS NOT NULL
),
application_by_start_stage AS (
    SELECT id,
           LAG(date_end, 1, create_date)
               OVER (PARTITION BY id ORDER BY sequence) AS date_begin,
           date_end,
           stage_id
    FROM application_by_stage
),
global_cte AS (
    SELECT abs.id AS applicant_id,
           abs.stage_id,
           abs.date_begin,
           abs.date_end,
           ha.partner_name AS name,
           ha.job_id,
           ha.company_id,
           CASE
               WHEN ha.active IS FALSE
                    AND ha.refuse_reason_id IS NOT NULL THEN 'refused'
               WHEN ha.active IS FALSE
                    AND ha.refuse_reason_id IS NULL THEN 'archived'
               WHEN ha.date_closed IS NOT NULL THEN 'is_hired'
               ELSE 'in_progress'
           END AS state,
           CASE
               WHEN ha.refuse_date IS NOT NULL THEN
                   ABS(EXTRACT(DAY
                               FROM abs.date_end
                                    - COALESCE(ha.refuse_date,
                                               ha.create_date)))
               ELSE
                   EXTRACT(DAY
                           FROM abs.date_end - abs.date_begin)
           END AS days_in_stage
    FROM application_by_start_stage abs
         JOIN hr_applicant ha
              ON ha.id = abs.id
)
SELECT ROW_NUMBER() OVER (ORDER BY date_begin) AS id, *
  FROM global_cte
        """
        self.env.cr.execute(SQL("CREATE OR REPLACE VIEW %s AS (%s)", SQL.identifier(self._table), SQL(query)))
