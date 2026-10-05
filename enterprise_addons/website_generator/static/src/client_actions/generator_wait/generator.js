import { location } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { Component, onMounted, onWillStart, onWillUnmount, proxy, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { redirect } from "@web/core/utils/urls";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";

class WebsiteGenerator extends Component {
    static template = "website_generator.WebsiteGenerator";

    props = useProps(standardActionServiceProps);

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.website = useService("website");

        this.canCallGetResultWaitingRequests = true;
        this.state = proxy({
            error: "",
        });
        onWillStart(() => this._checkRequestStatus());
        // Every 10 seconds, we ask the server to call IAP to see if the
        // scraping result is ready.
        // If it is ready, the server will process the IAP file and generate the
        // website. Once it's done, a later call of this `setInterval` loop will
        // notice it (success or error status) and act accordingly.
        onMounted(() => {
            this._showWebsiteLoader();
            this.interval = setInterval(() => this._checkRequestStatus(), 10000);
        });
        onWillUnmount(() => clearInterval(this.interval));
    }

    async _checkRequestStatus() {
        // Get scraping request
        const [lastScrapRequest] = await this.orm.silent.searchRead(
            "website_generator.request",
            [],
            ["id", "status", "status_message", "website_id"],
            { limit: 1, order: "id DESC" }
        );
        // Safety check, return to backend if no request
        if (!lastScrapRequest) {
            redirect("/odoo");
            return;
        }
        // If no real error status but not yet ready, ask server to check for
        // results
        if (
            [
                "error_request_still_processing",
                "error_maintenance",
                "waiting",
                "ready_generate_site",
            ].includes(lastScrapRequest.status)
        ) {
            if (this.canCallGetResultWaitingRequests) {
                this.canCallGetResultWaitingRequests = false;
                this.lastGetResultWaitingRequests = this.orm
                    .call("website_generator.request", "cronless_call_server_and_generate_site", [
                        lastScrapRequest.id,
                    ])
                    .then(() => {
                        this.canCallGetResultWaitingRequests = true;
                    });
            }
            return;
        }
        // If it's in error, adapt screen message to show the error
        if (lastScrapRequest.status.includes("error")) {
            this.state.error = lastScrapRequest.status_message;
            clearInterval(this.interval);
            this.website.hideLoader({ completeRemainingProgress: false });
            return;
        }

        this.website.redirectOutFromLoader({
            redirectAction: () => {
                location.href = `/website/force/${lastScrapRequest.website_id[0]}`;
            },
        });
    }

    _showWebsiteLoader() {
        const loadingSteps = [
            {
                description: _t("Importing your colors and design."),
                flag: "colors",
            },
            {
                description: _t("Copying your text."),
                flag: "text",
            },
            {
                description: _t("Uploading your images."),
                flag: "images",
            },
            {
                description: _t("Adapting building blocks."),
                flag: "generic",
            },
        ];
        this.website.showLoader({
            title: _t("Your website, now customizable effortless."),
            loadingSteps,
            bottomMessageTemplate: "website_generator.request_website_loader_bottom_message",
            showProgressBar: false,
            showCloseButton: true,
        });
    }
}

registry.category("actions").add("website_generator", WebsiteGenerator);
