import { fields, models } from "@web/../tests/web_test_helpers";

export class StockMove extends models.Model {
    _name = "stock.move";
    uom_id = fields.Many2one({ relation: "uom.uom" });
    _records = [
        {
            id: 1,
            uom_id: 4,
        },
    ];

    post_barcode_process() {
        return [];
    }
}
