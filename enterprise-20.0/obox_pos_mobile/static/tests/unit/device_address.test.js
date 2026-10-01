import { resolveDeviceAddress } from "@obox_pos_mobile/app/utils/device_address";
import { advanceTime, beforeEach, expect, test } from "@odoo/hoot";
import { patch } from "@web/core/utils/patch";
import mobile from "@web_mobile/js/services/core";

const OWN_IP = "192.168.1.10";
const OWN_IP_CACHE_MS = 2000;

let nativeCalls;

const forgetCachedIp = () => advanceTime(OWN_IP_CACHE_MS + 1);

beforeEach(() => {
    nativeCalls = 0;
    patch(mobile.methods, {
        getLocalIp: async () => {
            nativeCalls++;
            return { success: true, data: OWN_IP };
        },
    });
});

test("the device's own ip becomes loopback", async () => {
    expect(await resolveDeviceAddress(OWN_IP)).toBe("127.0.0.1");
    await forgetCachedIp();
});

test("the port is kept", async () => {
    expect(await resolveDeviceAddress(`${OWN_IP}:4545`)).toBe("127.0.0.1:4545");
    await forgetCachedIp();
});

test("a full url keeps its scheme, port and path", async () => {
    expect(await resolveDeviceAddress(`http://${OWN_IP}:4545/usb/v1`)).toBe(
        "http://127.0.0.1:4545/usb/v1"
    );
    await forgetCachedIp();
});

test("another device's address is left alone", async () => {
    expect(await resolveDeviceAddress("192.168.1.20:4545")).toBe("192.168.1.20:4545");
    expect(await resolveDeviceAddress("192.168.1.100")).toBe("192.168.1.100");
    await forgetCachedIp();
});

test("setting up several devices asks the app once", async () => {
    await Promise.all([
        resolveDeviceAddress(OWN_IP),
        resolveDeviceAddress(`${OWN_IP}:4545`),
        resolveDeviceAddress("192.168.1.20"),
    ]);
    expect(nativeCalls).toBe(1);
    await forgetCachedIp();
});

test("the ip is asked again once the cache is forgotten", async () => {
    await resolveDeviceAddress(OWN_IP);
    await forgetCachedIp();
    await resolveDeviceAddress(OWN_IP);
    expect(nativeCalls).toBe(2);
    await forgetCachedIp();
});

test("outside the app the address is left alone", async () => {
    patch(mobile.methods, { getLocalIp: undefined });
    expect(await resolveDeviceAddress(`${OWN_IP}:4545`)).toBe(`${OWN_IP}:4545`);
    expect(nativeCalls).toBe(0);
});

test("a native failure leaves the address alone", async () => {
    patch(mobile.methods, {
        getLocalIp: async () => ({ success: false, data: "no network" }),
    });
    expect(await resolveDeviceAddress(OWN_IP)).toBe(OWN_IP);
    await forgetCachedIp();
});
