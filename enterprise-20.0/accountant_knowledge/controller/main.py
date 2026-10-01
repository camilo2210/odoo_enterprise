import json
import logging
import re

from io import BytesIO
from urllib.parse import parse_qs, urlencode, urlsplit
from lxml import html, etree
from markupsafe import Markup

from odoo import http, _
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.http import request
from odoo.http.stream import content_disposition
from odoo.tools import (
    format_amount,
    format_date,
    html_sanitize,
    is_html_empty
)
try:
    # only available in modern pypdf, which dropped add_link/addLink
    from pypdf.annotations import Link
    from pypdf.generic import Fit
except ImportError:
    Link = Fit = None

from odoo.tools.pdf import PdfFileReader, PdfFileWriter, PdfReadError
from odoo.addons.accountant_knowledge.tools.color_utils import lighten_color

_logger = logging.getLogger(__name__)


def is_html_element_empty(root):
    return not root.xpath("//*[translate(normalize-space(.), ' ', '') != '']")


def xpath_has_class(class_name):
    """ Returns an XPath expression that checks whether an element contains the
        specified class name. This provides the same behavior as a hypothetical
        hasclass() function, which is not available in lxml's XPath implementation.
        :param str class_name: Class name """
    return f'contains(concat(" ", normalize-space(@class), " "), " { class_name } ")'


def render_placeholder(text, template_variables):
    for to_replace, value in template_variables.items():
        text = text.replace(to_replace, value)
    return text


def get_toc_pdf(audit_report, headings, offset=0):
    toc_html = request.env['ir.qweb']._render(
        'accountant_knowledge.audit_report_table_of_content', {
            'audit_report': audit_report,
            'headings': headings,
            'lighten_color': lighten_color,
            'offset': offset,
            # Variables used in the company layout:
            'base_url': audit_report.get_base_url(),
            'company': audit_report.company_id,
            'is_html_empty': is_html_empty,
            'report_type': 'pdf',
        })

    IrActionsReport = request.env['ir.actions.report']
    Report = IrActionsReport.with_company(audit_report.company_id)
    bodies, *_ = Report._prepare_html(toc_html)

    return PdfFileReader(BytesIO(
        Report._run_pdf_engine_without_processing(
            'wkhtmltopdf',
            bodies,
            specific_paperformat_args={
                'data-report-margin-top': 12,
                'data-report-margin-bottom': 12,
            })))


def get_attached_pdfs(root):
    domains = []
    for element in root.xpath(f'.//*[@data-embedded="file" or { xpath_has_class("o_file_box") }]'):
        if element.get('data-embedded') == 'file':
            embedded_props = json.loads(element.get('data-embedded-props', '{}'))
            file_data = embedded_props.get('fileData')
            if file_data:
                file_type = file_data.get('type')
                if file_type == 'binary':
                    domains.extend([[
                        ('mimetype', 'in', ['application/pdf', 'application/pdf;base64']),
                        ('id', '=', file_data.get('id')),
                        ('access_token', '=', file_data.get('access_token'))
                    ]])
        else:
            for link in element.xpath(f'.//*[{ xpath_has_class("o_link_readonly") }]'):
                parsed_url = urlsplit(link.get('href'))
                match = re.search(r'^\/web\/content\/(?P<ir_attachment_id>[0-9]+)$', parsed_url.path)
                if match:
                    url_params = parse_qs(parsed_url.query)
                    domains.extend([[
                        ('mimetype', 'in', ['application/pdf', 'application/pdf;base64']),
                        ('id', '=', int(match.group('ir_attachment_id'))),
                        ('access_token', '=', url_params.get('access_token', [False])[0])
                    ]])
    if not domains:
        return
    all_ir_attachments = request.env['ir.attachment'].search(Domain.OR(domains))
    for domain in domains:
        ir_attachments = all_ir_attachments.filtered_domain(domain)
        if ir_attachments:
            yield PdfFileReader(BytesIO(ir_attachments[0].raw))


