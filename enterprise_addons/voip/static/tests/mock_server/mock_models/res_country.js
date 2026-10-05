import { ResCountry } from "@mail/../tests/mock_server/mock_models/res_country";

import { patch } from "@web/core/utils/patch";

patch(ResCountry.prototype, {
    _store_voip_fields(res) {
        res.extend(["code", "image_url", "name", "phone_code"]);
    },
});
