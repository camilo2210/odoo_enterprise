import { registry } from "@web/core/registry";

// `/my/documents` redirects internal users to the backend, which can't be
// displayed inside the website preview iframe: open it in the top window.
registry
    .category("isTopWindowURL")
    .add("documents.website_builder_action", ({ pathname }) => pathname === "/my/documents");
