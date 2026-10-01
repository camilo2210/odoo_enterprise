import json
from odoo import fields, models
from odoo.tools.misc import format_datetime
from odoo.addons.spreadsheet.utils.helpers import (
    DEFAULT_COLUMN_WIDTH,
    MIN_COLUMNS,
    MIN_ROWS,
    to_cell_reference,
)


class SignTemplate(models.Model):
    _inherit = "sign.template"

    def action_sign_template_open_linked_spreadsheet(self):
        """ Create and open a new spreadsheet containing the template answers.

        This method generates a new document in the documents application populated
        with the formatted data from `_build_spreadsheet_data`.

        :return: The action to open the newly created spreadsheet.
        :rtype: dict
        """
        self.ensure_one()

        folder_sudo = self._get_sign_answers_folder_sudo()
        datetime_str = format_datetime(self.env, fields.Datetime.now())

        action = self.env['documents.document'].sudo().action_open_new_spreadsheet({
            'name': f"{self.name} (#{self.id}) {self.env._('Answers')} - {datetime_str}",
            'folder_id': folder_sudo.id,
            'owner_id': False,
            'spreadsheet_data': json.dumps(self._build_spreadsheet_data()),
        })

        return action

    def _compute_spreadsheet_table_for_doc(self, document_id=None, sign_requests=None):
        """ Generate the spreadsheet data table for the signed documents.

        This method organizes the signed data into a columnar structure suitable
        for export or spreadsheet views. It sorts sign items by position (page, x, y)
        and sign requests by date (latest first).

        :param int document_id: Optional ID of a specific document to filter items.
        :param recordset sign_requests: Optional 'sign.request' records to process.
                                        If not provided, uses self.sign_request_ids.
        :return: A tuple containing:
                 - result (list): List of columns, where each column is a list of cell values.
                 - checkbox_indices (list): Indices of columns containing boolean/checkbox values.
        :rtype: tuple
        """
        self.ensure_one()
        sign_requests = sign_requests or self.sign_request_ids
        signed_requests = sign_requests.filtered(lambda r: r.state == "signed")
        request_items = signed_requests.request_item_ids.sorted('signing_date', reverse=True)
        n_rows = len(request_items) + 1  # +1 for header row

        all_items = self.sign_item_ids
        if document_id:
            all_items = all_items.filtered(lambda i: i.document_id.id == document_id)
            all_items = all_items.sorted("page, posY, posX")
        else:
            all_items = all_items.sorted("document_id, page, posY, posX")

        # Separate initials from other items ---
        initial_items = all_items.filtered(lambda i: i.type_id.item_type == 'initial')
        other_items = all_items - initial_items

        # 1. Build table columns ---
        result = []
        checkbox_indices = []

        # Timestamp & Signer columns
        timestamp_col = self._empty_column(self.env._("Timestamp"), n_rows)
        signer_col = self._empty_column(self.env._("Signer"), n_rows)
        result.extend([timestamp_col, signer_col])

        initial_cols, initials_column, initial_columns_map = self._prepare_initials_columns(initial_items, request_items, n_rows)
        result.extend(initial_cols)
        # Other sign items
        field_columns = {}
        for item in other_items:
            if item.type_id.item_type == 'checkbox':
                checkbox_indices.append(len(result))

            col = self._empty_column(item.type_id.name, n_rows)
            field_columns[item.id] = col
            result.append(col)

        # 2. Fill table rows ---
        for row_idx, req_item in enumerate(request_items, start=1):
            # Timestamp & Signer
            sign_values = req_item.sudo().sign_item_value_ids
            timestamp_col[row_idx]['value'] = format_datetime(self.env, max(sign_values.mapped('create_date'))) if sign_values else (fields.Date.to_string(req_item.signing_date) or "")
            signer_col[row_idx]['value'] = req_item.partner_id.display_name or ""

            vals_map = {v.sign_item_id.id: v.value for v in sign_values}

            # Initials
            if initials_column:
                initials_column[row_idx]['value'] = self.env._("Signed")
            else:
                for i in initial_items:
                    initial_columns_map[i.id][row_idx]['value'] = self.env._("Signed") if vals_map.get(i.id) else ""

            # Other items
            for item in other_items:
                raw_val = vals_map.get(item.id, "")
                field_columns[item.id][row_idx]['value'] = self._format_sign_value(item, raw_val)

        return result, checkbox_indices

    def _prepare_initials_columns(self, initial_items, request_items, n_rows):
        """ Determine how to handle initials and generate the corresponding columns.

        This method checks if all 'initial' items are signed across all requests.
        If they are, it generates a single grouped 'Initials' column. If any are
        missing, it generates individual columns for each initial item to show
        granular status.

        :param recordset initial_items: The 'sign.item' records of type 'initial'.
        :param recordset request_items: The 'sign.request.item' records to check.
        :param int n_rows: The total number of rows (header + data) to generate.
        :return: A tuple containing:
                 - columns_to_add (list): The list of generated column structures.
                 - initials_column (list|None): Reference to the grouped column if created.
                 - initial_columns_map (dict): Mapping of item_id -> column if expanded.
        :rtype: tuple
        """
        if not initial_items:
            return [], None, {}

        # Check if all initials are signed in all request items
        all_signed = True
        for req_item in request_items:
            vals_map = {v.sign_item_id.id: v.value for v in req_item.sudo().sign_item_value_ids}
            if any(not vals_map.get(i.id) for i in initial_items):
                all_signed = False
                break

        columns_to_add = []
        initials_column = None
        initial_columns_map = {}

        if all_signed:
            # Scenario A: Single column for initials
            initials_column = self._empty_column(self.env._("Initials"), n_rows)
            columns_to_add.append(initials_column)
        else:
            # Scenario B: One column per initial
            for i in initial_items:
                header_text = f"{i.type_id.name} ({self.env._('Page')} {i.page})"
                col = self._empty_column(header_text, n_rows)
                initial_columns_map[i.id] = col
                columns_to_add.append(col)

        return columns_to_add, initials_column, initial_columns_map

    def _empty_column(self, header, n_rows):
        """ Create a column structure with a header and empty values.

        :param str header: The text to display in the column header.
        :param int n_rows: The total number of rows (including the header) to generate.
        :return: A list of dictionaries representing cells.
        :rtype: list
        """
        return [{'value': header}] + [{'value': ""} for i in range(n_rows - 1)]

    def _build_spreadsheet_data(self, sign_requests=None):
        """ Generate the spreadsheet data structure for the template.

        This method constructs the JSON-compatible dictionary required to render the
        spreadsheet. It creates a dedicated sheet for each document in the template,
        populates it with signed data, and applies formatting (header styles,
        checkbox validation, frozen panes).

        :param recordset sign_requests: Optional 'sign.request' records to include.
                                        If not provided, uses self.sign_request_ids.
        :return: A dictionary containing the spreadsheet structure (sheets, styles, settings).
        :rtype: dict
        """
        self.ensure_one()

        locale = self.env['res.lang']._lang_get(self.env.user.lang)._odoo_lang_to_spreadsheet_locale()
        sheets = []
        for document in self.document_ids:
            doc_table, checkbox_indices = self._compute_spreadsheet_table_for_doc(document_id=document.id, sign_requests=sign_requests)
            if not doc_table:
                continue

            number_of_columns = len(doc_table)
            number_of_rows = len(doc_table[0]) if number_of_columns > 0 else 0

            cells = {}
            for col_idx, column in enumerate(doc_table):
                for row_idx, cell_data in enumerate(column):
                    cell_key = to_cell_reference(col_idx, row_idx)
                    raw_value = cell_data.get('value', '')
                    cells[cell_key] = str(raw_value) if raw_value not in (False, None) else ""

            validation_rules = []
            if checkbox_indices and number_of_rows > 1:
                for idx, col_index in enumerate(checkbox_indices):
                    start_ref = to_cell_reference(col_index, 1)
                    end_ref = to_cell_reference(col_index, number_of_rows - 1)
                    validation_rules.append({
                        "id": f"checkbox_rule_{document.id}_{idx}",
                        "criterion": {"type": "isBoolean", "values": []},
                        "ranges": [f"{start_ref}:{end_ref}"]
                    })

            last_cell_ref = to_cell_reference(max(0, number_of_columns - 1), 0)
            style_range = f"A1:{last_cell_ref}" if number_of_columns > 0 else "A1"

            sheets.append({
                'id': f'sheet_{document.id}',
                'name': f"{document.name} (#{document.id})",
                'cols': {str(i): {'size': DEFAULT_COLUMN_WIDTH} for i in range(number_of_columns)},
                'colNumber': max(MIN_COLUMNS, number_of_columns),
                'rowNumber': max(MIN_ROWS, number_of_rows),
                'cells': cells,
                'dataValidationRules': validation_rules,
                'styles': {
                    style_range: 1
                },
                'panes': {
                    'ySplit': 1,
                    'xSplit': 0
                }
            })

        return {
            'version': '18.4.2',
            'sheets': sheets,
            'settings': {
                'locale': locale,
            },
            'styles': {
                '1': {'bold': True}
            },
            'revisionId': 'START_REVISION',
        }

    def _format_sign_value(self, item, value):
        """ Format the raw input value into a human-readable string.

        This method handles type-specific formatting, such as converting checkbox states
        to boolean strings, signatures to a static 'Signed' label, and selection IDs
        to their display labels.

        :param recordset item: The 'sign.item' record associated with the value.
        :param str|bool value: The raw value stored in the database.
        :return: The formatted string suitable for display.
        :rtype: str
        """
        if item.type_id.item_type == "checkbox":
            if (not value or
                isinstance(value, str) and value.lower() == "off"):
                return "FALSE"
            return "TRUE"
        if not value:
            return ""
        itype = item.type_id.item_type
        if itype in ("signature", "stamp"):
            return self.env._("Signed")
        if itype == "selection":
            selected_option = item.option_ids.filtered(lambda o: o.id == int(value))
            return selected_option.value if selected_option else ""
        return value

    def _get_sign_answers_folder_sudo(self):
        """ Retrieve or create the 'Sign Request Answers' folder in Documents.

        This method checks the system parameter 'sign.spreadsheet_answers_folder_id'
        for an existing folder. If missing or deleted, it creates a new folder
        under the Sign root and updates the parameter. It also unarchives the
        folder if it exists but was archived.

        :return: The recordset of the documents folder (sudo).
        :rtype: recordset
        """
        folder_id = self.env["ir.config_parameter"].sudo().get_int('sign.spreadsheet_answers_folder_id')
        folder_sudo = self.env["documents.document"].sudo().browse(folder_id).exists()

        if not folder_sudo:
            sign_root = self.env.ref('documents_sign.document_sign_folder', raise_if_not_found=False)
            folder_sudo = self.env["documents.document"].sudo().create({
                'name': self.env._('Sign Request Answers'),
                'type': 'folder',
                'folder_id': sign_root.id if sign_root else False,
                'access_internal': 'view',
            })
            self.env["ir.config_parameter"].sudo().set_int('sign.spreadsheet_answers_folder_id', folder_sudo.id)

        elif not folder_sudo.active:
            folder_sudo.action_unarchive()

        return folder_sudo
