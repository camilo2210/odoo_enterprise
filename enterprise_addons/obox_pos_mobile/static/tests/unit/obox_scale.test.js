import { OboxScale } from "@obox_point_of_sale/app/utils/scale/obox_scale";
import { advanceTime, beforeEach, expect, mockFetch, test } from "@odoo/hoot";
import { allowTranslations } from "@web/../tests/web_test_helpers";
import mobile from "@web_mobile/js/services/core";
import { patch } from "@web/core/utils/patch";

const OWN_IP = "192.168.1.10";
const OWN_IP_CACHE_MS = 2000;

const makeScale = (localAddress) =>
    new OboxScale({
        config: {
            obox_scale_id: { identifier: "scale", obox_id: { local_address: localAddress } },
        },
    });

beforeEach(() => {
    allowTranslations();
    patch(mobile.methods, {
        getLocalIp: async () => ({ success: true, data: OWN_IP }),
    });
});

async function readUrl(scale) {
    let url;
    mockFetch((input) => {
        url = String(input);
        return { weight: 1 };
    });
    await scale._readWeight();
    await advanceTime(OWN_IP_CACHE_MS + 1);
    return url;
}

test("a scale on this device is read through loopback", async () => {
    expect(await readUrl(makeScale(`${OWN_IP}:4545`))).toBe(
        "http://127.0.0.1:4545/usb/v1/scale/read_scale_weight"
    );
});

test("a scale on another device keeps its address", async () => {
    expect(await readUrl(makeScale("192.168.1.20:4545"))).toBe(
        "http://192.168.1.20:4545/usb/v1/scale/read_scale_weight"
    );
});
