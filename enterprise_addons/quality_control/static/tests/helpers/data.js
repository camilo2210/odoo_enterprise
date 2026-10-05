import { defineModels, fields, onRpc } from "@web/../tests/web_test_helpers";
import { SpreadsheetMixin } from "@spreadsheet/../tests/helpers/data";

class QualityCheckSpreadsheet extends SpreadsheetMixin {
    _name = "quality.check.spreadsheet";

    name = fields.Char();
    check_cell = fields.Char();

    _records = [
        {
            id: 1,
            name: "My quality check spreadsheet",
            spreadsheet_data: "{}",
            check_cell: "A1",
        },
        {
            id: 1111,
            name: "My quality check spreadsheet",
            spreadsheet_data: "{}",
            check_cell: "A1",
        },
    ];

}

onRpc(
    "/spreadsheet/data/<string:res_model>/<int:res_id>",
    function (_request, { res_model, res_id }) {
        const [record] = this.env[res_model].search_read([["id", "=", parseInt(res_id)]]);
        return {
            data: JSON.parse(record.spreadsheet_data),
            name: record.name,
            revisions: [],
            has_write_access: true,
            quality_check_display_name: "The check name",
            quality_check_cell: record.check_cell,
        };
    }
);

onRpc(
    "/spreadsheet/<string:res_model>/<int:res_id>/dispatch",
    function () {}
);

export function defineQualitySpreadsheetModels() {
    defineModels({
        QualityCheckSpreadsheet,
    });
}
