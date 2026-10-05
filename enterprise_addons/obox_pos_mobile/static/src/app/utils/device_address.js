import { hasMobileNative, mobileNative } from "@pos_mobile_android/app/utils/native";
import { debounce } from "@web/core/utils/timing";

const LOOPBACK = "127.0.0.1";
const OWN_IP_CACHE_MS = 2000;
const ADDRESS_RE = /^(\w+:\/\/)?([^/:]+)(.*)$/;

let ownIp;
const forgetOwnIp = debounce(() => (ownIp = undefined), OWN_IP_CACHE_MS);

function getOwnIp() {
    if (ownIp === undefined) {
        ownIp = mobileNative.getLocalIp().catch(() => null);
    }
    forgetOwnIp();
    return ownIp;
}

export async function resolveDeviceAddress(address) {
    if (!address || !hasMobileNative("getLocalIp")) {
        return address;
    }
    const ip = await getOwnIp();
    const match = ip && address.match(ADDRESS_RE);
    if (!match || match[2] !== ip) {
        return address;
    }
    return `${match[1] ?? ""}${LOOPBACK}${match[3]}`;
}
