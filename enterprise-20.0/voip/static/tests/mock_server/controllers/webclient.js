import { registerStoreHandler } from "@mail/../tests/mock_server/store_handler";

import { makeKwArgs } from "@web/../tests/web_test_helpers";

// Mirrors the store handlers of `voip/controllers/webclient.py` (WebClient).

registerStoreHandler(
    "res.country",
    function store_get_res_country(store) {
        /** @type {import("mock_models").ResCountry} */
        const ResCountry = this.env["res.country"];
        store.add(
            ResCountry.browse(
                ResCountry.search([["phone_code", "!=", false]], makeKwArgs({ order: "name" }))
            ),
            "_store_voip_fields"
        );
    },
    { audience: "everyone" }
);
