import { hasMobileNative, mobileNative } from "@pos_mobile_android/app/utils/native";
import { isPrivateIp } from "@point_of_sale/utils";

/**
 * Local Network Access from the app. The WebView cannot reach the local
 * network itself, so the requests that declare a targetAddressSpace are
 * performed by the app.
 */
export async function mobileLnaFetch(input, init = {}) {
    const request = new Request(input, {
        method: init.method,
        headers: init.headers,
        body: init.body,
        signal: init.signal,
    });
    const headers = {};
    request.headers.forEach((value, key) => (headers[key] = value));
    const body = init.body == null ? null : await request.text();
    if (body && !headers["content-type"]) {
        headers["content-type"] = "text/xml; charset=utf-8";
    }
    const reply = await mobileNative.lnaFetch({
        url: request.url,
        params: {
            method: request.method,
            headers,
            body,
            "no-cors": init.mode === "no-cors",
        },
    });
    if (!reply?.status) {
        throw new TypeError(reply?.message || "native request failed");
    }
    return new Response(reply.body || "", { status: reply.status, headers: reply.headers || {} });
}

function isLocalNetworkRequest(input, init) {
    if (!init?.targetAddressSpace) {
        return false;
    }
    try {
        return isPrivateIp(new URL(input instanceof Request ? input.url : input).hostname);
    } catch {
        return false;
    }
}

if (hasMobileNative("lnaFetch")) {
    const browserFetch = window.fetch.bind(window);
    window.fetch = (input, init) =>
        isLocalNetworkRequest(input, init)
            ? mobileLnaFetch(input, init)
            : browserFetch(input, init);

    const query = navigator.permissions?.query?.bind(navigator.permissions);
    if (query) {
        navigator.permissions.query = (descriptor) =>
            descriptor?.name === "local-network-access"
                ? Promise.resolve(
                      Object.assign(new EventTarget(), { state: "granted", onchange: null })
                  )
                : query(descriptor);
    }
}
