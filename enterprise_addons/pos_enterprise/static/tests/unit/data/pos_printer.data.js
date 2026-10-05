import { models } from "@web/../tests/web_test_helpers";

export class PosPrinter extends models.ServerModel {
    _name = "pos.printer";

    _load_pos_preparation_data_fields() {
        return ["product_categories_ids", "printer_ip", "use_lna"];
    }
}
