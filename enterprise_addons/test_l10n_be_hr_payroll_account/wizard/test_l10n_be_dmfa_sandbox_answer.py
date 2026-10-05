# Part of Odoo. See LICENSE file for full copyright and licensing details.

import random
import string

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_be_hr_payroll.models.utils import xml_str_to_dict

# Expeditor number used by the ONSS in the name of the files it sends back
ONSS_EXPEDITOR_NUMBER = '999999'

# Answer file name code by XML root tag, as analysed by
# l10n.be.onss.declaration._process_incoming_onss_files()
ANSWER_CODES = {
    'ACRF': 'ACRF',
    'NOTIFICATION': 'NOTI',
    'IDFLUX': 'IDFL',
    'DmfAConsultationAnswer': 'DMDB',
    'DmfAUpdateNotification': 'DMNO',
    'DmfAPID': 'DMPI',
}

SAMPLE_ACRF_ANSWER = """<?xml version="1.0" encoding="UTF-8"?>
<ACRF xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="ACRF_%(year_quarter)s.xsd">
    <Form>
        <Identification>ACRF001</Identification>
        <FormCreationDate>%(creation_date)s</FormCreationDate>
        <FormCreationHour>%(creation_hour)s</FormCreationHour>
        <AttestationStatus>0</AttestationStatus>
        <TypeForm>FA</TypeForm>
        <FileReference>
            <FileName>%(referenced_filename)s</FileName>
            <ReferenceOrigin>2</ReferenceOrigin>
            <ReferenceNbr>%(onss_reference)s</ReferenceNbr>
        </FileReference>
        <!-- To refuse the received files, set ResultCode to 0 and add one ErrorID
             per anomaly, e.g. <ErrorID>ACRF-125</ErrorID> (125: invalid signature) -->
        <ReceptionResult>
            <ResultCode>1</ResultCode>
        </ReceptionResult>
    </Form>
</ACRF>
"""

SAMPLE_NOTIFICATION_ANSWER = """<?xml version="1.0" encoding="UTF-8"?>
<NOTIFICATION xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="NOTIFICATION_%(year_quarter)s.xsd">
    <Form>
        <Identification>NOTI001</Identification>
        <FormCreationDate>%(creation_date)s</FormCreationDate>
        <FormCreationHour>%(creation_hour)s</FormCreationHour>
        <AttestationStatus>0</AttestationStatus>
        <TypeForm>FA</TypeForm>
        <FileReference>
            <FileName>%(referenced_filename)s</FileName>
            <ReferenceOrigin>2</ReferenceOrigin>
            <ReferenceNbr>%(onss_reference)s</ReferenceNbr>
        </FileReference>
        <HandledOriginalForm>
            <Identification>%(handled_identification)s</Identification>
            <FormCreationDate>%(original_creation_date)s</FormCreationDate>
            <FormCreationHour>%(original_creation_hour)s</FormCreationHour>
            <AttestationStatus>0</AttestationStatus>
            <TypeForm>SU</TypeForm>
        </HandledOriginalForm>
        <Reference>
            <ReferenceType>1</ReferenceType>
            <ReferenceOrigin>1</ReferenceOrigin>
            <ReferenceNbr>%(user_reference)s</ReferenceNbr>
        </Reference>
        <EmployerId>
            <NOSSRegistrationNbr>%(registration_number)s</NOSSRegistrationNbr>
            <CompanyID>%(company_number)s</CompanyID>
        </EmployerId>
        <ConcernedQuarter>
            <Quarter>%(year_quarter)s</Quarter>
        </ConcernedQuarter>
        <HandledReference>
            <ReferenceType>1</ReferenceType>
            <ReferenceOrigin>2</ReferenceOrigin>
            <ReferenceNbr>%(onss_reference)s</ReferenceNbr>
        </HandledReference>
        <!-- To refuse the declaration, set ResultCode to 0, 2 or 3, add a Diagnosis
             (3: rejected because of blocking anomalies) and one AnomalyReport per
             anomaly (AnomalyClass B: blocking, W: warning, P/NP: percentage based
             or not, D: deduction rights, I: investigation), for example:
        <HandlingResult>
            <ResultCode>0</ResultCode>
            <Diagnosis>3</Diagnosis>
            <AnomalyReport>
                <ErrorID>00011-155</ErrorID>
                <TagName>NOSSRegistrationNbr</TagName>
                <Value>%(registration_number)s</Value>
                <AnomalyClass>B</AnomalyClass>
                <Path>
                    <INSS>%(sample_niss)s</INSS>
                </Path>
            </AnomalyReport>
        </HandlingResult>
        -->
        <HandlingResult>
            <ResultCode>1</ResultCode>
        </HandlingResult>
    </Form>
</NOTIFICATION>
"""


