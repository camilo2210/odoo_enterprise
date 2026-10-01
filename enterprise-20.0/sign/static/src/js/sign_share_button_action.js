import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

async function copyShareLinkAndCloseWizard(env, action) {
    const notificationService = useService("notification");
    const shareLink = action.params.share_link;
    await browser.navigator.clipboard.writeText(shareLink);
    notificationService.add(_t("Share link copied to clipboard"), {
        type: "success",
    });
    return { type: "ir.actions.act_window_close" };
}

registry.category("actions").add("sign_share_and_close_action", copyShareLinkAndCloseWizard);
