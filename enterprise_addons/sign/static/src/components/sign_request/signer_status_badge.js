import { Component, useProps, proxy, types as t } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class SignerStatusBadge extends Component {
    static template = "sign.SignerStatusBadgeTemplate";
    static components = { Dropdown };

    props = useProps({
        currentRequestItem: t.any().optional(),
        waitingSigners: t.array().optional(),
        canceledSigners: t.array().optional(),
        completedSigners: t.array().optional(),
        showResendButtons: t.boolean().optional(),
        sequencedSignatureMail: t.boolean().optional(),
        onResendClick: t.function().optional(),
    });

    setup() {
        this.uiService = useService("ui");
        this.state = proxy({ resentIds: new Set() });
    }

    async handleResend(signerId) {
        if (this.props.onResendClick) {
            await this.props.onResendClick(signerId);
            this.state.resentIds.add(signerId);
        }
    }

    // Collapse the signer badges into a dropdown past a couple of signers, or
    // always on small screens where there is no room to lay them out inline.
    // Only the other signers go in the dropdown content, so on small screens
    // stay inline when there are none rather than opening an empty sheet.
    get showDropdown() {
        return this.totalSigners > 2 || (this.uiService.isSmall && this.otherSignersCount > 0);
    }

    get otherSignersCount() {
        return (
            (this.props.waitingSigners?.length || 0) +
            (this.props.completedSigners?.length || 0) +
            (this.props.canceledSigners?.length || 0)
        );
    }

    get totalSigners() {
        return this.otherSignersCount + (this.props.currentRequestItem ? 1 : 0);
    }

    get signedCount() {
        let count = this.props.completedSigners?.length || 0;
        if (this.props.currentRequestItem?.state === "completed") {
            count++;
        }
        return count;
    }

    get waitingCount() {
        let count = this.props.waitingSigners?.length || 0;
        if (this.props.currentRequestItem?.state === "sent") {
            count++;
        }
        return count;
    }

    get canceledCount() {
        let count = this.props.canceledSigners?.length || 0;
        if (this.props.currentRequestItem?.state === "canceled") {
            count++;
        }
        return count;
    }

    get signersSummary() {
        if (this.signedCount > 0 && this.waitingCount === 0 && this.canceledCount === 0) {
            return _t("Fully signed");
        }

        const parts = [];
        if (this.signedCount > 0) {
            parts.push(`${this.signedCount} ${_t("signed")}`);
        }
        if (this.waitingCount > 0) {
            parts.push(`${this.waitingCount} ${_t("waiting")}`);
        }
        if (this.canceledCount > 0) {
            parts.push(`${this.canceledCount} ${_t("cancelled")}`);
        }
        return parts.join(", ");
    }
}

registry.category("public_components").add("sign.SignerStatusBadge", SignerStatusBadge);
