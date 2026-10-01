import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Client action that will open the authentication URL in new window
 * and refresh the view when the login is done.
 */
export async function SocialConnectAccount(env, actionDescr) {
    const params = actionDescr.params || {};
    if (!params.url || !params.url.startsWith("https://")) {
        return;
    }

    const action = useService("action");

    const width = 800;
    const height = 800;
    const multiScreenLeft = window.screenLeft !== undefined ? window.screenLeft : window.screenX;
    const multiScreenTop = window.screenTop !== undefined ? window.screenTop : window.screenY;
    const currentWidth = window.outerWidth || document.documentElement.clientWidth;
    const currentHeight = window.outerHeight || document.documentElement.clientHeight;
    const left = multiScreenLeft + (currentWidth - width) / 2;
    const top = multiScreenTop + (currentHeight - height) / 2;

    const w = window.open(
        params.url,
        _t("Connect Your Account"),
        `width=${width},height=${height},left=${left},top=${top},resizable=yes`
    );
    window.addEventListener(
        "message",
        (event) => {
            if (
                event.data?.name !== "social-authentication-done" ||
                window.origin !== event.origin ||
                event.source !== w
            ) {
                // The event can be sent only from the window we created,
                // and only on the same origin
                return;
            }
            w.close();

            action.doAction("soft_reload");
        },
        { once: true }
    );
    return params.next_action;
}

registry.category("actions").add("social.ConnectAccount", SocialConnectAccount);
