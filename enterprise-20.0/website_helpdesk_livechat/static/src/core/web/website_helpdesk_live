import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export const websiteHelpdeskLivechatCoreWebService = {
    dependencies: ["mail.store"],
    /**
     * @param {import("@web/env").OdooEnv}
     * @param {Partial<import("services").Services>} services
     */
    start(env, services) {
        if (services["mail.store"].helpdesk_livechat_active) {
            registry
                .category("discuss.channel_commands")
                .add(
                    "ticket",
                    {
                        help: _t("Create a new helpdesk ticket (/ticket ticket title)"),
                        methodName: "execute_command_helpdesk",
                        condition: ({ store }) => store.has_access_livechat,
                    },
                    { force: true }
                )
                .add(
                    "search_tickets",
                    {
                        force: true,
                        help: _t("Search helpdesk tickets (/search_tickets keyword)"),
                        methodName: "execute_command_helpdesk_search",
                        condition: ({ store }) => store.has_access_livechat,
                    },
                    { force: true }
                );
        } else {
            registry.category("discuss.channel_commands").remove("ticket");
            registry.category("discuss.channel_commands").remove("search_tickets");
        }
    },
};

registry
    .category("services")
    .add("website_helpdesk_livechat_core_web", websiteHelpdeskLivechatCoreWebService);
