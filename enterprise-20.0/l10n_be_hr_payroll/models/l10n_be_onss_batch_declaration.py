# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io
from datetime import date

import requests
from dateutil.relativedelta import relativedelta
from lxml import etree

from odoo import _, api, fields, models, modules
from odoo.exceptions import UserError, ValidationError
from odoo.tools import BinaryBytes, config, frozendict

from odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_file import ENVIRONMENTS


class L10nBeONSSBatchDeclaration(models.AbstractModel):
    _name = 'l10n.be.onss.batch.declaration'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'ONSS Batch Declaration'

    _ONSS_TO_STATE = frozendict({
        'posted': 'pending',
        'received': 'done',
        'notified': 'in_progress',
        'error': 'refused',
        'other': 'in_progress',
    })

    @api.model
    def default_get(self, fields):
        if "BE" not in self.env.companies.country_id.mapped('code'):
            raise UserError(_('You must be logged in a Belgian company to use this feature'))
        return super().default_get(fields)

    name = fields.Char(string="Reference")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

    environment = fields.Selection(selection=ENVIRONMENTS, default='R', required=True)
    onss_declaration_ids = fields.One2many('l10n.be.onss.declaration', string="ONSS Declarations", compute='_compute_onss_declaration_ids', search='_search_onss_declaration_ids')

    error_message = fields.Char(store=True, compute='_compute_error_message', string="Error Message")

    xml_file = fields.Binary(string="XML file")
    xml_raw_content = fields.Text(readonly=True)
    xml_filename = fields.Char()
    signature_file = fields.Binary(string="Signature file")
    signature_filename = fields.Char()
    go_file = fields.Binary(string="Go file")
    go_filename = fields.Char()

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('ready', 'Ready'),
            ('done', 'Done'),
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('refused', 'Refused'),
            ('error', 'Error'),
        ],
        required=True,
        store=True,
        default='draft',
        compute='_compute_state',
    )

    def _fetch_validation_schema(self):
        self.ensure_one()
        # We fetch the schema labeled with the previous quarter. I.E -> in May 2026 we use Q1 2026's schema.
        base_schema_filename = self._get_base_schema_filename()

        target_date = date.today() - relativedelta(months=3)
        target_quarter = (target_date.month - 1) // 3 + 1
        current_year_quarter = '%s%s' % (target_date.year, target_quarter)
        schema_filename = base_schema_filename + current_year_quarter

        attachment = self.env['ir.attachment'].search([
            ('name', '=', schema_filename),
            ('res_model', '=', self._name),
        ], limit=1)
        if attachment:
            xsd_root = etree.parse(io.BytesIO(attachment.raw))
            return xsd_root

        base_url = self._get_base_schema_url()
        schema_url = base_url + schema_filename + '.xsd'
        try:
            response = requests.get(schema_url, timeout=30)
            response.raise_for_status()
            schema_xsd_root = etree.parse(io.BytesIO(response.content))
            self.env['ir.attachment'].create({
                'name': schema_filename,
                'type': 'binary',
                'raw': response.content,
                'res_model': self._name,
                'description': f'Cached {self._name} {self._get_declaration_type()} XSD schema',
            })
        except Exception as e:  # noqa: BLE001
            raise UserError(_(
                'Failed to fetch validation schema of %(type)s report for quarter %(year_quarter)s: \n%(error)s', type=self._get_declaration_type(), year_quarter=current_year_quarter, error=e))

        return schema_xsd_root

    @api.depends('xml_file')
    def _compute_error_message(self):
        for declaration in self:
            declaration.error_message = False
            if not declaration.xml_file or config['test_enable'] or modules.module.current_test:
                continue
            xsd_root = declaration._fetch_validation_schema()
            schema = etree.XMLSchema(xsd_root)
            try:
                xml_root = etree.fromstring(declaration.xml_file.content)
                schema.assertValid(xml_root)
            except (etree.DocumentInvalid, etree.XMLSyntaxError) as err:
                declaration.error_message = self.env._("Error upon generating the declaration: %s", str(err))

    @api.depends('xml_file', 'error_message', 'onss_declaration_ids.state')
    def _compute_state(self):
        grouped_declarations = dict(self.env['l10n.be.onss.declaration']._read_group(
            domain=[('batch_declaration_id', 'in', [f'{r._name},{r.id}' for r in self])],
            groupby=['batch_declaration_id'],
            aggregates=['id:max'],
        ))
        onss_declarations = self.env['l10n.be.onss.declaration'].browse(grouped_declarations.values())
        latest_declaration_state_by_id = {
            int(ref.split(',')[1]): onss_declarations.browse(latest_id).state
            for ref, latest_id in grouped_declarations.items()
        }
        for record in self:
            if not record.xml_file:
                record.state = 'draft'
                continue
            if record.error_message:
                record.state = 'error'
                continue
            declaration_state = latest_declaration_state_by_id.get(record.id)
            record.state = self._ONSS_TO_STATE.get(declaration_state, 'ready')

    def _get_common_filename(self):
        # https://www.socialsecurity.be/site_fr/general/helpcentre/batch/files/directives.htm
        # filename format: {prefix}.{type}.{expeditor}.{date}.{num_suite}.{env}.{file_number}[.{number_of_total_files}]
        self.ensure_one()
        date_str = fields.Date.context_today(self).strftime('%Y%m%d')
        if not (onss_expeditor_number := self.company_id.onss_expeditor_number):
            raise UserError(self.env._('There is no defined expeditor number for the company.'))
        expeditor = (
            onss_expeditor_number.split('_')[3]
            if onss_expeditor_number.startswith('self_service_chaman_')
            else onss_expeditor_number
        )

        declaration_type = self._get_declaration_type()

        [(max_file_seq,)] = self.env['l10n.be.onss.file']._read_group(
            domain=[
                ('declaration_type', '=', declaration_type),
                ('expeditor_number', '=', expeditor),
                ('creation_date', '=', fields.Date.context_today(self)),
            ],
            aggregates=['file_sequence:max'],
        )
        max_seq = int(max_file_seq) if max_file_seq else 0

        filename_pattern = f'%.{declaration_type}.{expeditor}.{date_str}.%.%.%'
        for rec in self.env[self._name].search_read(
            [('xml_filename', 'like', filename_pattern), ('id', '!=', self.id)],
            ['xml_filename'],
        ):
            if len(parts := rec['xml_filename'].split('.')) >= 6:
                max_seq = max(max_seq, int(parts[4]))

        num_seq = str(max_seq + 1).zfill(5)

        return f'.{declaration_type}.{expeditor}.{date_str}.{num_seq}.{self.environment}.1'

    def generate_declaration_xml_report(self):
        self.ensure_one()
        filename_common = self._get_common_filename()
        certificate_sudo = self.company_id.sudo().onss_certificate_id
        if not certificate_sudo and self.environment != 'S' and not self.env.context.get('onss_skip_signature'):
            return {
                'type': 'ir.actions.client',
                'tag': 'l10n_be_hr_payroll.batch_declaration_certificate_warning',
            }

        # Declaration File
        # ================
        template_xmlid = self._get_declaration_template_xmlid()
        xml_str = self.env['ir.qweb']._render(template_xmlid, self._get_rendering_data())

        # Prettify xml string
        root = etree.fromstring(xml_str, parser=etree.XMLParser(remove_blank_text=True))
        xml_formatted_str = etree.tostring(root, pretty_print=True, encoding='UTF-8', xml_declaration=True)
        # Yep, shame.
        xml_formatted_str = xml_formatted_str.replace(b'\n', b'\r\n')
        self.xml_raw_content = xml_formatted_str
        self.xml_file = BinaryBytes(xml_formatted_str)
        self.xml_filename = 'FI' + filename_common + '.1'

        # Signature File
        # ==============
        self.signature_file = None
        self.signature_filename = None
        if not self.env.context.get('onss_skip_signature') and self.environment != 'S':
            certificate_sudo = self.company_id.sudo().onss_certificate_id
            if not certificate_sudo:
                raise UserError(_('No Certificate defined on the Payroll Configuration'))

            sign = certificate_sudo._decode_certificate_for_be_onss_xml(xml_formatted_str)
            self.signature_file = BinaryBytes(sign)
            self.signature_filename = 'FS' + filename_common + '.1'

        self.go_file = BinaryBytes(b'go')
        self.go_filename = 'GO' + filename_common
        return None

    def _compute_onss_declaration_ids(self):
        groups = self.env['l10n.be.onss.declaration']._read_group(
            domain=[('batch_declaration_id', 'in', [f'{r._name},{r.id}' for r in self])],
            groupby=['batch_declaration_id'],
            aggregates=['id:recordset'],
        )
        declarations_by_ref = dict(groups)
        for batch_declaration in self:
            batch_declaration.onss_declaration_ids = declarations_by_ref.get(
                f'{batch_declaration._name},{batch_declaration.id}',
                self.env['l10n.be.onss.declaration'],
            )

    def _search_onss_declaration_ids(self, operator, value):
        declarations = self.env['l10n.be.onss.declaration'].search([
            ('batch_declaration_id', 'like', f'{self._name},%'),
            ('id', operator, value),
        ])
        return [('id', 'in', [d.batch_declaration_id.id for d in declarations])]

    def _get_declaration_type(self):
        raise NotImplementedError

    def _get_base_schema_url(self):
        raise NotImplementedError

    def _get_base_schema_filename(self):
        raise NotImplementedError

    def _get_declaration_template_xmlid(self):
        raise NotImplementedError

    def _get_rendering_data(self):
        raise NotImplementedError

    def action_open_onss_declaration(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('l10n_be_hr_payroll.action_l10n_be_onss_declaration')
        reference_id = f'{self._name},{self.id}'
        action.update({
            'domain': [('batch_declaration_id', '=', reference_id)],
            'context': {'default_batch_declaration_id': reference_id},
        })
        return action

    def create_onss_declaration(self):
        FILE_FIELDS = ["xml", "signature", "go"]
        onss_declaration_vals = []
        for batch_declaration in self:
            available_files = [file for file in FILE_FIELDS if batch_declaration[f"{file}_file"]]
            if not available_files:
                raise UserError(self.env._("No files available to post. Please generate the XML report first."))
            onss_declaration_vals.append({
                'batch_declaration_id': f'{batch_declaration._name},{batch_declaration.id}',
                'environment': batch_declaration.environment,
                'onss_file_ids': [
                    (0, 0, {
                        'name': batch_declaration[f"{file}_filename"],
                        'file': batch_declaration[f"{file}_file"],
                    }) for file in available_files
                ]
            })
        return self.env['l10n.be.onss.declaration'].create(onss_declaration_vals)

    def action_download_declaration_file(self):
        self.ensure_one()
        if not self.xml_file:
            raise UserError(self.env._("No file available to download. Please generate the XML report first."))
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/xml_file/{self.xml_filename}?download=true',
            'target': 'self',
        }

    def action_post_onss_declaration(self):
        onss_declaration = self.create_onss_declaration()
        onss_declaration.action_post()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': self.env._("Declaration posted successfully to ONSS"),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }

    def _pre_submit_checks(self):
        self.ensure_one()
        errors = []
        if not self.xml_file or not self.xml_filename:
            errors.append(self.env._("The XML file is missing. Please generate the declaration first."))
        if self.environment != 'S' and not self.env.context.get('onss_skip_signature') and (not self.signature_file or not self.signature_filename):
            errors.append(self.env._("The signature file is missing. Please generate the declaration first."))
        if not self.go_file or not self.go_filename:
            errors.append(self.env._("The GO file is missing. Please generate the declaration first."))
        if not self.company_id.onss_expeditor_number:
            errors.append(self.env._("There is no defined expeditor number for the company."))
        return errors

    def action_submit_declaration(self):
        self.ensure_one()
        self.generate_declaration_xml_report()
        onss_declaration = self.create_onss_declaration()
        return onss_declaration.action_post()

    def action_mark_done(self):
        self.ensure_one()
        if not self.name:
            raise ValidationError(_("Please provide the reference to mark the report as done"))
        self.state = 'done'

    def action_reset_to_draft(self):
        self.ensure_one()
        self.state = 'draft'
        self.xml_file = None
        self.signature_file = None
        self.go_file = None
