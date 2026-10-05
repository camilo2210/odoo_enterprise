from itertools import count
from uuid import uuid4

from odoo import Command
from odoo.tools import LazyTranslate
from odoo.addons.account_reports.utils.report_data_objects import AccountReportColumnData, AccountReportLineData

_lt = LazyTranslate(__name__)

CODE_TO_NAME = {
    'l10n_fr_2031_annexes_partner_natural': 'Line',
    'l10n_fr_2031_annexes_partner_legal': 'Line',
    'l10n_fr_2031_annexes_other_establishments_addresses': 'Line',
    'l10n_fr_2031_annexes_h_tax_free_capital_gains': 'Line',
    'l10n_fr_2033_c_iii_immo': 'Asset',
    'FR_2033_D_I_C': 'Compensation',
    'FR_2033_F_capital_held_legal_entities': 'Legal Entity',
    'FR_2033_F_capital_held_individuals': 'Individual',
    'FR2033G_905': 'Subsidiary',
    'FR_2065_SD_H': 'Remuneration',
    'FR_2065_SD_I_2': 'Establishment',
    'l10n_fr_2069_special_cases_first_case': 'Line',
    'l10n_fr_2069_special_cases_second_case': 'Line',
    'l10n_fr_2069_sponsorship': 'Line',
}


def _set_custom_options(options, name):
    """ Sets custom display and configuration options for an account report.

        :param options: The options dictionary for the report.
        :param name: The custom name to assign to the report line template.
    """
    options['ignore_totals_below_sections'] = True
    options['custom_display_config'].setdefault('templates', {})['AccountReportLineName'] = name


def _display_add_section_line(report, lines, codes, name):
    """ Adds a new section line after specific report lines matching the given codes.

        :param report: The report used to generate the generic line ID.
        :param lines: The list of existing report lines to process.
        :param codes: A collection of line codes that trigger the addition of a new section line.
        :param name: The name to assign to the newly created section line.
        :return: A new list of report lines including the inserted section lines.
    """
    new_lines = []
    for line in lines:
        new_lines.append(line)
        if not line.code in codes:
            continue
        new_lines.append(AccountReportLineData(
            id=report._get_generic_line_id(None, None, markup='', parent_line_id=line.id),
            name=name,
            level=line.level + 2,
            parent_id=line.id,
            unfoldable=False,
            code='add_new_section',
            columns=[AccountReportColumnData() for _ in line.columns],
        ))
    return new_lines


def _remove_section(handler, options, params=None, exclude_code=[]):
    """ Removes a section line and its children from an account report, updating sequences and names accordingly.

        :param handler: The handler providing access to the Odoo environment records.
        :param options: The options dictionary for the report.
        :param params: An optional dictionary containing parameters, expected to hold the target 'line' details to remove.
        :param exclude_code: A list of line codes to exclude during the sequence and name update process.
        :return: The parent line record of the removed section.
    """
    report = handler.env['account.report'].browse(options['report_id'])
    line_id = report._get_res_id_from_line_id(params.get('line', {}).get('id'), 'account.report.line')
    line = handler.env['account.report.line'].browse(line_id)
    parent_line = line.parent_id
    default_name = handler.env._(CODE_TO_NAME.get(parent_line.code, 'Line'))  # pylint: disable=E8502

    _remove_section_children(line.children_ids)
    _update_sequences_and_name(removed_line=line, default_name=default_name, exclude_code=exclude_code)
    line.unlink()
    return parent_line


def _add_section(handler, options, sections={}, expressions={}, params=None, exclude_code=[]):
    """ Dynamically adds a new section line and its corresponding children or expressions to an account report.

        :param handler: The handler object providing access to the Odoo environment records.
        :param options: The options dictionary for the report.
        :param sections: A dictionary mapping parent line codes to their specific child field definitions.
        :param expressions: A dictionary containing expression definitions to attach to the new section line.
        :param params: An optional dictionary containing parameters, expected to hold the target 'line' details.
        :param exclude_code: A list of line codes to exclude when computing sequences and child counts.
        :return: The parent line record to which the new section was added.
    """
    report = handler.env['account.report'].browse(options['report_id'])
    line = params.get('line', {})
    parent_line_id = report._get_res_id_from_line_id(line.get('parent_id'), 'account.report.line')
    parent_line = handler.env['account.report.line'].browse(parent_line_id)
    default_name = handler.env._(CODE_TO_NAME.get(parent_line.code, 'Line'))  # pylint: disable=E8502
    fields = sections.get(parent_line.code, [{}])

    default_code = f'{parent_line.code}_parent_section_line_'

    section_delta = _compute_section_len(fields) * 10
    if len(parent_line.children_ids) - len(exclude_code):
        last_child_sequence = max(parent_line.children_ids.filtered(lambda line: not any(ex in line.code for ex in exclude_code)).mapped('sequence')) + section_delta
    else:
        last_child_sequence = parent_line.sequence

    sequence = count(last_child_sequence, 10)
    lines_to_shift = report.line_ids.filtered(lambda line: line.sequence > last_child_sequence)
    for line in lines_to_shift:
        line.sequence += section_delta

    code_suffix = uuid4().hex
    level = parent_line.hierarchy_level + 2

    handler.env['account.report.line'].create({
        'name': f"{default_name} {len(parent_line.children_ids) + 1 - len(exclude_code)}",
        'report_id': report.id,
        'sequence': next(sequence),
        'hierarchy_level': level,
        'code': f'{default_code}{code_suffix}_dynadded',
        'foldability': 'foldable',
        'parent_id': parent_line.id,
        'children_ids': _build_children_section_data(
            handler=handler,
            fields=fields,
            sequence=sequence,
            report=report,
            base_code=parent_line.code,
            code_suffix=code_suffix,
            level=level + 2,
        ) if not len(expressions) else [],
        'expression_ids': _build_expressions_section_data(
            fields=expressions,
            default_code=default_code,
            code_suffix=code_suffix,
        ) if len(expressions) else [],
    })

    return parent_line