def get_account_reports_pdfs(article, root):
    all_account_report_options = []
    for element in root.xpath('.//*[@data-embedded="accountReport"]'):
        embedded_props = json.loads(element.get('data-embedded-props', '{}'))
        all_account_report_options.append(embedded_props.get('options', {}))

    audit_report = article._get_inherited_audit_report()
    AccountReport = request.env['account.report'].with_company(audit_report.company_id)
    AccountReport = AccountReport.with_context(exclude_page_footer=True)
    all_account_reports = AccountReport.browse({
        account_report_options['report_id']
            for account_report_options in all_account_report_options
    })

    for account_report_options in all_account_report_options:
        company_id = account_report_options.get("forced_companies", [False])[0] \
            or (account_report_options.get("companies") and account_report_options["companies"][0].get("id"))
        account_report_id = account_report_options['report_id']
        account_report = all_account_reports.filtered(
            lambda account_report: account_report.id == account_report_id)

        if account_report:
            if company_id:
                account_report = account_report.with_company(company_id)
            result = account_report.dispatch_report_action(account_report_options, 'export_to_pdf')
            yield PdfFileReader(BytesIO(result.get('file_content')))


def get_pdf_outline(pdf):
    return pdf.outline if hasattr(pdf, 'outline') else pdf.outlines


def flatten_outline(outlines, depth=0):
    """ PyPDF represents outlines as a nested structure reflecting the document's
        heading hierarchy. This method returns a generator for linear traversal
        of the outlines in title order.
        Example of PyPDF outline structure:
        [{ "/Title": "h1", ... }, [{ "/Title": "h2", ... }]]
        For this structure, the method will yield:
        (0, { "/Title": "h1", ... }) then (1, { "/Title": "h2", ... }) where
        the first element of the tuple indicates the heading's depth.
    """
    for outline in outlines:
        if isinstance(outline, list):
            yield from flatten_outline(outline, depth + 1)
        else:
            yield (depth, outline)


def get_links_from_pdf(pdf):
    """ Returns a generator that yields all links present in the given PDF. """
    for page_number, page in enumerate(pdf.pages):
        if '/Annots' not in page:
            continue
        for annotation in page['/Annots']:
            object = annotation.get_object()
            if object['/Subtype'] != '/Link':
                continue
            yield {
                'page_number': page_number,
                'object': object
            }


def delete_all_annotations(page):
    """ Delete all annotations from the given page (i.e: the comments, the links,
        the highlights, the form fields and the markups). """
    if '/Annots' in page:
        del page['/Annots']


def get_front_cover_pdf(audit_report):
    front_cover_html = request.env['ir.qweb']._render(
        'accountant_knowledge.audit_report_front_cover', {
            'audit_report': audit_report,
            'format_date': lambda value, lang_code=None, date_format=False: format_date(request.env, value, lang_code, date_format),
            # Variables used in the company layout:
            'base_url': audit_report.get_base_url(),
            'company': audit_report.company_id,
            'hide_footer_pager': True,
            'is_html_empty': is_html_empty,
            'report_type': 'pdf',
        })

    IrActionsReport = request.env['ir.actions.report']
    Report = IrActionsReport.with_company(audit_report.company_id)
    bodies, _res_ids, header, footer, _specific_paperformat_args = Report._prepare_html(front_cover_html)

    return PdfFileReader(BytesIO(
        Report._run_pdf_engine_without_processing(
            'wkhtmltopdf',
            bodies,
            header=header,
            footer=footer,
            specific_paperformat_args={
                'data-report-margin-top': 100,
                'data-report-header-spacing': 100,
            })))


