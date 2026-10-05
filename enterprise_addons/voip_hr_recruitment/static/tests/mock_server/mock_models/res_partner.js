import { voipModels } from "@voip/../tests/voip_test_helpers";
import { fields } from "@web/../tests/web_test_helpers";

export class ResPartner extends voipModels.ResPartner {
    applicant_ids = fields.One2many({ relation: "hr.applicant", string: "Applicants" });

    _store_voip_fields(res) {
        super._store_voip_fields(res);
        res.many("applicant_ids", ["partner_id", "partner_name"]);
    }
}
