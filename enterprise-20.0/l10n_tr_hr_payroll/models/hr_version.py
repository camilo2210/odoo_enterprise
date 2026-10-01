from odoo import fields, models


L10N_TR_SOCIAL_SECURITY_LAW_SELECTION = [
    ("00687", "Decree Law No. 00687"),
    ("01687", "Law No. 01687"),
    ("02828", "Social Services Law No. 02828"),
    ("03294", "Employment of Social Assistance Recipients No. 03294"),
    ("05510", "Law No. 05510 – Vocational School Incentive 5%"),
    ("05746", "R&D Law No. 05746"),
    ("06111", "Law No. 06111"),
    ("06486", "Workers Sent Abroad No. 06486"),
    ("06645", "On-the-Job Training No. 06645"),
    ("07252", "Law No. 07252 – Beneficiaries of Short-Time Work/Non-Working Support"),
    ("07316", "Sectors with Suspended Activities No. 07316"),
    ("14857", "100% Disabled Employment Incentive No. 14857"),
    ("15746", "R&D Law No. 15746"),
    ("15921", "Unemployment Benefit Recipients No. 15921"),
    ("16322", "Law No. 16322"),
    ("17103", "New Generation Manufacturing / IT No. 17103"),
    ("17256", "Reemployment Support No. 17256"),
    ("25225", "Cultural Investments Incentive No. 25225"),
    ("25510", "Additional M-2 No. 25510"),
    ("26322", "Law No. 26322"),
    ("27103", "New Generation – Other No. 27103"),
    ("27256", "Additional Employment Support No. 27256"),
    ("36322", "Project-Based Investment Incentive Certificate No. 36322"),
    ("37103", "One From You, One From Me No. 37103"),
    ("46486", "Additional 6-Point Discount No. 46486"),
    ("55225", "Cultural Investments Incentive No. 55225"),
    ("56486", "Additional 6-Point Discount No. 56486"),
    ("66486", "Additional 6-Point Discount No. 66486"),
    ("15510", "SGDP – Law No. 5510 Temporary Article 95"),
    ("25746", "R&D Incentive for State of Emergency Provinces No. 25746"),
    ("35746", "R&D Incentive for State of Emergency Provinces No. 35746"),
    ("0", "No Law Type"),
]

