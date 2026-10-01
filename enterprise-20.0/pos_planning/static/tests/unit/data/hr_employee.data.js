import { patch } from "@web/core/utils/patch";
import { HrEmployee } from "@pos_hr/../tests/unit/data/hr_employee.data";

patch(HrEmployee.prototype, {
    _load_pos_data_fields() {
        return [...super._load_pos_data_fields(), "resource_id"];
    },
});

HrEmployee._records.find((record) => record.id === 2).resource_id = false;
HrEmployee._records.find((record) => record.id === 3).resource_id = 1;
