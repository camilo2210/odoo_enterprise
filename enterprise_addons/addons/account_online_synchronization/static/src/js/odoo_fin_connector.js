import { markup, usePlugin } from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { cookie } from "@web/core/browser/cookie";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";
import { ORM } from "@web/core/orm_plugin";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
/* global OdooFin */

const PROXY_MODE_REGEX = /^[a-z0-9-_]+$/;
const RUNBOT_REGEX = /^https:\/\/[a-z0-9-_]+\.[a-z0-9-_]+\.odoo\.com$/;

export function OdooFinConnector(env, action) {
    const orm = usePlugin(ORM);
    const currency = useService("currency");
    const actionService = useService("action");
    const notificationService = useService("notification");
    const debugMode = usePlugin(DebugModePlugin).toString();

    const actionParams = action.params;
    const proxyMode = actionParams.proxyMode;

    const id = action.id;
    action.params.colorScheme = cookie.get("color_scheme");
    let mode = actionParams.mode || "link";
    // Ensure that the proxyMode is valid
    if (!PROXY_MODE_REGEX.test(proxyMode) && !RUNBOT_REGEX.test(proxyMode)) {
        return;
    }

    let url = `https://${proxyMode}.odoofin.com/proxy/v1/odoofin_link`;
    if (RUNBOT_REGEX.test(proxyMode)) {
        url = `${proxyMode}/proxy/v1/odoofin_link`;
    }

    let actionResult = false;
    loadJS(url).then(function () {
        // Create and open the iframe
        const params = {
            data: actionParams,
            proxyMode: proxyMode,
            onEvent: async function (event, data) {
                switch (event) {
                    case "close":
                        return;
                    case "reload":
                        return actionService.doAction({ type: "ir.actions.client", tag: "reload" });
                    case "notification":
                        notificationService.add(data.message, data);
                        break;
                    case "exchange_token":
                        await orm.call("account.online.link", "exchange_token", [[id], data], {
                            context: action.context,
                        });
                        break;
                    case "success":
                        mode = data.mode || mode;
                        actionResult = await orm.call(
                            "account.online.link",
                            "success",
                            [[id], mode, data],
                            { context: action.context }
                        );
                        actionResult.help = markup(actionResult.help);
                        // Reload the currency otherwise in might not be in the session for the getCurrency
                        await currency.reloadCurrencies();
                        return actionService.doAction(actionResult);
                    case "connect_existing_account":
                        actionResult = await orm.call(
                            "account.online.link",
                            "connect_existing_account",
                            [data],
                            { context: action.context }
                        );
                        actionResult.help = markup(actionResult.help);
                        // Reload the currency otherwise in might not be in the session for the getCurrency
                        await currency.reloadCurrencies();
                        return actionService.doAction(actionResult);
                    default:
                        return;
                }
            },
            onAddBank: async function (data) {
                return await actionService.doActionButton({
                    type: "object",
                    resModel: "account.online.link",
                    name: "action_create_manual_bank_account",
                    resId: id,
                    args: JSON.stringify([data]),
                });
            },
        };
        // propagate parent debug mode to iframe
        if (typeof debugMode !== "undefined" && debugMode) {
            params.data["debug"] = debugMode;
        }
        OdooFin.create(params);
        OdooFin.open();
    });
}

registry.category("actions").add("odoo_fin_connector", OdooFinConnector);
