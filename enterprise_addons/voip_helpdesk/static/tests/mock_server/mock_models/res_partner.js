import { ResPartner } from "@voip/../tests/mock_server/mock_models/res_partner";
import { patch } from "@web/core/utils/patch";

patch(ResPartner.prototype, {
    _store_voip_fields(res) {
        super._store_voip_fields(res);
        res.attr("commercial_partner_ticket_count");
    },
});
