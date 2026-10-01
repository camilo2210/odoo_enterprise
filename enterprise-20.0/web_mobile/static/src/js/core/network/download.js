import { browser } from "@web/core/browser/browser";
import mobile from "@web_mobile/js/services/core";
import { download, downloadFile } from "@web/core/network/download";

function extractPathFromUrl(url) {
    const parsedUrl = URL.parse(url);
    return parsedUrl ? `${parsedUrl.pathname}${parsedUrl.search}` : url;
}

const _download = download._download;

download._download = async function (options) {
    if (mobile.methods.downloadFile) {
        if (odoo.csrf_token) {
            options.csrf_token = odoo.csrf_token;
        }

        options.url = extractPathFromUrl(options.url);

        mobile.methods.downloadFile(options);
        // There is no need to wait downloadFile because we delegate this to
        // Download Manager Service where error handling will be handled correclty.
        // On our side, we do not want to block the UI and consider the request
        // as success.
        return Promise.resolve();
    } else {
        return _download.apply(this, arguments);
    }
};

const _downloadFile = downloadFile._download;

downloadFile._download = async function (data, filename, mimetype) {
    if (!mobile.methods.downloadFile) {
        return _downloadFile.apply(this, arguments);
    }
    const isUrl = !filename && !mimetype && typeof data === "string";
    if (isUrl) {
        mobile.methods.downloadFile({
            form: { method: "GET" },
            url: extractPathFromUrl(data)
        });
    } else {
        browser.console.warn(
            "downloadFile: the native saveFile bridge only supports URL downloads; ignoring Blob/string content."
        );
    }
    return Promise.resolve();
};
