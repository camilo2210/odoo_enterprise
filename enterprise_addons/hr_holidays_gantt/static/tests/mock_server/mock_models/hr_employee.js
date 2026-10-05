import { hrModels } from "@hr/../tests/hr_test_helpers";
import { fields } from "@web/../tests/web_test_helpers";

export class HrEmployee extends hrModels.HrEmployee {
    _name = "hr.employee";

    avatar_leave_summary = fields.Json();
    
    _store_avatar_card_fields(res) {
        super._store_avatar_card_fields(res);
        res.attr("avatar_leave_summary");
    }
}
