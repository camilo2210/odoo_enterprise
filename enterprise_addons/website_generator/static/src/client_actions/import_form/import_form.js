import { Component, onWillStart, proxy, t, useProps } from "@odoo/owl";
import { useDebounced } from "@web/core/utils/timing";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { documentationUrl } from "@web/core/utils/urls";

export class WebsiteGeneratorForm extends Component {
    static template = "website_generator.WebsiteGeneratorActionWrapper";

    props = useProps({
        action: t.any().optional(),
        importBlogs: t.any().optional(),
        importProducts: t.any().optional(),
        websiteId: t.any().optional(),
    });

    setup() {
        this.state = proxy({
            importWebsite: this.props.action?.context?.importWebsite ?? false,
            importProducts: this.props.importProducts ?? false,
            websites: [],
            ecommercePlatform: "auto",
            submitted: false,
            targetUrl: "",
            submitting: false,
            isValidatingUrl: false,
            searchingUrlApi: false,
            isValidUrl: false,
            showUrlVerificationIcon: false,
            showAPISearchingIcon: false,
            checkedUrlApi: false,
            websiteId: this.props.websiteId,
            showSuccessTitle: this.props.action?.context?.showSuccessTitle ?? false,
            importBlogs: this.props.importBlogs ?? false,
            blogPlatform: "",
            productAPIConnectedDate: "",
            blogAPIConnectedDate: "",
            showAPIKeyValidatingIcon: false,
            validatingApiKey: false,
            isValidAPIKey: false,
        });

        this.notification = useService("notification");
        this.orm = useService("orm");
        this.debouncedCheckUrl = useDebounced(this.checkUrl.bind(this), 800);
        // checkUrlApi does not need a long timer for the debounce because:
        //  1. It comes after debouncedCheckUrl when url input is changed so it's already done the waiting
        //  2. The other time it is activated is just by toggling importProducts or importBlogs which should be faster IMO.
        this.debouncedCheckUrlApi = useDebounced(this.checkUrlApi.bind(this), 100);

        onWillStart(async () => {
            const websites = await this.orm.searchRead("website", [], ["id", "name"]);
            this.state.websites = websites;
        });
    }

    get importWebsiteDocumentationUrl() {
        return documentationUrl(
            "/applications/websites/website/website_creation.html#import-an-existing-website"
        );
    }

    async checkUrl() {
        // If the user hasn't changed the URL, no need to reverify.
        if (this.state.showUrlVerificationIcon) {
            return this.state.isValidUrl;
        }

        if (!this.state.targetUrl) {
            this.state.showUrlVerificationIcon = false;
            this.state.isValidUrl = false;
            return this.state.isValidUrl;
        }

        this.state.isValidatingUrl = true;
        this.state.showUrlVerificationIcon = true;
        let result;
        try {
            result = await this.orm.call("website", "url_check", [this.state.targetUrl], {});
            if (result.status === "success") {
                this.state.isValidatingUrl = false;
                this.state.isValidUrl = true;
                return true;
            }
            this._handleCheckUrlErrorMessages(result.status);
        } finally {
            if (!result) {
                this.notification.add("Something went wrong.", {
                    title: _t("Error"),
                });
            }
        }
        this.state.isValidatingUrl = false;
        this.state.isValidUrl = false;
        return false;
    }

    async onUrlInput(ev) {
        this.state.targetUrl = ev.target.value ? ev.target.value.trim() : "";
        this.state.showUrlVerificationIcon = false;
        this.state.isValidUrl = false;
        this.state.showAPISearchingIcon = false;
        this.state.ecommercePlatform = "auto";
        this.state.blogPlatform = "";
        await this.debouncedCheckUrl();
        await this.debouncedCheckUrlApi();
    }

    async onConfigurationChange(ev) {
        await this.debouncedCheckUrlApi();
    }

    onApiKeyInput(ev) {
        this.state.showAPIKeyValidatingIcon = false;
    }