class TestL10nBeDmfaSandboxAnswer(models.TransientModel):
    _name = 'test.l10n.be.dmfa.sandbox.answer'
    _description = 'Belgium: DMFA Sandbox Answer'

    onss_declaration_id = fields.Many2one(
        'l10n.be.onss.declaration',
        string="ONSS Declaration",
        required=True,
        domain=[('environment', '=', 'S')])
    batch_declaration_id = fields.Reference(related='onss_declaration_id.batch_declaration_id')
    declaration_state = fields.Selection(related='onss_declaration_id.state')
    answer_xml = fields.Text(
        string="Answer XML",
        compute='_compute_answer_xml', store=True, readonly=False,
        help="XML content of the answer the ONSS would send back for this declaration. "
             "It is prefilled with a sample answer based on the original declaration.")

    @api.depends('onss_declaration_id', 'onss_declaration_id.state')
    def _compute_answer_xml(self):
        for wizard in self:
            if not wizard.onss_declaration_id:
                wizard.answer_xml = False
            elif wizard.onss_declaration_id.state == 'posted':
                # The first answer acknowledges the reception of the files
                wizard.answer_xml = SAMPLE_ACRF_ANSWER % wizard._get_sample_values()
            else:
                # Then the declaration itself is validated
                wizard.answer_xml = SAMPLE_NOTIFICATION_ANSWER % wizard._get_sample_values()

    def _get_referenced_files(self):
        """ Return the (GO or FI, FI) files of the original submission: the
        ONSS answers reference the submitted files by their name.
        """
        original_files = self.onss_declaration_id.onss_file_ids.filtered(
            lambda f: f.declaration_type in ('DMFA', 'DMWA', 'DMRQ'))
        go_file = original_files.filtered(lambda f: f.file_type == 'GO')[:1]
        fi_file = original_files.filtered(lambda f: f.file_type == 'FI')[:1]
        return go_file or fi_file, fi_file

    def _get_sample_values(self):
        self.ensure_one()
        dmfa = self.onss_declaration_id.batch_declaration_id
        referenced_file, fi_file = self._get_referenced_files()
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        creation_date, creation_hour = now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S.000')
        sample_employee = dmfa.with_context(active_test=False).payslip_ids[:1].employee_id
        return {
            'year_quarter': '%s%s' % (dmfa.year, dmfa.quarter),
            'creation_date': creation_date,
            'creation_hour': creation_hour,
            'referenced_filename': referenced_file.name or '',
            'onss_reference': ''.join(random.choices(string.ascii_uppercase + string.digits, k=13)),
            'handled_identification': {
                'original': 'DMFA',
                'modification': 'DMFAUPD',
                'consultation': 'DMFAREQ',
            }[dmfa.declaration_type],
            'original_creation_date': fi_file.form_creation_date or creation_date,
            'original_creation_hour': fi_file.form_creation_hour or creation_hour,
            'user_reference': dmfa.name or '%s/%s' % (dmfa.year, dmfa.quarter),
            'registration_number': dmfa.company_id.current_payroll_config_id.onss_registration_number or '',
            'company_number': dmfa.company_id.current_payroll_config_id.l10n_be_company_number or '',
            'sample_niss': sample_employee.niss or '00000000000',
        }

    def action_simulate_answer(self):
        self.ensure_one()
        declaration = self.onss_declaration_id
        if declaration.environment != 'S':
            raise UserError(_("Only Test Declarations (S) can be answered in sandbox mode."))
        answer_xml = (self.answer_xml or '').strip()
        if not answer_xml:
            raise UserError(_("Please provide the XML content of the ONSS answer."))
        try:
            data_dict = xml_str_to_dict(answer_xml)
        except Exception as e:  # noqa: BLE001
            raise UserError(_("The answer is not a valid XML document:\n%s", e))
        root_tag = next(iter(data_dict))
        answer_code = ANSWER_CODES.get(root_tag)
        if not answer_code:
            raise UserError(_(
                "Unsupported answer type %(root_tag)s. The supported root elements are: %(supported)s.",
                root_tag=root_tag, supported=', '.join(ANSWER_CODES)))

        base_name = self._get_available_answer_filename(answer_code)
        # Process the answer exactly like files fetched from the ONSS SFTP
        # server, so that it is analysed by the real flow
        onss_files = self.env['l10n.be.onss.declaration']._process_incoming_onss_files([
            (f'FO.{base_name}', answer_xml.encode()),
            (f'GO.{base_name}', b'go'),
        ])

        answered_declaration = onss_files[:1].onss_declaration_id
        if answered_declaration:
            state_labels = dict(declaration._fields['state']._description_selection(self.env))
            message = _(
                'Sandbox answer %(filename)s processed: the declaration is now "%(state)s"',
                filename=onss_files[:1].name,
                state=state_labels.get(answered_declaration.state, answered_declaration.state))
            notification_type = 'success'
        else:
            message = _(
                "Sandbox answer %(filename)s was processed but could not be matched with any "
                "posted declaration, check the FileName tag.",
                filename=onss_files[:1].name)
            notification_type = 'warning'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': notification_type,
                'message': message,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'soft_reload',
                },
            }
        }

    def _get_available_answer_filename(self, answer_code):
        date_str = fields.Date.context_today(self).strftime('%Y%m%d')
        sequence = 0
        while True:
            base_name = '%s.%s.%s.%s.S' % (answer_code, ONSS_EXPEDITOR_NUMBER, date_str, str(sequence).zfill(5))
            if not self.env['l10n.be.onss.file'].search_count([('name', 'like', base_name)], limit=1):
                return base_name
            sequence += 1