def get_article_pdf(article, root, template_variables, html_template_variables):
    audit_report = article._get_inherited_audit_report()

    # Replace all the placeholder values:
    for element in root.iter():
        if element.text:
            element.text = render_placeholder(element.text, template_variables)
            # Render the HTML template variables:
            for to_replace, value in html_template_variables.items():
                if to_replace not in element.text:
                    continue
                node = html.fragment_fromstring(value, create_parent='div')
                element.text = element.text.replace(to_replace, '')
                element.append(node)
        if element.tail:
            element.tail = render_placeholder(element.tail, template_variables)

    elements = []
    for child in root.getchildren():
        elements.append(
            html.tostring(child, encoding='unicode', method='html'))

    article_body = Markup(html_sanitize(''.join(elements)))
    article_html = request.env['ir.qweb']._render(
        'accountant_knowledge.audit_report_page_layout', {
            'body': article_body,
            # Variables used in the company layout:
            'base_url': audit_report.get_base_url(),
            'company': audit_report.company_id,
            'is_html_empty': is_html_empty,
            'report_type': 'pdf',
        })

    IrActionsReport = request.env['ir.actions.report']
    Report = IrActionsReport.with_company(audit_report.company_id)
    bodies, *_ = Report._prepare_html(article_html)

    return PdfFileReader(BytesIO(
        Report._run_pdf_engine_without_processing(
            'wkhtmltopdf',
            bodies,
            specific_paperformat_args={
                'data-report-margin-top': 12,
                'data-report-margin-bottom': 12,
            })))


def get_title_page_pdf(article, title):
    audit_report = article._get_inherited_audit_report()
    title_page_html = request.env['ir.qweb']._render(
        'accountant_knowledge.audit_report_title_page', {
            'audit_report': audit_report,
            'title': title,
            # Variables used in the company layout:
            'base_url': audit_report.get_base_url(),
            'company': audit_report.company_id,
            'is_html_empty': is_html_empty,
            'report_type': 'pdf',
        })

    IrActionsReport = request.env['ir.actions.report']
    Report = IrActionsReport.with_company(audit_report.company_id)
    bodies, *_ = Report._prepare_html(title_page_html)

    return PdfFileReader(BytesIO(
        Report._run_pdf_engine_without_processing('wkhtmltopdf', bodies)))


def compute_total_assets(audit_report):
    balance_sheet_report = request.env.ref('account_reports.balance_sheet').with_company(audit_report.company_id)
    balance_sheet_report_options = balance_sheet_report.get_options({
        'forced_companies': audit_report.company_id.ids,
        'date': {
            'date_from': str(audit_report.start_date),
            'date_to': str(audit_report.end_date),
        },
        'rounding_unit': 'decimals',
    })
    all_expressions = next(iter(
        balance_sheet_report._compute_expression_totals_for_each_column_group(
            balance_sheet_report.line_ids.expression_ids,
            balance_sheet_report_options).values()))
    total_assets_line = request.env.ref('account_reports.account_financial_report_total_assets0')
    for expression, totals in all_expressions.items():
        if expression.report_line_id == total_assets_line:
            return totals.get('value')
    return 0


def compute_net_profit_and_total_revenue(audit_report):
    profit_and_loss_report = request.env.ref('account_reports.profit_and_loss').with_company(audit_report.company_id)
    profit_and_loss_report_options = profit_and_loss_report.get_options({
        'forced_companies': audit_report.company_id.ids,
        'date': {
            'date_from': str(audit_report.start_date),
            'date_to': str(audit_report.end_date),
        },
        'rounding_unit': 'decimals',
    })
    all_expressions = next(iter(
        profit_and_loss_report._compute_expression_totals_for_each_column_group(
            profit_and_loss_report.line_ids.expression_ids,
            profit_and_loss_report_options).values()))

    net_profit = 0
    total_revenue = 0

    net_profit_report_line = request.env.ref('account_reports.account_financial_report_net_profit0')
    total_revenue_report_line = request.env.ref('account_reports.account_financial_report_revenue0')

    for expression, totals in all_expressions.items():
        if expression.report_line_id == net_profit_report_line:
            net_profit = totals.get('value')
        elif expression.report_line_id == total_revenue_report_line:
            total_revenue = totals.get('value')

    return {
        'net_profit': net_profit,
        'total_revenue': total_revenue
    }


