import { location } from "@web/core/browser/browser";
import { router } from "@web/core/browser/router";
import { patch } from "@web/core/utils/patch";

/* if you guys at framework-js read this, we are sorry, bigram-request */
patch(router, {
    stateToUrl(state) {
        const url = super.stateToUrl(state);
        if (!state.access_token) {
            return url;
        }

        const parsedUrl = new URL(url, location.origin);
        if (!parsedUrl.pathname.endsWith(`/spreadsheet/${state.resId}`)) {
            return url;
        }

        parsedUrl.searchParams.delete("access_token");

        // The shared spreadsheet URL uses the access token instead of the record id.
        parsedUrl.pathname =
            `${parsedUrl.pathname.slice(0, parsedUrl.pathname.lastIndexOf("/"))}/` +
            encodeURIComponent(state.access_token);

        return `${parsedUrl.pathname}${parsedUrl.search}`;
    },

    urlToState(urlObj) {
        const pathParts = urlObj.pathname.split("/");
        if (pathParts.at(-2) !== "spreadsheet") {
            return super.urlToState(urlObj);
        }

        const token = decodeURIComponent(pathParts.at(-1));
        const separatorIndex = token.lastIndexOf("o"); // see _compute_access_token in documents_document.py
        const idHex = token.slice(separatorIndex + 1);
        const spreadsheetId = parseInt(idHex, 16);

        if (
            separatorIndex < 0 ||
            Number.isNaN(spreadsheetId) ||
            spreadsheetId.toString(16) !== idHex
        ) {
            return super.urlToState(urlObj);
        }

        const urlWithoutAccessToken = new URL(urlObj.href);
        urlWithoutAccessToken.pathname = [...pathParts.slice(0, -1), spreadsheetId].join("/");

        const state = super.urlToState(urlWithoutAccessToken);
        state.access_token = token;
        return state;
    },
});
