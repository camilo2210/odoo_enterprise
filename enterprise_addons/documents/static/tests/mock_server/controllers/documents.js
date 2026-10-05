import { registerRoute } from "@mail/../tests/mock_server/mail_mock_server";

// Mirrors the routes of `documents/controllers/documents.py`.

registerRoute("/documents/touch/<access_token>", documents_touch);
/** @type {import("@mail/../tests/mock_server/mail_mock_server").RouteCallback} */
function documents_touch() {
    return {};
}
