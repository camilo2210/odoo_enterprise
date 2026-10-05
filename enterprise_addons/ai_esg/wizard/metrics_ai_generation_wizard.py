import json

from odoo import api, fields, models, Command
from odoo.addons.ai.utils.ai_utils import get_text_from_parts


class MetricsAiGenerationWizard(models.TransientModel):
    _name = 'metrics.ai.generation.wizard'
    _description = 'AI generation of suggestions of ESG Metrics based on Company Data'

    company_id = fields.Many2one(
        'res.company',
        'Group Reporting Company',
        default=lambda self: self.env['res.company'].sudo().ESG_REPORT_DEFAULT_COMPANY or self.env.company,
        help='This company defines the fiscal year and main company information used for the Group CSRD report. Information entered in the CSRD creation wizard will be saved under this company. If your group has several companies, choose the one representing the consolidated perimeter.',
        required=True,
    )
    attachment_id = fields.Many2one('ir.attachment')
    nace_id = fields.Many2one(
        'esg.nace',
        required=True,
        compute='_compute_nace_id',
        store=True,
        readonly=False,
    )
    company_size = fields.Selection(
        selection=[
            ('small', '< 250 employees'),
            ('medium', '250 - 1000 employees'),
            ('large', '> 1000 employees'),
        ],
        compute='_compute_company_size',
        store=True,
        readonly=False,
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
    )
    revenues_value = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_revenues_value',
        store=True,
        readonly=False,
        help='Your company\'s total annual turnover (net revenue), in your reporting currency',
    )
    assets_value = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_assets_value',
        store=True,
        readonly=False,
        help='Your company\'s total balance sheet assets (total assets, not just the fixed ones), as of your last financial year-end, in your reporting currency',
    )
    core_business_description = fields.Html(
        compute='_compute_core_business_description',
        store=True,
        readonly=False,
    )

    @api.depends('company_id')
    def _compute_nace_id(self):
        for wizard in self:
            wizard.nace_id = wizard.company_id.esg_nace_id

    @api.depends('company_id')
    def _compute_company_size(self):
        for wizard in self:
            wizard.company_size = wizard.company_id.esg_company_size

    @api.depends('company_id')
    def _compute_revenues_value(self):
        for wizard in self:
            wizard.revenues_value = wizard.company_id.esg_revenues_value

    @api.depends('company_id')
    def _compute_assets_value(self):
        for wizard in self:
            wizard.assets_value = wizard.company_id.esg_assets_value

    @api.depends('company_id')
    def _compute_core_business_description(self):
        for wizard in self:
            wizard.core_business_description = wizard.company_id.esg_core_business_description

    def _get_company_data(self):
        self.ensure_one()
        # Get key suppliers and customers
        top_suppliers = [
            partner for partner, _ in self.env['account.move'].sudo()._read_group(
                domain=[
                    ('state', '=', 'posted'),
                    ('move_type', 'in', self.env['account.move'].get_purchase_types(include_receipts=True)),
                ],
                groupby=['partner_id'],
                aggregates=['__count'],
                order='__count desc',
                limit=5,
            )
        ]
        top_customers = [
            partner for partner, _ in self.env['account.move'].sudo()._read_group(
                domain=[
                    ('state', '=', 'posted'),
                    ('move_type', 'in', self.env['account.move'].get_sale_types(include_receipts=True)),
                ],
                groupby=['partner_id'],
                aggregates=['__count'],
                order='__count desc',
                limit=5,
            )
        ]
        return {
            'Industry Sector': self.nace_id.display_name,
            'Company Size': dict(self._fields['company_size']._description_selection(self.env)).get(self.company_size, False),
            'Currency': self.currency_id.name,
            'Revenues': self.revenues_value,
            'Assets': self.assets_value,
            'Core Business Description': str(self.core_business_description),
            'Key Suppliers': [
                {
                    'name': supplier.complete_name,
                    'description': supplier.comment,
                    'country': supplier.country_id.name,
                    'website': supplier.website,
                }
                for supplier in top_suppliers
            ],
            'Key Customers': [
                {
                    'name': customer.complete_name,
                    'description': customer.comment,
                    'country': customer.country_id.name,
                    'website': customer.website,
                }
                for customer in top_customers
            ],
        }

    def action_generate_metrics(self):
        self.ensure_one()

        # Save the company information
        csrd_company = self.company_id
        if csrd_company.has_access('write'):
            csrd_company.write({
                'esg_nace_id': self.nace_id.id,
                'esg_company_size': self.company_size,
                'esg_revenues_value': self.revenues_value,
                'esg_assets_value': self.assets_value,
                'esg_core_business_description': self.core_business_description,
            })

        # Prompt to AI
        company_data = self._get_company_data()
        current_fiscal_dates = self.env['esg.metric']._get_default_dates()
        existing_metrics = self.env['esg.metric'].search(
            domain=[('date_start', '<=', current_fiscal_dates['date_to']), ('date_end', '>=', current_fiscal_dates['date_from'])],
            limit=100,
        )
        exisiting_metrics_data = [{
            'ESRS Code': metric.esrs_id.code,
            'ESRS Category': metric.category,
            'IRO Type': metric.type,
            'Justification': metric.notes or 'No detail provided',
        } for metric in existing_metrics]

        prompt = """
            Based on the company data I provide you here: %(company_data)s.
            And based on ESRS data points from the list (from EFRAG) I provide you in attachment as a CSV file.

            Determine which ESRS data points are relevant.

            Important instructions:
            1. Be **specific and contextual** — base your reasoning strictly on the company data (sector, size, operations, business model, geography, etc.).
            - Do NOT generate generic or vague statements such as “improving workforce policies increases productivity.”
            - Each IRO description must clearly relate to the company's concrete activities, technologies, or value chain.

            2. Only include the IRO categories (Positive Impact, Negative Impact, Risk, or Opportunity) **if they truly make sense** for the company in the context of the ESRS data point.
            - It is perfectly valid for a metric to only have one or two relevant IROs.
            - Do NOT force the presence of all four categories.

            3. Explore and diversify across all ESRS areas:
            Review the company's activities against each ESRS pillar (E1-E5, S1-S4, G1) and identify which data points could reasonably apply based on its sector, value chain, and operations.
            Aim for a balanced and diverse set of relevant ESRS datapoints across the three sustainability dimensions (Environmental, Social, Governance).
            Also aim for diversity in the types of IROs identified (Positive Impacts, Negative Impacts, Risks, Opportunities).
            Do not restrict the output to the same few datapoints in every generation. Each run should reassess all ESRS topics independently to identify new or previously overlooked ones.
            Avoid reusing identical IRO sentences from previous generations. Rephrase or adjust the focus when appropriate.

            4. If some ESRS data points have **already been reported** by the company for the current fiscal year (provided here: %(existing_metrics)s), you may:
            - Fill in the missing information, or
            - Suggest only new ones that are genuinely relevant and not redundant.

            5. The goal is to identify **all potentially material ESRS data points** for the company — across Environmental, Social, and Governance pillars — while keeping the reasoning realistic, specific, and limited to the company's scope.

            6. Use all the company data provided, including the core business description, the key suppliers and customers info (name, description, country, website) to make justifications in the description of the IROs.

            7. Pick at most 6 ESRS per generation.
        """ % {
                'company_data': company_data,
                'existing_metrics': str(exisiting_metrics_data) if existing_metrics else '[]',
            }

        self.attachment_id = self.env.ref('ai_esg.esg_esrs_efrag_list')
        _record_context, files_parts = self._get_ai_context(['attachment_id'])
        msg_parts = [{'type': 'text', 'text': prompt}]
        msg_parts.extend(files_parts)
        schema = {
            'type': 'object',
            'properties': {
                'items': {
                    'type': 'array',
                    'description': 'A list of ESRS data points and their corresponding Impacts, Risks, and Opportunities (IROs).',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'code': {
                                'type': 'string',
                                'description': 'The relevant ESRS data point ID from the ID column (e.g. "E1-5", "S1-14").'
                            },
                            'name': {
                                'type': 'string',
                                'description': 'A summary topic of 5-8 words max (e.g., "Carbon footprint from logistics", "Employee well-being programs").'
                            },
                            'iros': {
                                'type': 'object',
                                'description': 'The IROs (Impacts, Risks, and Opportunities) that match according to the company data and the ESRS data points.',
                                'properties': {
                                    'positive_impacts': {
                                        'type': 'array',
                                        'items': {'type': 'string'},
                                        'description': 'A small description of identified positive impacts.'
                                    },
                                    'negative_impacts': {
                                        'type': 'array',
                                        'items': {'type': 'string'},
                                        'description': 'A small description of identified negative impacts.'
                                    },
                                    'risks': {
                                        'type': 'array',
                                        'items': {'type': 'string'},
                                        'description': 'A small description of identified risks.'
                                    },
                                    'opportunities': {
                                        'type': 'array',
                                        'items': {'type': 'string'},
                                        'description': 'A small description of identified opportunities.'
                                    }
                                },
                                'required': ['positive_impacts', 'negative_impacts', 'risks', 'opportunities'],
                                'additionalProperties': False
                            }
                        },
                        'required': ['code', 'name', 'iros'],
                        'additionalProperties': False
                    }
                }
            },
            'required': ['items'],
            'additionalProperties': False
        }
        try:
            response = self.env['ai.session']._get_direct_response(
                instructions="Execute the user request exactly as described",
                message=msg_parts,
                schema=schema,
                usage="esg_metrics",
            )
        except Exception:  # noqa: BLE001
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': self.env._('Oops, it looks like our AI is unreachable.'),
                    'type': 'warning',
                }
            }
        result = response and json.loads(get_text_from_parts(response))
        if not result:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': self.env._('No additional relevant sustainability metrics found.\n\nUpdate your company data or material topics to refine future suggestions.'),
                    'type': 'warning',
                }
            }

        esrs_data = []
        esrs_codes = set()
        for data in result.get('items', []):
            esrs_code = data['code']
            esrs_codes.add(esrs_code)
            vals = {'code': esrs_code, 'name': data.get('name', '')}
            if iros := data.get('iros'):
                if positive_impacts := iros.get('positive_impacts'):
                    esrs_data.extend([
                        {**vals, 'detail': positive_impact, 'type': 'positive_impact'}
                        for positive_impact in positive_impacts
                    ])
                if negative_impacts := iros.get('negative_impacts'):
                    esrs_data.extend([
                        {**vals, 'detail': negative_impact, 'type': 'negative_impact'}
                        for negative_impact in negative_impacts
                    ])
                if risks := iros.get('risks'):
                    esrs_data.extend([
                        {**vals, 'detail': risk, 'type': 'risk'}
                        for risk in risks
                    ])
                if opportunities := iros.get('opportunities'):
                    esrs_data.extend([
                        {**vals, 'detail': opportunity, 'type': 'opportunity'}
                        for opportunity in opportunities
                    ])
        esrs_records = self.env['esg.esrs'].search([('code', 'in', list(esrs_codes))])
        esrs_per_code = {esrs.code: esrs.id for esrs in esrs_records}
        esg_suggestion_vals_list = []
        for data in esrs_data:
            esrs_code = data.pop('code')
            if esrs_code in esrs_per_code:
                data['esrs_id'] = esrs_per_code[esrs_code]
                esg_suggestion_vals_list.append(data)
        metrics_ai_suggestion_wizard = self.env['metrics.ai.suggestion.wizard'].create({
            'suggestion_line_ids': [Command.create(esg_suggestion_vals) for esg_suggestion_vals in esg_suggestion_vals_list],
        })

        return {
            'name': self.env._('AI Suggested Metrics'),
            'type': 'ir.actions.act_window',
            'res_model': 'metrics.ai.suggestion.wizard',
            'view_mode': 'form',
            'target': 'new',
            'res_id': metrics_ai_suggestion_wizard.id,
            'context': {'dialog_size': 'extra-large'},
        }
