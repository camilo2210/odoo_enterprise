import { describe, expect, test } from "@odoo/hoot";
import { queryAllTexts } from "@odoo/hoot-dom";
import { contains, assignDialogTestEnv, mountWithCleanup } from "@web/../tests/web_test_helpers";

import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { CarrierSelectorDialog } from "@delivery_shipstation/components/shipstation_selection_dialog";

describe.current.tags("desktop");
defineMailModels();

const carriers = [
    {
        carrier_id: "se-123456",
        carrier_code: "ups",
        friendly_name: "UPS",
        packages: [],
        services: [
            {
                service_code: "ups_ground",
                name: "UPS Ground",
                domestic: true,
                is_multi_package_supported: true,
            },
            { service_code: "ups_next_day_air", name: "UPS Next Day Air", domestic: true },
        ],
    },
    {
        carrier_id: "se-654321",
        carrier_code: "usps",
        friendly_name: "USPS",
        packages: [],
        services: [
            {
                service_code: "usps_priority_mail",
                name: "USPS Priority Mail",
                domestic: true,
                is_return_supported: true,
            },
        ],
    },
];

async function mountCarrierSelectorDialog(props = {}) {
    await assignDialogTestEnv();
    await mountWithCleanup(CarrierSelectorDialog, {
        props: {
            carrier_record_id: 1,
            carriers,
            close: () => {},
            ...props,
        },
    });
}

const CARRIER_ROW = ".modal-body .border-end .cursor-pointer";
const SERVICE_CARD = ".modal-body .card";
const SAVE_BUTTON = ".modal-footer .btn-primary";

test("carriers are listed and their services are shown once selected", async () => {
    await mountCarrierSelectorDialog();

    expect(queryAllTexts(CARRIER_ROW)).toEqual(["UPS\nups", "USPS\nusps"]);
    // No carrier is selected yet, so no service can be picked.
    expect(SERVICE_CARD).toHaveCount(0);
    expect(SAVE_BUTTON).toHaveAttribute("disabled");

    await contains(`${CARRIER_ROW}:first`).click();
    expect(queryAllTexts(`${SERVICE_CARD} .fw-bold`)).toEqual(["UPS Ground", "UPS Next Day Air"]);
    // A carrier alone is not enough to save, a service is required.
    expect(SAVE_BUTTON).toHaveAttribute("disabled");

    await contains(`${SERVICE_CARD}:first input[type=radio]`).click();
    expect(SAVE_BUTTON).not.toHaveAttribute("disabled");

    // Switching carrier resets the service selection.
    await contains(`${CARRIER_ROW}:last`).click();
    expect(queryAllTexts(`${SERVICE_CARD} .fw-bold`)).toEqual(["USPS Priority Mail"]);
    expect(SAVE_BUTTON).toHaveAttribute("disabled");
});

test("the carrier and service already configured are preselected", async () => {
    await mountCarrierSelectorDialog({
        current_carrier_id: "se-654321",
        current_service_code: "usps_priority_mail",
    });

    expect(queryAllTexts(`${SERVICE_CARD} .fw-bold`)).toEqual(["USPS Priority Mail"]);
    expect(SAVE_BUTTON).not.toHaveAttribute("disabled");
});