    async checkUrlApi() {
        if (!this.state.isValidUrl) {
            return false;
        }
        if (!this.state.importProducts && !this.state.importBlogs) {
            return true;
        }
        // If the user hasn't changed the URL, no need to reverify.
        if (this.state.showAPISearchingIcon) {
            return this.state.checkedUrlApi;
        }

        this.state.searchingUrlApi = true;
        this.state.showAPISearchingIcon = true;
        this.state.checkedUrlApi = false;
        let result;
        try {
            result = await this.orm.call("website", "url_check_api", [this.state.targetUrl], {});
            if (result.status === "success") {
                this.state.ecommercePlatform = result.ecommerce_platform;
                this.state.blogPlatform = result.blog_platform;
                if (["woocommerce", "prestashop"].includes(this.state.ecommercePlatform)) {
                    this.state.productAPIConnectedDate = await this.hasAPISetup(
                        this.state.ecommercePlatform,
                        false
                    );
                }
                if (this.state.blogPlatform === "ghost") {
                    this.state.blogAPIConnectedDate = await this.hasAPISetup("ghost", false);
                }
                this.state.searchingUrlApi = false;
                this.state.checkedUrlApi = true;
                return true;
            } else {
                this._handleCheckUrlErrorMessages(result.status);
            }
        } finally {
            if (!result) {
                this.notification.add("Something went wrong.", {
                    title: _t("Error"),
                });
            }
        }
        this.state.searchingUrlApi = false;
        return false;
    }

    _handleCheckUrlErrorMessages(status) {
        switch (status) {
            case "empty_url":
                this.notification.add("Please add your URL and try again.", {
                    title: _t("The provided URL is empty"),
                    type: "danger",
                });
                break;
            case "error_invalid_url":
                this.notification.add("Please check your URL and try again.", {
                    title: _t("The provided URL is not reachable"),
                    type: "danger",
                });
                break;
            case "error_banned_url":
                this.notification.add("We can't process your request.", {
                    title: _t("The provided URL is not allowed"),
                    type: "danger",
                });
                break;
            case "error_allowed_request_exhausted":
                this.notification.add(
                    "You have exceeded the number of requests, try again later.",
                    {
                        title: _t("Too many requests"),
                        type: "danger",
                    }
                );
                break;
            case "error_url_redirection":
                this.notification.add(
                    "The requested URL redirected to another URL, try again with the final URL.",
                    {
                        title: _t("URL redirection"),
                        type: "danger",
                    }
                );
                break;
            default:
                this.notification.add("Something went wrong.", {
                    title: _t("Error"),
                });
                break;
        }
    }

    async makeWebsiteGeneratorRequest(ev) {
        ev.preventDefault();
        // We have to get the form data before disabling inputs.
        const formData = new FormData(ev.currentTarget);
        const data = Object.fromEntries(formData.entries());

        // Prevent multiple submissions
        if (this.state.submitting) {
            return;
        }
        this.state.submitting = true;
        // We must always have at least import products or import website as true. If neither, we cannot submit.
        if (!data["import_products"] && !data["import_website"]) {
            if (!data["import_blogs"]) {
                this.notification.add(
                    _t(
                        "Please select at least one option: Import Website, Import Products or Import Blogs."
                    )
                );
                this.state.submitting = false;
                return;
            } else if (!this.state.blogPlatform) {
                this.notification.add(
                    _t(
                        "No blog platform detected. Please select at least Import Website or Import Products to continue."
                    )
                );
                this.state.submitting = false;
                return;
            }
        }

        if (!(await this.checkUrl())) {
            this.notification.add(_t("Please make sure the URL is correct and try again."), {
                title: _t("URL unreachable"),
            });
            this.state.submitting = false;
            return;
        }

        if (!(await this.checkUrlApi())) {
            this.notification.add(_t("Please wait for the API check to finish."), {
                title: _t("API Check failed"),
            });
            this.state.submitting = false;
            return;
        }

        if (data["import_products"] && this.state.ecommercePlatform == "woocommerce") {
            this.state.productAPIConnectedDate = await this.hasAPISetup("woocommerce", true);
            if (!this.state.productAPIConnectedDate) {
                this.state.submitting = false;
                return;
            }
        }

        if (data["import_products"] && this.state.ecommercePlatform == "prestashop") {
            if (data["prestashop_api_key"]) {
                this.state.showAPIKeyValidatingIcon = true;
                this.state.validatingApiKey = true;
                const submitted_key_response = await this.orm.call(
                    "website_generator.request",
                    "apply_api_key",
                    [],
                    {
                        platform: "prestashop",
                        consumer_key: data["prestashop_api_key"],
                        validate: true,
                        target_url: this.state.targetUrl,
                    }
                );
                this.state.validatingApiKey = false;
                this.state.isValidAPIKey = submitted_key_response.status === "success";
                if (!this.state.isValidAPIKey) {
                    this.notification.add(
                        _t(
                            "Something went wrong applying your API key. Please check your API key and try again."
                        )
                    );
                    this.state.submitting = false;
                    return;
                }
            }
            this.state.productAPIConnectedDate = await this.hasAPISetup("prestashop", true);
            if (!this.state.productAPIConnectedDate) {
                this.state.submitting = false;
                return;
            }
        }
        delete data.prestashop_api_key;

        if (data["import_blogs"] && this.state.blogPlatform == "ghost") {
            if (data["ghost_api_key"]) {
                this.state.showAPIKeyValidatingIcon = true;
                this.state.validatingApiKey = true;
                const submitted_key_response = await this.orm.call(
                    "website_generator.request",
                    "apply_api_key",
                    [],
                    {
                        platform: "ghost",
                        consumer_key: data["ghost_api_key"],
                        validate: true,
                        target_url: this.state.targetUrl,
                    }
                );
                this.state.validatingApiKey = false;
                this.state.isValidAPIKey = submitted_key_response.status === "success";
                if (!this.state.isValidAPIKey) {
                    this.notification.add(
                        _t(
                            "Something went wrong applying your API key. Please check your API key and try again."
                        )
                    );
                }
            }
            this.state.blogAPIConnectedDate = await this.hasAPISetup("ghost", true);
            if (!this.state.blogAPIConnectedDate) {
                this.state.submitting = false;
                return;
            }
        }
        delete data.ghost_api_key;

        // Wait 500 seconds to show that the URL was verified successfully
        await new Promise((resolve) => setTimeout(resolve, 500));

        let result;
        try {
            if (this.state.websiteId) {
                data.website_id = this.state.websiteId;
            }
            if (data["import_products"]) {
                data.ecommerce_platform = this.state.ecommercePlatform;
            }
            if (data["import_blogs"]) {
                data.blog_platform = this.state.blogPlatform;
            }
            result = await this.orm.call("website", "import_website", [], data);
        } catch (error) {
            if (error?.data?.name === "odoo.exceptions.UserError") {
                throw error;
            }
            console.error("Error starting the import_website:", error);
        }

        if (result) {
            this.state.submitted = true;
            this.onSubmitted();
        } else {
            this.notification.add(result, {
                title: _t("Something went wrong while importing your website"),
            });
        }
        this.state.submitting = false;
    }

