# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io
import json
import logging
import re

from werkzeug.exceptions import Forbidden

from odoo import api
from odoo.addons.base.models.ir_qweb import QWebError
from odoo.exceptions import UserError
from odoo.http import Controller, request, route
from odoo.http.dispatcher import serialize_exception
from odoo.http.stream import content_disposition
from odoo.tools.json import json_default
from odoo.tools.pdf import PdfFileReader, PdfFileWriter
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class HrPayroll(Controller):

    @route(["/print/payslips"], type='http', auth='user')
    def get_payroll_report_print(self, list_ids='', **post):
        if not request.env.user.has_group('hr_payroll.group_hr_payroll_user') or not list_ids or re.search("[^0-9|,]", list_ids):
            return request.not_found()

        ids = [int(s) for s in list_ids.split(',')]
        payslips = request.env['hr.payslip'].browse(ids)

        pdf_writer = PdfFileWriter()
        payslip_reports = payslips._get_pdf_reports()
        pdf_generic_name = request.env._("Payslip")
        attachments_vals_list = []

        for report, slips in payslip_reports.items():
            payslips_languages = slips._get_payslips_pdf_lang()
            for payslip in slips:
                try:
                    pdf_content = payslip._prepare_payslip_pdf_content(report, payslips_languages.get(payslip, (None, None)))
                    reader = PdfFileReader(io.BytesIO(pdf_content), strict=False, overwriteWarnings=False)
                    pdf_writer.append_pages_from_reader(reader)
                except QWebError as error:
                    raise UserError(error)
                if report.print_report_name:
                    pdf_name = safe_eval(report.print_report_name, {'object': payslip})
                else:
                    pdf_name = pdf_generic_name

                attachments_vals_list.append({
                    'name': pdf_name,
                    'type': 'binary',
                    'raw': pdf_content,
                    'res_model': payslip._name,
                    'res_id': payslip.id
                })

        _buffer = io.BytesIO()
        pdf_writer.write(_buffer)
        merged_pdf = _buffer.getvalue()
        _buffer.close()

        if len(payslip_reports) == 1 and len(payslips) == 1 and payslips.struct_id.report_id.print_report_name:
            report_name = safe_eval(payslips.struct_id.report_id.print_report_name, {'object': payslips})
        else:
            report_name = ' - '.join(r.name for r in list(payslip_reports.keys()))
            employees = payslips.employee_id.mapped('name')
            if len(employees) == 1:
                report_name = '%s - %s' % (report_name, employees[0])

        request.env['ir.attachment'].sudo().create(attachments_vals_list)

        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(merged_pdf)),
            ('Content-Disposition', content_disposition(report_name + '.pdf'))
        ]

        return request.make_response(merged_pdf, headers=pdfhttpheaders)

    @route('/hr_payroll/dashboard/warnings', type='http', auth='user')
    def get_dashboard_payroll_warnings(self, **kwargs):
        """Stream the dashboard warning cards, one JSON object per line.

        Each card is written to the socket as soon as it is computed, so a
        warning yielding several cards does not withhold the first one. A
        warning that fails to compute or to serialize does not abort the
        stream: it is streamed as an error card instead.
        """
        if not request.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            raise Forbidden()

        db_registry = request.env.registry
        uid = request.env.uid
        cids_str = request.cookies.get('cids', str(request.env.user.company_id.id))
        cids = [int(cid) for cid in cids_str.split('-')]
        context = dict(request.env.context, allowed_company_ids=cids)

        def encode(payload):
            return (json.dumps(payload, default=json_default) + '\n').encode()

        def stream():
            with db_registry.cursor(readonly=True) as cr:
                env = api.Environment(cr, uid, context)
                Warning = env['hr.payroll.warning']
                for warning in Warning.search(Warning._get_effective_warning_domain(env.company)):
                    try:
                        for warning_data in warning._iter_applicable_payroll_warnings(env.company):
                            yield encode({'type': 'card', 'warning': warning._serialize_card(warning_data)})
                    except Exception as e:
                        _logger.exception("Could not compute payroll dashboard warning %s: %s", warning.id, warning.name)
                        cr.rollback()
                        yield encode({'type': 'card', 'warning': warning._serialize_error_card(serialize_exception(e))})
                    else:
                        cr.commit()
                yield encode({'type': 'done'})

        return request.make_response(
                    stream(),
                    headers=[
                        ('Content-Type', 'application/x-ndjson; charset=utf-8'),
                        ('X-Accel-Buffering', 'no'),  # prevent proxies from buffering response
                    ],
                )
