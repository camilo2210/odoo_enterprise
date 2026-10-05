import { patch } from "@web/core/utils/patch";
import { hootPosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { fields, models } from "@web/../tests/web_test_helpers";

export class PlatformOrderProvider extends models.ServerModel {
    _name = "platform.order.provider";

    code = fields.Selection({
        selection: [
            ["none", "No Provider Set"],
            ["odoo_food", "Odoo Food"],
        ],
    });
    // `module_state` is a related field on `module_id` (comodel `ir.module.module`), which
    // isn't part of the mocked POS model set, so the server-fetched field definitions never
    // include it. Declare it locally so `model._fields` has it and `_order` can sort by it.
    module_state = fields.Selection({
        selection: [
            ["uninstalled", "Not Installed"],
            ["installed", "Installed"],
        ],
    });

    _load_pos_data_fields() {
        return ["id", "name", "code", "write_date", "valid_for_seconds"];
    }

    _records = [
        {
            id: 1,
            name: "Odoo Food",
            code: "odoo_food",
            write_date: "2025-09-17 09:00:00",
            valid_for_seconds: 3600,
            module_state: "installed",
        },
    ];
}
patch(hootPosModels, [...hootPosModels, PlatformOrderProvider]);
