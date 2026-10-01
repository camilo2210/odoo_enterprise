import json

from odoo import fields, models


class L10nVnReportsForm01GtgtExportWizard(models.TransientModel):
    _name = 'l10n_vn_reports.form_01_gtgt.export.wizard'
    _description = 'Vietnam Form 01/GTGT XML Export Wizard'

    business_activity = fields.Selection(
        selection=[
            ('ordinary', 'Ordinary business'),
            ('lottery', 'Lottery business'),
            ('petroleum', 'Petroleum exploration and exploitation business'),
            ('infrastructure_housing', 'Investment projects on infrastructure and housing for transfer located in a province other than where the head office is based'),
            ('power_generation', 'Power generation plant located in a province other than where the head office is based'),
        ],
        default='ordinary',
        required=True,
        string='Business activity type',
    )
    first_time = fields.Boolean(
        default=True,
        string='First submission',
    )
    adjustment_no = fields.Integer(
        default=0,
        string='Adjustment No',
    )
    dependent_unit_name = fields.Char(
        string='Name',
    )
    dependent_unit_tax_code = fields.Char(
        string='Tax code',
    )
    province_id = fields.Many2one(
        comodel_name='res.country.state',
        domain="[('country_id.code', '=', 'VN')]",
        string='Province/City',
    )
    district = fields.Char(
        string='District',
    )
    ward = fields.Char(
        string='Ward',
    )

    def action_generate_export(self):
        self.ensure_one()

        BUSINESS_ACTIVITY_DATA = {
            'ordinary': ('00', 'Hoạt động sản xuất kinh doanh thông thường'),
            'lottery': ('01', 'Hoạt động xổ số kiến thiết'),
            'petroleum': ('02', 'Hoạt động thăm dò khai thác dầu khí'),
            'infrastructure_housing': ('03', 'Dự án đầu tư cơ sở hạ tầng, nhà để chuyển nhượng khác tỉnh nơi đóng trụ sở chính'),
            'power_generation': ('04', 'Nhà máy sản xuất điện khác tỉnh nơi đóng trụ sở chính'),
        }

        activity_code, activity_label = BUSINESS_ACTIVITY_DATA[self.business_activity]
        show_dependent_unit = self.business_activity in ('infrastructure_housing', 'power_generation')

        options = dict(self.env.context.get('l10n_vn_reports_form_01_gtgt_options') or {})
        options['l10n_vn_xml_export'] = {
            'business_activity': self.business_activity,
            'business_activity_code': activity_code,
            'business_activity_label': activity_label,
            'first_time': self.first_time,
            'adjustment_no': self.adjustment_no,
            'show_dependent_unit': show_dependent_unit,
            'dependent_unit_name': self.dependent_unit_name or '',
            'dependent_unit_tax_code': self.dependent_unit_tax_code or '',
            'province_code': self.province_id.code or '',
            'province_name': self.province_id.name or '',
            'district': self.district or '',
            'ward': self.ward or '',
        }
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': 'account.report',
                'options': json.dumps(options),
                'file_generator': 'export_tax_report_to_xml',
            },
        }