def get_template_variables(article):
    audit_report = article._get_inherited_audit_report()
    results = compute_net_profit_and_total_revenue(audit_report)
    return {
        "{{ start of period }}": format_date(request.env, audit_report.start_date),
        "{{ end of period }}": format_date(request.env, audit_report.end_date),
        "{{ company name }}": audit_report.company_id.name,
        "{{ total balance sheet }}": format_amount(request.env, compute_total_assets(audit_report), audit_report.company_id.currency_id),
        "{{ revenue }}": format_amount(request.env, results.get('total_revenue', 0), audit_report.company_id.currency_id),
        "{{ net accounting result }}": format_amount(request.env, results.get('net_profit', 0), audit_report.company_id.currency_id)
    }


class KnowledgeAuditReportController(http.Controller):

    def _get_template_variables(self, article):
        return get_template_variables(article)

    def _get_html_template_variables(self, article):
        return {}

    @http.route(
        '/knowledge_accountant/article/<model("knowledge.article"):root_article>/audit_report',
        type='http', auth='user', methods=['GET'])
    def export_article_to_pdf(self, root_article, include_pdf_files, include_child_articles, **kwargs):
        audit_report = root_article._get_inherited_audit_report()

        if not audit_report.company_id.external_report_layout_id:
            raise UserError(_(
                '''Please make sure a document layout has been set for the '''
                '''company linked to the audit report you intend to export.'''))

        # Dirty hack to force the print delay to 100ms during our PDF generation
        # It defaults to 1000ms inside `_run_wkhtmltopdf` and as we generate a lot
        # of different pdf files, it adds an unnecessary significant number of times.

        IrConfigParameterSudo = request.env['ir.config_parameter'].sudo()
        print_delay = IrConfigParameterSudo.get_int('report.print_delay')
        IrConfigParameterSudo.set_int('report.print_delay', 100)

        body_pdfs = []
        headings = []
        root_article_body = html.fragment_fromstring(root_article.body, create_parent='div')
        generate_headings = root_article_body.find('.//*[@data-embedded="articleIndex"]') is not None
        page_offset_in_body = 0

        stack = [root_article]
        template_variables = self._get_template_variables(root_article)
        html_template_variables = self._get_html_template_variables(root_article)

        SUPPORTED_IMAGE_TYPES = {
            'image/jpeg', 'image/png', 'image/gif',
            'image/webp', 'image/svg+xml'
        }

        while stack:
            article = stack.pop()
            root = html.fragment_fromstring(article.body, create_parent='div')

            # Remove elements with the `d-print-none` class to avoid empty pages:
            for element in root.xpath(f'//*[{ xpath_has_class("d-print-none") }]'):
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)

            # Replace the embedded images with standard <img /> tags:
            for element in root.xpath('.//*[@data-embedded="file"]'):
                try:
                    embedded_props = json.loads(
                        element.get('data-embedded-props', '{}'))
                except json.JSONDecodeError:
                    continue

                if not isinstance(embedded_props, dict):
                    continue

                file_data = embedded_props.get('fileData', {})
                if not isinstance(file_data, dict):
                    continue

                is_embedded_image = (
                        file_data.get('type') == 'binary'
                    and file_data.get('mimetype') in SUPPORTED_IMAGE_TYPES
                )

                if not is_embedded_image:
                    continue

                if attachment_id := file_data["id"]:
                    url = f'/web/content/{attachment_id}'
                    if access_token := file_data.get('access_token'):
                        url += '?' + urlencode({'access_token': access_token})

                    img = etree.Element('img', src=url, style='max-width: 100%')
                    img.tail = element.tail
                    parent = element.getparent()
                    parent.replace(element, img)

            article_headings = root.xpath(
                "//*[self::h1 or self::h2 or self::h3][translate(normalize-space(.), ' ', '') != '']")
            article_has_only_one_nonempty_heading = (
                len(article_headings) == 1 and
                not bool(root.xpath(
                    "//text()[translate(normalize-space(.), ' ', '') != '' and not(ancestor::h1 or ancestor::h2 or ancestor::h3)]")))

            # Append a title page if the article only contains an h1, h2 or h3
            if article_has_only_one_nonempty_heading:
                title = article_headings[0].text
                title_page_pdf = get_title_page_pdf(article, title)
                if generate_headings:
                    try:
                        for (depth, outline) in flatten_outline(get_pdf_outline(title_page_pdf)):
                            headings.append({
                                'page_offset_in_body': page_offset_in_body,
                                'depth': depth,
                                'outline': outline
                            })
                    except PdfReadError:
                        # version 1.26 of PyPDF2 is not capable of generating the outline / headers
                        # see https://github.com/py-pdf/pypdf/issues/193
                        _logger.warning('Unable to generate Annual Report heading, please update your PyPDF version.')
                        generate_headings = False

                body_pdfs.append(title_page_pdf)
                page_offset_in_body += len(title_page_pdf.pages)

            # Append the account reports present in the article:
            account_report_pdfs = list(get_account_reports_pdfs(article, root))
            body_pdfs.extend(account_report_pdfs)
            page_offset_in_body += sum(
                len(account_report_pdf.pages) for account_report_pdf in account_report_pdfs)

            # Append the article body if not empty:
            if not article_has_only_one_nonempty_heading and not is_html_element_empty(root):
                article_pdf = get_article_pdf(article, root, template_variables, html_template_variables)
                if generate_headings:
                    try:
                        for (depth, outline) in flatten_outline(get_pdf_outline(article_pdf)):
                            headings.append({
                                'page_offset_in_body': page_offset_in_body,
                                'depth': depth,
                                'outline': outline
                            })
                    except PdfReadError:
                        # version 1.26 of PyPDF2 is not capable of generating the outline / headers
                        # see https://github.com/py-pdf/pypdf/issues/193
                        _logger.warning('Unable to generate Annual Report heading, please update your PyPDF version.')
                        generate_headings = False

                body_pdfs.append(article_pdf)
                page_offset_in_body += len(article_pdf.pages)

            # Append the pdf attachments present in the article:
            if include_pdf_files == '1':
                attached_pdfs = list(get_attached_pdfs(root))
                body_pdfs.extend(attached_pdfs)
                page_offset_in_body += sum(
                    len(attached_pdf.pages) for attached_pdf in attached_pdfs)

            # Append the child articles:
            if include_child_articles == '1':
                stack.extend(article.child_ids.sorted(
                    lambda child: child.sequence, reverse=True))

        front_cover_pdf = get_front_cover_pdf(audit_report)
        # Create the PDF output:
        writer = PdfFileWriter()
        writer.append_pages_from_reader(front_cover_pdf)
        toc_pdf = False
        toc_links = []
        if headings:
            toc_pdf = get_toc_pdf(audit_report, headings)
            # Regenerate the table of content to update the page numbers:
            toc_pdf = get_toc_pdf(audit_report, headings, offset=len(toc_pdf.pages))
            toc_links = list(get_links_from_pdf(toc_pdf))

        if toc_pdf:
            writer.append_pages_from_reader(toc_pdf,
                after_page_append=delete_all_annotations)
        for body_pdf in body_pdfs:
            writer.append_pages_from_reader(body_pdf)

        toc_pdf_num_pages = (len(toc_pdf.pages) if toc_pdf else 0)
        # Add the links:
        add_link = getattr(writer, 'add_link', None) or getattr(writer, 'addLink', None)
        for link, heading in zip(toc_links, headings):
            target_page = heading['outline']['/Page'] + len(front_cover_pdf.pages) + toc_pdf_num_pages + heading['page_offset_in_body']
            if add_link:
                # old PyPDF2 / transitional pypdf API
                add_link(
                    link['page_number'] + len(front_cover_pdf.pages),
                    target_page,
                    link['object']['/Rect'],
                    [0, 0, 0],
                    '/XYZ',
                    heading['outline']['/Left'],
                    heading['outline']['/Top'],
                    heading['outline']['/Zoom'])
            else:
                # modern pypdf (>= 5.0) dropped add_link/addLink entirely
                writer.add_annotation(
                    link['page_number'] + len(front_cover_pdf.pages),
                    Link(
                        rect=link['object']['/Rect'],
                        border=[0, 0, 0],
                        target_page_index=target_page,
                        fit=Fit.xyz(
                            left=heading['outline']['/Left'],
                            top=heading['outline']['/Top'],
                            zoom=heading['outline']['/Zoom'])))

        # Add the outlines:
        writer.page_mode = "/UseOutlines"

        add_bookmark = getattr(writer, 'add_outline_item', None) or writer.add_bookmark
        bookmarks_stack = []
        for heading in headings:
            parent_heading_depth, parent_bookmark = bookmarks_stack[-1] \
                if bookmarks_stack else (0, None)

            while bookmarks_stack and heading['depth'] <= parent_heading_depth:
                bookmarks_stack.pop()
                parent_heading_depth, parent_bookmark = bookmarks_stack[-1] \
                    if bookmarks_stack else (0, None)

            page_number = heading['outline']['/Page'] + len(front_cover_pdf.pages) + toc_pdf_num_pages + heading['page_offset_in_body']
            if Fit is not None:
                # modern pypdf (>= 5.0): add_outline_item() gained a `before` parameter
                # and now requires a Fit object instead of a fit-type string + xyz args
                bookmark = add_bookmark(
                    heading['outline']['/Title'],
                    page_number,
                    parent_bookmark, None, None, False, False,
                    Fit.xyz(
                        left=heading['outline']['/Left'],
                        top=heading['outline']['/Top'],
                        zoom=heading['outline']['/Zoom'])
                )
            else:
                # old PyPDF2 / transitional pypdf API
                bookmark = add_bookmark(
                    heading['outline']['/Title'],
                    page_number,
                    parent_bookmark, None, False, False,
                    '/XYZ',
                    heading['outline']['/Left'],
                    heading['outline']['/Top'],
                    heading['outline']['/Zoom']
                )

            if heading['depth'] >= parent_heading_depth:
                # Record heading depth to handle skipped levels
                bookmarks_stack.append((heading['depth'], bookmark))

        # Add the page numbers:
        number_of_pages = len(writer.pages) - len(front_cover_pdf.pages)

        IrActionsReport = request.env['ir.actions.report']
        Report = IrActionsReport.with_company(audit_report.company_id)
        bodies = [
            request.env['ir.qweb']._render(
                'accountant_knowledge.audit_report_empty_document',
                {'number_of_pages': number_of_pages})]
        empty_pdf_for_page_numbers = PdfFileReader(BytesIO(
            Report._run_pdf_engine_without_processing(
                'wkhtmltopdf',
                bodies,
                specific_paperformat_args={
                    'data-report-margin-top': 0,
                    'data-report-margin-left': 0,
                    'data-report-margin-right': 0,
                    'data-report-margin-bottom': 16,
                    'data-report-header-spacing': 0,
                },
                footer=request.env['ir.qweb']._render(
                    'accountant_knowledge.audit_report_footer', {
                        'audit_report': audit_report,
                        'lighten_color': lighten_color,
                    }))))

        for k in range(number_of_pages):
            page = writer.get_page(k + len(front_cover_pdf.pages))
            page.merge_page(empty_pdf_for_page_numbers.pages[k])
            page.compress_content_streams()

        output_stream = BytesIO()
        writer.write(output_stream)
        pdf_bytes = output_stream.getvalue()

        # Restore the print delay:
        IrConfigParameterSudo.set_int('report.print_delay', print_delay)

        return request.make_response(pdf_bytes, headers=[
            ('Content-Disposition', content_disposition(f'{root_article.name}.pdf')),  # File name
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf_bytes)),
        ])