def _remove_section_children(children):
    """ Recursively removes all nested child section lines from the database.

        :param children: A recordset or collection of child report lines to delete.
    """
    for child in children:
        _remove_section_children(child.children_ids)
        child.unlink()


def _update_sequences_and_name(removed_line, default_name, exclude_code=[]):
    """ Sequentially renumbers both the sequence field and the names of remaining sibling lines.

        :param removed_line: The report line record that is being removed.
        :param default_name: The base name string used to re-sequence the line names.
        :param exclude_code: A list of line codes to exclude from the process.
    """
    lines_after = removed_line.parent_id.children_ids.filtered(lambda line: line.sequence > removed_line.sequence and line.code not in exclude_code)
    lines_before = removed_line.parent_id.children_ids.filtered(lambda line: line.code not in exclude_code) - lines_after

    for order, line in enumerate(lines_after, start=len(lines_before)):
        line.name = f"{default_name} {order}"


def _compute_section_len(fields):
    """ Computes the total number of sections by recursively counting fields and their nested children.

        :param fields: A list of dictionaries representing the report fields configuration.
        :return: The total count of all top-level and deeply nested child fields.
    """
    return len(fields) + sum(
        _compute_section_len(field.get('children', []))
        for field in fields
        if field.get('figure_type') == 'parent'
    )


def _update_aggregation_formulas(parent_line, total_line, labels, default_code):
    """ Recursively builds and updates the aggregation formulas for a total line's expressions based on matching child lines.

        :param parent_line: The parent report line record whose nested children will be aggregated.
        :param total_line: The report line record whose expression formulas will be updated.
        :param labels: A collection of expression labels to process and update.
        :param default_code: The code string used to filter which lines are included in the formula.
    """
    def build_formula(lines, expression_label, code):
        parts = []
        for line in lines:
            if line.children_ids:
                parts.extend(build_formula(line.children_ids, expression_label, code))
            elif code in line.code:
                parts.append(f'{line.code}.{expression_label}')
        return parts

    for label in labels:
        formula = ' + '.join(build_formula(parent_line.children_ids, label, default_code))
        if expression := total_line.expression_ids.filtered(lambda expr: expr.label == label):
            expression.formula = formula or '0'


def _build_children_section_data(handler, fields, sequence, report, base_code, code_suffix, level):
    """ Creates the child lines for a parent report line using a specified format dictionary.

        :param handler: The handler object providing access to the Odoo environment records.
        :param fields: A configuration dictionary specifying the format, engines, and structure of the child lines.
        :param sequence: A counter used to assign the correct layout sequence to each child line.
        :param report: The target account report record.
        :param base_code: A base prefix string used to construct the unique line code.
        :param code_suffix: A unique identifier suffix used to construct the unique line code.
        :param level: The hierarchy depth level to assign to the new child lines.
        :return: A list of the created child report lines.
    """
    children = []
    for field in fields:
        is_parent = field['figure_type'] == 'parent'
        if not is_parent:
            engine = field['engine']
        children.append(Command.create({
            'name': handler.env._(field['title']),  # pylint: disable=E8502
            'code': f'{base_code}_{field['default_suffix']}_{code_suffix}_dynadded',
            'sequence': next(sequence),
            'hierarchy_level': level,
            'report_id': report.id,
            'children_ids': _build_children_section_data(
                handler=handler,
                fields=field.get('children', {}),
                sequence=sequence,
                report=report,
                base_code=base_code,
                code_suffix=code_suffix,
                level=level + 2
            ) if is_parent else [],
            'expression_ids': [Command.create({
                'label': 'balance',
                'engine': engine,
                'formula': 'most_recent' if engine == 'external' else field.get('formula', 'res.partner'),
                'date_scope': 'from_beginning',
                'subformula': f'editable;rounding={2 if field['figure_type'] == 'percentage' else 0}' if engine == 'external' else None,
                'figure_type': field['figure_type'],
            })] if not is_parent else [],
        }))
    return children


def _build_expressions_section_data(fields, default_code, code_suffix):
    """ Generates report expression records for a report line based on a list of expression definitions.

        :param fields: A list of dictionaries containing the data definitions for each expression.
        :param default_code: A base prefix string used to construct the unique line code.
        :param code_suffix: A unique identifier suffix used to construct the unique line code.
        :return: A list of the created report expressions.
    """
    return [
        Command.create({
            'label': expression['label'],
            'engine': expression['engine'],
            'formula': expression['formula'].format(default_code=default_code, code_suffix=code_suffix),
            'date_scope': expression['date_scope'],
            'subformula': expression.get('subformula'),
            'figure_type': expression['figure_type'],
        }) for expression in fields
    ]
