import mobile from "@web_mobile/js/services/core";

export class NativeError extends Error {
    constructor(method, payload) {
        const detail = payload?.error ?? payload?.data ?? payload;
        const message = typeof detail === "string" ? detail : detail?.message || `${method} failed`;
        super(message);
        this.name = "NativeError";
        this.method = method;
        this.code = detail?.name ?? detail?.code ?? null;
        this.payload = payload;
    }
}

export function hasMobileNative(method) {
    return typeof mobile.methods[method] === "function";
}

export function mobileNativeCall(method, args = {}) {
    const fn = mobile.methods[method];
    if (!fn) {
        return Promise.reject(new NativeError(method, "not available in this app"));
    }
    return fn(args).then((result) => {
        if (!result || result.success === false) {
            throw new NativeError(method, result);
        }
        return result.data;
    });
}

export const mobileNative = new Proxy(Object.create(null), {
    get: (_, method) => (args) => mobileNativeCall(method, args),
});