L10N_TR_DOCUMENT_TYPE_SELECTION = [
    ("01", "All Insurance Branches / Foreign Nationals"),
    ("02", "Social Security Support Premium Declaration"),
    ("03", "Law 2098 Including Unemployment"),
    ("04", "Underground Permanent"),
    ("05", "Grouped Underground"),
    ("06", "Grouped Aboveground"),
    ("07", "Apprentice / Intern Student"),
    ("08", "Handmade Carpet Weaving, Textile"),
    ("09", "Group"),
    ("10", "Non-agreement Foreign National"),
    ("11", "Partial Employment Student under Higher Education Board"),
    ("12", "Temporary Article 20 (Fund)"),
    ("13", "Monthly Insurance Premium Excluding Unemployment"),
    ("14", "Libya"),
    ("15", "Foreign National from Contracted Country"),
    ("16", "Law 1798 Excluding Unemployment"),
    ("17", "Receiving Disability Pension Under Law 2098"),
    ("18", "Receiving Duty Disability Pension"),
    ("19", "Work in Penal Institutions / Detention Houses"),
    ("20", "Working in Germany (Federal Republic)"),
    ("21", "Countries Without Signed Social Security Agreement"),
    ("22", "Mandatory Vocational High School Internship"),
    ("23", "Military Laws (War-related)"),
    ("24", "Military Laws + Additional Duties"),
    ("25", "4447 Law – Unemployed Training Trainee"),
    ("28", "4046 Article 21 – Job Loss Compensation"),
    ("29", "Subject to 60 Days of Active Service Bonus"),
    ("30", "Excluding Employment Insurance – 60 Days Active"),
    ("31", "Military Law – 60 Days Active"),
    ("32", "T.S.K.T. – 90 Days Active Service"),
    ("33", "Excluding Unemployment Insurance – 90 Days Active"),
    ("34", "Military Law – 90 Days Active"),
    ("35", "Worked Under T.S.K.T. for 180 Days"),
    ("36", "Excluding Employment Insurance – 180 Days"),
    ("37", "Military Law – 180 Days"),
    ("39", "Temporary Assignment – Swiss Agreement"),
    ("41", "Public Admin – Suspended Contract"),
    ("42", "Apprentice/Student – Not a Care Obligation"),
    ("43", "Intern – Not a Care Obligation"),
    ("44", "İŞKUR Course – Not a Care Obligation"),
    ("46", "İŞKUR Trainees"),
    ("47", "Part-time Work Allowance"),
    ("48", "Retired Working Underground"),
    ("49", "Complementary – With Care Obligation"),
    ("50", "Complementary – Without Care Obligation"),
    ("51", "Security Guards Annex-15"),
    ("52", "No Pension Granted – 670 KHK"),
    ("53", "No Pension Granted – 60 Days Active"),
    ("54", "No Pension Granted – 90 Days Active"),
    ("55", "No Pension Granted – 180 Days Active"),
    ("56", "Temporary Article 20 – Excl. Unemployment"),
    ("57", "Temporary Article 20 – Excl. Unemployment (Retired)"),
    ("90", "Honorary Service – Subject to Insurance"),
    ("91", "60 Days Active – Subject to Risk & Service"),
    ("92", "90 Days Active – Subject to Risk & Service"),
]


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_tr_is_net_to_gross = fields.Boolean(
        string='Net to Gross',
        help='If checked, the gross salary will be calculated based on the net salary.',
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_tr_is_rd_incentive = fields.Boolean(
        string='Qualifies for R&D/Design Center Incentives',
        help=(
            "If checked, employee receives tax relief (income tax + stamp duty) on qualifying wages up to 40x gross "
            "minimum wage. Relief rate depends on the employee's certificate level."
        ),
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_tr_food_allowance = fields.Monetary(
        string="Food Allowances", groups="hr_payroll.group_hr_payroll_user", tracking=1,
    )
    l10n_tr_graduation_year = fields.Char(
        string='Graduation Year',
        groups='hr_payroll.group_hr_payroll_user',
        size=4,
    )
    l10n_tr_is_ex_convict = fields.Boolean(
        string='Is ex-convict',
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_tr_insurance_type = fields.Selection(
        string='Insurance Type',
        selection='_get_l10n_tr_insurance_type_selection',
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_tr_job_code = fields.Selection(
        string='Job Code',
        selection='_get_l10n_tr_job_code_selection',
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_tr_labour_sector = fields.Selection(
        string='Labour Sector',
        selection='_get_l10n_tr_labour_sector_selection',
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_tr_occupational_code = fields.Selection(
        string='Occupational Code',
        selection='_get_l10n_tr_occupational_code_selection',
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_tr_social_security_law = fields.Selection(
        string='Social Security Law',
        help="Choose the specific SGK law number that applies to the employee's coverage status.",
        selection=L10N_TR_SOCIAL_SECURITY_LAW_SELECTION,
        default="05510",
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_tr_document_type = fields.Selection(
        string="Social Security Document Type",
        help="Select the employee's coverage category according to SGK definitions.",
        selection=L10N_TR_DOCUMENT_TYPE_SELECTION,
        default="01",
        groups='hr_payroll.group_hr_payroll_user',
    )

    def _get_l10n_tr_insurance_type_selection(self):
        return [
            ('0', self.env._('Compulsory Insured')),
            ('7', self.env._('Apprentices')),
            ('8', self.env._('Social Security Support Premium')),
            ('12', self.env._('Foreign National Without International Agreement Insured')),
            ('14', self.env._('Prison Employee')),
            ('16', self.env._('İŞKUR Trainees')),
            ('17', self.env._('Those Receiving Unemployment Compensation')),
            ('18', self.env._('YÖK Partial Employment')),
            ('19', self.env._('Intern Students')),
            ('24', self.env._('Intern Student')),
            ('25', self.env._('Receiving Monthly Pension Under War and Duty Disability Laws 2330 and 3713')),
            ('32', self.env._('Scholarship Holder')),
            ('33', self.env._('Security Guard')),
            ('34', self.env._('Compulsory Insured Under Temporary 20')),
            ('35', self.env._('Social Security Support Premium Under Temporary 20')),
            ('37', self.env._('Students Receiving Complementary or Field Training')),
        ]

    def _get_l10n_tr_job_code_selection(self):
        return [
            ('1', self.env._('Employer or Representative')),
            ('2', self.env._('Employer')),
            ('3', self.env._('Employees covered under Law 657 Article 4/b')),
            ('4', self.env._('Employees covered under Law 657 Article 4/c')),
            ('5', self.env._('Apprentices and Intern Students')),
            ('6', self.env._('Others')),
        ]

    def _get_l10n_tr_labour_sector_selection(self):
        return [
            ('1', self.env._('Hunting, Fishing, Agriculture & Forestry')),
            ('2', self.env._('Food Industry')),
            ('3', self.env._('Mining & Quarrying')),
            ('4', self.env._('Petroleum, Chemicals, Rubber, Plastics & Pharmaceuticals')),
            ('5', self.env._('Textiles, Ready‑Made Clothing & Leather')),
            ('6', self.env._('Wood & Paper')),
            ('7', self.env._('Telecommunications / Communications')),
            ('8', self.env._('Press, Publishing & Journalism')),
            ('9', self.env._('Banking, Finance & Insurance')),
            ('10', self.env._('Trade, Office Work, Education & Fine Arts')),
            ('11', self.env._('Cement, Clay & Glass')),
            ('12', self.env._('Metal Industry')),
            ('13', self.env._('Construction')),
            ('14', self.env._('Energy')),
            ('15', self.env._('Transportation')),
            ('16', self.env._('Shipbuilding, Marine Transport, Warehousing & Freight Handling')),
            ('17', self.env._('Health & Social Services')),
            ('18', self.env._('Accommodation & Entertainment')),
            ('19', self.env._('Defense & Security')),
            ('20', self.env._('General Services')),
        ]

    def _get_l10n_tr_occupational_code_selection(self):
        return [
            ('4110.05', self.env._('Subscriber Affairs Officer')),
            ('2320.95', self.env._('Emergency Health Services Instructor')),
            ('2221.27', self.env._('Emergency Room Nurse')),
            ('3258.02', self.env._('Emergency Medical Technician')),
            ('2212.10', self.env._('Emergency Medicine Specialist')),
            ('6223.01', self.env._('Offshore Fisherman')),
            ('9333.13', self.env._('Open-Air Warehouse Attendant')),
            ('8121.02', self.env._('Open Hearth Smelter (Martin) – Steel')),
            ('7223.01', self.env._('Buffing and Polishing Machine Operator – Metalworking')),
            ('3411.03', self.env._('Justice Vocational Staff Member')),
            ('2320.96', self.env._('Justice Teacher')),
            ('3119.32', self.env._('Forensic Technician / Autopsy Assistant')),
            ('2212.50', self.env._('Forensic Medicine Specialist')),
            ('5419.02', self.env._('Disaster Response Personnel')),
            ('8121.48', self.env._('Refining Operator')),
            ('9510.03', self.env._('Poster Hanger')),
            ('3154.04', self.env._('FTN Officer')),
            ('2132.01', self.env._('Agronomist (Agricultural Scientist)')),
            ('8151.45', self.env._('Net Twisting Machine Worker')),
            ('8152.17', self.env._('Net Weaver – Automatic Loom')),
            ('8154.50', self.env._('Net Stretching Machine Worker')),
            ('3513.05', self.env._('Network Operator (Information Technology)')),
            ('3513.01', self.env._('Network Technologies Staff')),
            ('2523.01', self.env._('Network Technologies Specialist')),
            ('8172.01', self.env._('Wood Cutting Machine Operator (Sawyer-Lumberjack)')),
            ('6112.01', self.env._('Tree Tapper (Excluding Rubber)')),
            ('7521.01', self.env._('Timber Assessor')),
            ('7521.05', self.env._('Wood Impregnation Worker')),
            ('7115.04', self.env._('Wooden Shipbuilding Worker')),
            ('7521.02', self.env._('Wood Treatment Worker (Wood Processing)')),
            ('7523.02', self.env._('Woodworking Machine Setup Operator')),
            ('7523.03', self.env._('Woodworking Machine Setter')),
            ('2141.05', self.env._('Forest Products Industrial Engineer')),
            ('2320.01', self.env._('Woodworking Teacher – Secondary Education')),
            ('3143.02', self.env._('Woodworking Technician')),
            ('3143.03', self.env._('Woodworking Technologist')),
            ('7115.05', self.env._('Wooden Boat Builder')),
            ('6210.01', self.env._('Tree Cutting and Logging Operator')),
            ('7521.06', self.env._('Wood Drying Worker')),
            ('7522.17', self.env._('Wood Carver / Wood Carving Worker')),
            ('7522.39', self.env._('Wood Pallet Manufacturer')),
            ('6210.02', self.env._('Timber Estimator and Marker (Marker)')),
            ('7523.22', self.env._('Wood Turner')),
            ('8154.03', self.env._('Bleaching and Cooking Machine Operator (Kasar)')),
            ('5142.13', self.env._('Waxing Specialist')),
            ('7318.22', self.env._('Net Weaver (Handmade)')),
            ('8332.09', self.env._('Heavy Truck Driver')),
            ('8211.16', self.env._('Heavy Weapons Maintenance and Repair Technician')),
            ('3115.50', self.env._('Heavy Vehicle Test Controller')),
            ('2261.01', self.env._('Oral Diseases Specialist (Stomatologist)')),
            ('2261.02', self.env._('Oral Pathologist')),
            ('3251.04', self.env._('Oral and Dental Health Technician')),
            ('3251.05', self.env._('Oral and Dental Health Technologist')),
            ('2261.03', self.env._('Oral, Dental and Maxillofacial Surgeon')),
            ('2310.01', self.env._('Faculty Member in Oral, Dental and Maxillofacial Diseases and Surgery')),
            ('9213.01', self.env._('Stableman (Animal Caretaker and Stable Cleaner) – Mixed Farming (Crop Production and Livestock Breeding)')),
        ]
