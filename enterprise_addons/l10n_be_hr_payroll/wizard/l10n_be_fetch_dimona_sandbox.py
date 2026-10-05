# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class L10nBeFetchDimonaSandbox(models.TransientModel):
    _name = 'l10n.be.fetch.dimona.sandbox'
    _description = 'Fetch Dimona Declarations from Sandbox'

    company_id = fields.Many2one('res.company', required=True)
    bulk_declarations_json = fields.Text('Bulk Declarations JSON with Periods and Relations', required=True)

    @api.model
    def action_open_json_wizard(self):
        company = self.env.company
        if company.l10n_be_dimona_environment != 'sandbox':
            raise UserError(self.env._('This feature is only available in sandbox mode. Please switch to a sandbox company to use this wizard.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Declaration from JSON'),
            'res_model': 'l10n.be.fetch.dimona.sandbox',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def default_get(self, fields):
        if self.env.company.l10n_be_dimona_environment != 'sandbox':
            raise UserError(self.env._('This feature is only available in sandbox mode. Please switch to a sandbox company.'))

        res = super().default_get(fields)
        company = self.env.company

        if 'bulk_declarations_json' in fields:
            demo_json = {
                "relations": [
                    {
                        "name": "87062315653",
                        "company_id": company.id,
                        "content": {
                            "startDate": "2023-01-01",
                            "endDate": "2023-01-31",
                            "worker": {
                                "ssin": "87062315653",
                                "firstName": "John",
                                "lastName": "Doe"
                            }
                        }
                    }
                ],
                "periods": [
                    {
                        "name": "2029409422",
                        "company_id": company.id,
                        "worker_ssin": "87062315653",
                        "content": {
                            "startDate": "2025-09-26",
                            "endDate": "2025-10-25",
                            "periodId": "2029409422",
                            "worker": {
                                "ssin": "87062315653",
                                "firstName": "John",
                                "lastName": "Doe"
                            }
                        }
                    }
                ],
                "declarations": [
                    {
                        "worker": {
                            "ssin": "87062315653",
                            "gender": "1",
                            "birthDate": "1991-11-11",
                            "givenName": "TEST",
                            "familyName": "EMPLOYEE",
                            "givenNames": "TEST EMPLOYEE",
                            "nationality": 150
                        },
                        "dimonaIn": {
                            "features": {
                                "workerType": "OTH",
                                "jointCommissionNumber": "100"
                            },
                            "startDate": "2025-09-26"
                        },
                        "employer": {
                            "employerId": 12548245,
                            "enterpriseNumber": "477472701"
                        },
                        "declarationStatus": {
                            "period": {
                                "id": 2029409422,
                            },
                            "result": "A",
                            "declarationId": 2029409422
                        }
                    },
                    {
                        "worker": {
                            "ssin": "87062315653",
                            "gender": "1",
                            "birthDate": "1991-11-11",
                            "givenName": "TEST",
                            "familyName": "EMPLOYEE",
                            "givenNames": "TEST EMPLOYEE",
                            "nationality": 150
                        },
                        "employer": {
                            "employerId": 125482497,
                            "enterpriseNumber": "477472701"
                        },
                        "dimonaUpdate": {
                            "periodId": 2029409422,
                            "startDate": "2025-09-26"
                        },
                        "declarationStatus": {
                            "period": {
                                "id": 2029409422,
                            },
                            "result": "B",
                            "declarationId": 656309296521
                        }
                    },
                    {
                        "worker": {
                            "ssin": "87062315653",
                            "gender": "1",
                            "birthDate": "1991-11-11",
                            "givenName": "TEST",
                            "familyName": "EMPLOYEE",
                            "givenNames": "TEST EMPLOYEE",
                            "nationality": 150
                        },
                        "employer": {
                            "employerId": 125482497,
                            "enterpriseNumber": "477472701"
                        },
                        "dimonaOut": {
                            "endDate": "2025-09-26",
                            "periodId": 2029409422
                        },
                        "declarationStatus": {
                            "period": {
                                "id": 2029409422,
                            },
                            "result": "A",
                            "declarationId": 656309314911
                        }
                    }
                ]
            }
            res['bulk_declarations_json'] = json.dumps(demo_json, indent=2)

        if 'company_id' in fields and not res.get('company_id'):
            res['company_id'] = company.id

        return res

    def action_create_declaration(self):
        self.ensure_one()
        if self.env.company.l10n_be_dimona_environment != 'sandbox':
            raise UserError(self.env._('This feature is only available in sandbox mode. Please switch to a sandbox company.'))

        try:
            content = json.loads(self.bulk_declarations_json)
        except json.JSONDecodeError as e:
            raise ValidationError(self.env._('Invalid JSON format: %s', str(e)))

        if not isinstance(content, dict):
            raise ValidationError(self.env._('JSON must be an object/dictionary'))

        created_relations = {}
        for relation_data in content.get('relations', []):
            relation = self.env['l10n.be.dimona.relation'].search([
                ('name', '=', relation_data.get('name')),
                ('company_id', '=', self.company_id.id)
            ])
            if not relation:
                relation = self.env['l10n.be.dimona.relation'].create({
                    'name': relation_data.get('name'),
                    'company_id': self.company_id.id,
                    'content': relation_data.get('content', {}),
                })
            created_relations[relation_data.get('name')] = relation

        created_periods = {}
        for period_data in content.get('periods', []):
            worker_ssin = period_data.get('worker_ssin')
            relation_id = created_relations.get(worker_ssin)

            period = self.env['l10n.be.dimona.period'].search([
                ('name', '=', period_data.get('name')),
                ('company_id', '=', self.company_id.id)
            ])
            if not period and relation_id:
                period = self.env['l10n.be.dimona.period'].create({
                    'name': period_data.get('name'),
                    'company_id': self.company_id.id,
                    'relation_id': relation_id.id,
                    'content': period_data.get('content', {}),
                })
            created_periods[period_data.get('name')] = period

        created_declarations = []
        for declaration_data in content.get('declarations', []):
            declaration_id = self._generate_declaration_id(declaration_data)
            declaration = self.env['l10n.be.dimona.declaration'].create({
                'name': declaration_id,
                'company_id': self.company_id.id,
                'content': declaration_data,
            })
            created_declarations.append(declaration)

        if created_declarations:
            return {
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'l10n.be.dimona.declaration',
                'res_id': created_declarations[0].id,
                'target': 'current',
            }
        raise ValidationError(self.env._('No declarations found in JSON content.'))

    def _generate_declaration_id(self, content):
        period_id = content.get('declarationStatus', {}).get('period', {}).get('id', None)

        if not period_id:
            raise ValidationError(self.env._('Period ID is missing from declaration content.'))

        base_id = str(period_id)
        existing = self.env['l10n.be.dimona.declaration'].search([
            ('name', '=', base_id),
            ('company_id', '=', self.company_id.id)
        ])

        counter = 1
        unique_id = base_id
        while existing:
            unique_id = f"{base_id}{counter}"
            existing = self.env['l10n.be.dimona.declaration'].search([
                ('name', '=', unique_id),
                ('company_id', '=', self.company_id.id)
            ])
            counter += 1

        return unique_id

    def action_open_fetch_dimona_sandbox(self):
        return self.env.ref('test_l10n_be_hr_payroll_account.l10n_be_fetch_dimona_sandbox_action').read()[0]
