import { OboxScale } from "@obox_point_of_sale/app/utils/scale/obox_scale";
import { beforeEach, expect, mockFetch, test } from "@odoo/hoot";
import { allowTranslations } from "@web/../tests/web_test_helpers";

beforeEach(allowTranslations);

const MOCK_IP = "192.168.1.100";
const MOCK_IDENTIFIER = "scale_abc123";

const makePos = (scaleDevice = null) => ({ config: { obox_scale_id: scaleDevice } });
const makeDevice = (overrides = {}) => ({
    identifier: MOCK_IDENTIFIER,
    obox_id: { local_ip: MOCK_IP },
    ...overrides,
});
const makeScale = (device = makeDevice()) => new OboxScale(makePos(device));

test("connectToScale returns true when scale device is configured", () => {
    expect(makeScale().connectToScale()).toBe(true);
});

test("connectToScale returns false when no scale device", () => {
    expect(makeScale(null).connectToScale()).toBe(false);
});

test("address uses obox local_ip", () => {
    expect(makeScale().address).toBe(`http://${MOCK_IP}`);
});

test("_readWeight returns weight value on success", async () => {
    mockFetch(() => ({ weight: 1.5 }));
    expect(await makeScale()._readWeight()).toBe(1.5);
});

test("_readWeight throws wrapped error on fetch failure", async () => {
    mockFetch(() => {
        throw new Error("Network error");
    });
    await expect(makeScale()._readWeight()).rejects.toThrow("Cannot weigh product");
});

test("_readWeight throws API error message when result is falsy", async () => {
    mockFetch(() => ({ error: "Scale not ready" }));
    await expect(makeScale()._readWeight()).rejects.toThrow("Scale not ready");
});

test("_readWeight falls back to JSON.stringify when no error field", async () => {
    mockFetch(() => ({ status: "timeout" }));
    await expect(makeScale()._readWeight()).rejects.toThrow('{"status":"timeout"}');
});

test("_readWeight sends correct identifier in request body", async () => {
    let capturedBody;
    mockFetch((_input, init) => {
        capturedBody = JSON.parse(init.body);
        return { weight: 0.5 };
    });
    await makeScale()._readWeight();
    expect(capturedBody.identifier).toBe(MOCK_IDENTIFIER);
});

test("_readWeight posts to correct endpoint URL", async () => {
    let capturedUrl;
    mockFetch((input) => {
        capturedUrl = input;
        return { weight: 0.5 };
    });
    await makeScale()._readWeight();
    expect(capturedUrl).toBe(`http://${MOCK_IP}/usb/v1/scale/read_scale_weight`);
});
