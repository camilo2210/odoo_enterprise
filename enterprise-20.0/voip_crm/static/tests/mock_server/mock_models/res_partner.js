import { ResPartner as MailResPartner } from "@voip/../tests/mock_server/mock_models/res_partner";

export class ResPartner extends MailResPartner {
    /** @override */
    _store_voip_fields(res) {
        super._store_voip_fields(res);
        res.attr("commercial_partner_opportunity_count");
    }
}