    // Hook on form submission (used in website configurator)
    onSubmitted() {}

    async hasAPISetup(platform, show_message) {
        let api_setup;
        let setup_date = "";
        try {
            api_setup = await this.orm.call(
                "website_generator.request",
                "has_api_setup",
                [platform],
                {}
            );
        } catch (error) {
            console.error("API check failed for", platform, ":", error);
        }
        let error_msg = "";
        if (!api_setup || api_setup.status == "no_api_key_found") {
            if (platform === "woocommerce") {
                error_msg = _t(
                    "You must authenticate the WooCommerce API before trying to import WooCommerce Products."
                );
            } else if (platform === "ghost") {
                error_msg = _t("You must add a Ghost API key before trying to import Ghost Blogs.");
            } else if (platform === "prestashop") {
                error_msg = _t(
                    "You must add a PrestaShop API key before trying to import PrestaShop products."
                );
            }
        } else if (api_setup.status === "error_api_key") {
            error_msg = _t(
                "API key has either expired, is invalid or there is no content to extract. Please provide a new API key."
            );
        }
        if (error_msg && show_message) {
            this.notification.add(error_msg, {
                title: _t("API authentication not setup"),
            });
        }
        if (api_setup?.status == "success") {
            setup_date = api_setup.create_date;
        }
        return setup_date;
    }

    async createWooCommerceLink() {
        if (!this.state.targetUrl) {
            return null;
        }
        if (!this.db_data) {
            this.db_data = await this.orm.call(
                "website_generator.request",
                "get_system_parameters",
                [],
                {}
            );
        }
        const [dbUuid, dbUrl, wsEndpoint] = this.db_data;
        const callbackUrl = new URL("/website_scraper/connect_woocommerce_api", wsEndpoint).href;
        const params = {
            app_name: "Odoo Website Import Tool",
            scope: "read",
            user_id: dbUuid,
            return_url: dbUrl,
            callback_url: callbackUrl,
        };
        const endpoint = "/wc-auth/v1/authorize";
        const baseUrl = new URL(endpoint, this.state.targetUrl);
        const queryString = new URLSearchParams(params).toString();
        return `${baseUrl}?${queryString}`;
    }

    async handleConnectClick(ev) {
        ev.preventDefault();
        const url = await this.createWooCommerceLink();

        if (url) {
            window.open(url, "_blank");
        } else {
            this.notification.add(_t("Make sure that you have set the website URL first."), {
                title: _t("Could not generate WooCommerce URL"),
            });
        }
    }
}

registry.category("actions").add("website_generator.action_open_form", WebsiteGeneratorForm);
