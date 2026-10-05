import { fields, models } from "@web/../tests/web_test_helpers";

export class Fake extends models.Model {
    _name = "fake";

    phone = fields.Char({ string: "Phone Number" });
    phone_sanitized = fields.Char({ string: "Sanitized Phone Number" });
    phone_formatted = fields.Char({ string: "Formatted Phone Number" });
    mobile = fields.Char({ string: "Mobile Number" });
    mobile_sanitized = fields.Char({ string: "Sanitized Mobile Number" });
    mobile_formatted = fields.Char({ string: "Formatted Mobile Number" });
}
