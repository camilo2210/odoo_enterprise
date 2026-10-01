import { ResPartner } from "@mail/core/common/res_partner_model";
import { fields } from "@mail/model/misc";

import { patch } from "@web/core/utils/patch";

patch(ResPartner.prototype, {
    setup() {
        super.setup();
        this.agent_ids = fields.Many("ai.agent", { inverse: "partner_id" });
    },
    get isBot() {
        return super.isBot || this.agent_ids?.length > 0;
    },
});
