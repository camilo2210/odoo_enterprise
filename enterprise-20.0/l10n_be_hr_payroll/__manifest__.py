# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Belgium - Payroll',
    'countries': ['be'],
    'category': 'Human Resources/Payroll',
    'depends': ['certificate', 'hr_payroll', 'hr_holidays', 'hr_address_extended', 'hr_payroll_fleet', 'web_enterprise'],
    'auto_install': ['hr_payroll'],
    'external_dependencies': {
        'python': ['paramiko', 'pyjwt'],
        'apt': {
            'paramiko': 'python3-paramiko',
            'pyjwt': 'python3-jwt',
        },
    },
    'description': """
Belgian Payroll Rules.
======================

    * Employee Details
    * Employee Contracts
    * Passport based Contract
    * Allowances/Deductions
    * Allow to configure Basic/Gross/Net Salary
    * Employee Payslip
    * Monthly Payroll Register
    * Integrated with Leaves Management
    * Salary Maj, ONSS, Withholding Tax, Child Allowance, ...

Automatic DmfA Signature
========================

Prerequisites:
--------------

- You need a Belgian Government Compliant Digital Certificate, delivered by Global
  Sign. See: https://shop.globalsign.com/en/belgian-government-services

- Generate certificate files from your SSL certificate (.pfx file) that are needed to create
  a technical user (.cer file) and to authenticate remotely to the ONSS (.pem) file. On a UNIX
  system, you may use the following commands:

  - PFX -> CRT: openssl pkcs12 -in my_cert.pfx -out my_cert.crt -nokeys -clcerts

  - CRT -> CER: openssl x509 -inform pem -in my_cert.crt -outform der -out my_cert.cer

  - PFX -> PEM: openssl pkcs12 -in my_cert.pfx -out my_cert.pem -nodes

  - PFX -> KEY: openssl pkcs12 -in my_cert.pfx -out my_cert.key -nocerts

- Before you can use the social security SFTP service, you must create an account
  for yourself or for your client and configure the security. (The whole procedure is
  available at https://www.socialsecurity.be/site_fr/general/helpcentre/batch/sftp/previewstep.htm)

  - Create a technical user + Activate a SFTP channel: Your client must now create a technical user in the Access management
    online service. The follow this procedure: https://www.socialsecurity.be/site_fr/general/helpcentre/rest/documents/pdf/webservices_creer_le_canal_FR.pdf

  - Configure your SFTP client: https://www.socialsecurity.be/site_fr/general/helpcentre/batch/document/pdf/step6_sftp_F.pdf

  - At the end of the procedure, you should have received a "ONSS Expeditor Number", you may
    encode in in the payroll Settings, with the .pem file and the related password, if any.

- Configuration note: The .pfx certificate should be set on the payroll configuration.

Synchronize DmfA to ONSS portal
===============================

Automates the synchronization of DmfA ONSS declarations
to the official Belgian SFTP portal.

- Upload the FO, FS, and GO files to the correct ONSS environment folder
  (IN, INTEST, INTEST-S).
- Poll the OUT folders (OUT, OUTTEST, OUTTEST-S) for returned files.
- Link received files to the corresponding declarations and employees
  when applicable.

Technical features include:
- Secure connection using a private key and technical user credentials.
- XML file parsing for ACRF and notification files.
- Error handling and logging for missing directories or malformed files.

This feature ensures compliance with ONSS electronic declaration
requirements and reduces manual interaction with the SFTP portal.

Automatic DIMONA declarations
=============================

- You need a Belgian Government Compliant Digital Certificate, delivered by Global
  Sign. See: https://shop.globalsign.com/en/belgian-government-services

- Generate certificate files from your SSL certificate (.pfx file) that are needed to create
  a technical user (.cer file) and to authenticate remotely to the ONSS (.pem) file. On a UNIX
  system, you may use the following commands:

  - PFX -> CRT: openssl pkcs12 -in my_cert.pfx -out my_cert.crt -nokeys -clcerts

  - CRT -> CER: openssl x509 -inform pem -in my_cert.crt -outform der -out my_cert.cer

  - PFX -> PEM: openssl pkcs12 -in my_cert.pfx -out my_cert.pem -nodes

- Before you can use the social security REST web service, you must create an account
  for yourself or for your client and configure the security. (The whole procedure is
  available at https://www.socialsecurity.be/site_fr/employer/applics/dimona/introduction/webservice.htm)

  - User account management: Follow the Procedure https://www.socialsecurity.be/site_fr/general/helpcentre/rest/documents/pdf/procedure_pour_gestion_des_acces_UMan_FR.pdf

  - Create a technical user: Your client must now create a technical user in the Access management
    online service. The follow this procedure: https://www.socialsecurity.be/site_fr/general/helpcentre/rest/documents/pdf/webservices_creer_le_canal_FR.pdf

  - Activate a web service channel: Once the technical user has been created, your client must
    activate the web service channel in Access Management. The following manual explains the
    steps to follow to activate the channel: https://www.socialsecurity.be/site_fr/general/helpcentre/rest/documents/pdf/webservices_ajouter_le_canal_FR.pdf

  - At the end of the procedure, you should receive a "ONSS Expeditor Number", you may
    encode in in the payroll Settings, with the .pem file and the related password, if any.
    """,
    'data': [
        'security/l10n_be_hr_payroll_security.xml',
        'data/report_paperformat.xml',
        'data/hr_salary_rule_category_data.xml',
        'views/menuitems.xml',
        'views/report_payslip_templates.xml',
        'views/reports.xml',
        'wizard/l10n_be_hr_payroll_schedule_change_wizard_views.xml',
        'wizard/hr_payroll_allocating_paid_time_off_views.xml',
        'views/hr_contract_template_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_work_entry_type_views.xml',
        'views/hr_employee_departure_views.xml',
        'views/report_termination_fees.xml',
        'views/report_termination_holidays.xml',
        'views/hr_dmfa_template.xml',
        'views/hr_dmfa_consultation_template.xml',
        'views/hr_dmfa_modification_template.xml',
        'views/l10n_be_flexi_at_work_template.xml',
        'views/wech009_xml_export_template.xml',
        'views/wech010_xml_export_template.xml',
        'views/hr_dmfa_views.xml',
        'views/l10n_be_flexi_at_work_views.xml',
        'views/hr_work_location_views.xml',
        'views/l10n_be_onss_file_views.xml',
        'views/l10n_be_onss_declaration_views.xml',
        'views/hr_departure_reason_views.xml',
        'views/273_xx_xml_export_template.xml',
        'views/281_10_xml_export_template.xml',
        'views/281_13_xml_export_template.xml',
        'views/281_18_xml_export_template.xml',
        'views/281_20_xml_export_template.xml',
        'views/281_30_xml_export_template.xml',
        'views/281_45_xml_export_template.xml',
        'views/281_xx_xml_export_template.xml',
        'views/withholding_tax_xml_export_template.xml',
        'views/hr_leave_views.xml',
        'views/l10n_be_dimona_declaration_views.xml',
        'views/l10n_be_dimona_period_views.xml',
        'views/l10n_be_dimona_relation_views.xml',
        'views/l10n_be_worker_code_views.xml',
        'views/hr_salary_rule_views.xml',
        'wizard/l10n_be_dimona_wizard_views.xml',
        'wizard/l10n_be_dimona_manual_wizard_views.xml',
        'wizard/l10n_be_fetch_dimona_sandbox_views.xml',
        'wizard/l10n_be_check_dimona_sandbox_views.xml',
        'views/l10n_be_reorganisation_measure_views.xml',
        'views/l10n_be_employer_category_views.xml',
        'views/l10n_be_nace_code_views.xml',
        'views/l10n_be_holiday_attest.xml',
        'views/resource_calendar_views.xml',
        'views/l10n_be_meal_voucher_report_views.xml',
        'views/res_config_settings_views.xml',
        'views/payroll_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/hr_employee_type_views.xml',
        'views/hr_leave_allocation_views.xml',
        'views/hr_payslip_views.xml',
        'views/fleet_views.xml',
        'views/hr_payroll_warning_views.xml',
        'views/hr_salary_attachment_views.xml',
        'data/res_partner_data.xml',
        'data/hr_employee_type_data.xml',
        'data/l10n.be.worker.code.csv',
        'data/l10n.be.drs.risk.csv',
        'data/resource_calendar_data.xml',
        'data/hr_payroll_warning_data.xml',
        'data/l10n.be.joint.committee.csv',
        'data/hr_payroll_structure_data.xml',
        'data/hr_work_entry_type_data.xml',
        'data/hr_time_rule_data.xml',
        'data/hr_rule_parameters_data.xml',
        'data/ir_config_parameter_data.xml',
        'data/hr_departure_reason_data.xml',
        'data/hr_salary_rule_section_data.xml',
        'data/l10n.be.nace.code.csv',
        'data/hr_salary_rule_data.xml',
        'data/l10n_be_281_mapping_data.xml',
        'data/ir_cron_data.xml',
        'data/res_country_data.xml',
        'data/res.city.csv',
        'views/l10n_be_joint_committee_views.xml',
        'data/l10n.be.reorganisation.measure.csv',
        'data/l10n.be.employer.category.csv',
        'data/l10n_be.salary.scale.csv',
        'views/l10n_be_individual_account_views.xml',
        'views/l10n_be_281_XX_views.xml',
        'views/l10n_be_281_mapping_views.xml',
        'report/hr_individual_account_templates.xml',
        'report/hr_281_10_templates.xml',
        'report/hr_281_13_templates.xml',
        'report/hr_281_18_templates.xml',
        'report/hr_281_20_templates.xml',
        'report/hr_281_30_templates.xml',
        'report/hr_281_45_templates.xml',
        'report/l10n_be_hr_payroll_274_XX_sheet_template.xml',
        'report/l10n_be_hr_payroll_273S_pdf_template.xml',
        'report/l10n_be_hr_payroll_273_part_pdf_template.xml',
        'wizard/l10n_be_onss_rates_import_views.xml',
        'wizard/l10n_be_social_balance_sheet_views.xml',
        'report/l10n_be_social_balance_report_template.xml',
        'wizard/l10n_be_social_security_certificate_views.xml',
        'report/l10n_be_social_security_certificate_report_template.xml',
        'report/l10n_be_hr_payroll_employment_certificate_template.xml',
        'views/l10n_be_273_XX_views.xml',
        'views/l10n_be_274_XX_views.xml',
        'views/l10n_be_benefit_view_ids.xml',
        'wizard/l10n_be_eco_vouchers_wizard_views.xml',
        'wizard/l10n_be_hr_payroll_employee_lang_views.xml',
        'views/hr_payslip_run_views.xml',
        'views/res_city_view.xml',
        'views/res_country_view.xml',
        'wizard/hr_leave_allocation_generate_multi_wizard_views.xml',
        'data/hr_contract_salary_benefit_data.xml',
        'views/l10n_be_salary_scale_views.xml',
        'views/hr_payroll_employee_declaration_views.xml',
        'views/hr_payslip_line_views.xml',
        'views/hr_payroll_structure_views.xml',
        'views/hr_salary_rule_category_views.xml',
        'views/hr_contract_salary_benefit_views.xml',
        'wizard/hr_payroll_salary_increase_wizard_views.xml',
        'security/ir.access.csv',
        'views/l10n_be_drs_views.xml',
        'views/l10n_be_drs_risk_views.xml',
    ],
    'demo': [
        'data/l10n_be_hr_payroll_demo.xml'
    ],
    'assets': {
        "im_livechat.assets_embed_core": [
            "l10n_be_hr_payroll/static/src/core/common/**/*",
        ],
        "mail.assets_public": [
            "l10n_be_hr_payroll/static/src/core/common/**/*",
        ],
        "portal.assets_chatter_helpers": [
            "l10n_be_hr_payroll/static/src/core/common/**/*",
        ],
        'web.assets_backend': [
            'l10n_be_hr_payroll/static/src/**/*',
        ],
        'web.report_assets_common': [
            'l10n_be_hr_payroll/static/src/scss/*.scss',
        ]
    },
    'post_init_hook': '_l10n_be_hr_payroll_post_install',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
