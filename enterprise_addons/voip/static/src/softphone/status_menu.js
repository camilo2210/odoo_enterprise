import { Component, onWillStart, proxy, status, t, useOnChange, useProps } from "@odoo/owl";

import { DeviceSelect as MailDeviceSelect } from "@mail/discuss/call/common/device_select";

import { FOREVER } from "@voip/core/common/res_users_settings_model_patch";

import { CopyButton } from "@web/core/copy_button/copy_button";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

class DeviceSelect extends MailDeviceSelect {
    CLICK_TO_ACTIVATE = _t("Click to Enable");

    setup() {
        this.settingName = useProps.static("settingName", t.string().optional());
        super.setup();
    }

    isSelected(id) {
        if (!this.settingName) {
            return super.isSelected(id);
        }
        if (id === undefined) {
            id = "";
        }
        return (
            this.store.settings[this.settingName] === id ||
            (this.isBrowserChrome &&
                this.store.settings[this.settingName] === "" &&
                id === "default")
        );
    }

    onSelectAudioDevice(ev, { device } = {}) {
        if (!this.settingName) {
            return super.onSelectAudioDevice(...arguments);
        }
        this.store.settings[this.settingName] = device?.deviceId ?? "";
    }
}

// Same icons as the matching node types in the flow editor (see
// @voip/flow_editor/node_types) so a destination reads the same way whether
// it's shown here or as a node in a call flow graph. "Call Flow" itself has
// no node type of its own (a flow isn't nested inside another flow), so it
// reuses "account_tree" (the flow editor's own icon set has no dedicated
// flowchart glyph either).
const SHARED_NUMBER_DESTINATION_INFO = {
    call_group: { icon: "group", iconClass: "oi-filled", label: _t("Group") },
    queue: { icon: "headphones", label: _t("Queue") },
    ivr: { icon: "format_list_numbered", label: _t("Menu") },
    call_flow: { icon: "account_tree", label: _t("Call Flow") },
};

export class StatusMenu extends Component {
    static components = { CopyButton, DeviceSelect, Dropdown, DropdownItem };
    static template = "voip.StatusMenu";

    props = useProps({
        callStatus: t.object().optional(),
        isUserVoipAdmin: t.boolean(),
        showAudioActivation: t.boolean(),
        showDeviceSelection: t.boolean(),
    });

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.store = useService("mail.store");
        this.voip = useService("voip");
        this.state = proxy({
            memberships: [],
            pendingAgentIds: new Set(),
            selectedCallerId: null,
        });
        this.dropdownState = useDropdownState();
        useOnChange(
            () => [this.isInCall],
            () => this.dropdownState.close(),
            { initialRun: false }
        );
        onWillStart(() => this.refreshMemberships());
    }

    /** local settings, holding the duration list */
    get settings() {
        return this.store.settings;
    }

    /** settings of the user, holding the do-not-disturb state */
    get userSettings() {
        return this.store.self_user.res_users_settings_id;
    }

    async refreshMemberships(notifyOnError = false) {
        if (!this.isOdooPhoneProduction) {
            return;
        }
        let memberships;
        try {
            memberships = await this.orm.call(
                "voip.queue.agent",
                "get_current_user_queue_memberships"
            );
        } catch {
            if (notifyOnError && status(this) !== "destroyed") {
                this.notification.add(_t("Could not refresh your queue memberships."), {
                    type: "danger",
                });
            }
            return;
        }
        if (status(this) !== "destroyed") {
            this.state.memberships = memberships;
        }
    }

    /** @returns {boolean} */
    get isOdooPhoneProduction() {
        return this.voip.config.usesOdooProvider && this.voip.config.mode === "prod";
    }

    /** @returns {boolean} */
    get isDemoMode() {
        return this.voip.config.mode === "demo";
    }

    /** @returns {boolean} */
    get isInCall() {
        return Boolean(this.props.callStatus);
    }

    /** @returns {boolean} */
    get showAudioSettings() {
        return this.props.showDeviceSelection;
    }

    showAudioPermissionDialog() {
        this.store.rtc.showMediaPermissionDialog(
            "microphone",
            this.voip.softphone.audioPermissionDialogConfiguration
        );
    }

    /** @returns {boolean} */
    get canBuyNumber() {
        return (
            this.props.isUserVoipAdmin &&
            !this.voip.config.didNumber &&
            (this.isOdooPhoneProduction || this.isDemoMode)
        );
    }

    /** @returns {boolean} */
    get canRequestNumber() {
        return (
            !this.props.isUserVoipAdmin &&
            !this.voip.config.didNumber &&
            (this.isOdooPhoneProduction || this.isDemoMode)
        );
    }

    /** @returns {boolean} */
    get isAvailable() {
        return !this.doNotDisturbUntilDt || this.doNotDisturbUntilDt <= luxon.DateTime.now();
    }

    /** @returns {boolean} */
    get isMutedForever() {
        return this.doNotDisturbUntilDt?.toMillis() === FOREVER.toMillis();
    }

    /** @returns {?luxon.DateTime} */
    get doNotDisturbUntilDt() {
        return this.userSettings.do_not_disturb_until_dt;
    }

    /** @returns {boolean} */
    get showsDoNotDisturbStatus() {
        return this.voip.phoneHeaderState === "available" && !this.isAvailable;
    }

    /** @returns {string} */
    get statusText() {
        if (this.showsDoNotDisturbStatus) {
            return _t("Do Not Disturb");
        }
        if (this.voip.phoneHeaderState === "no_number") {
            return this.isOdooPhoneProduction && this.voip.hasInternalCallingIdentity
                ? _t("Internal calls only")
                : _t("No number");
        }
        return (
            {
                available: _t("Available"),
                demo: _t("Demo Mode"),
                suspended: _t("Suspended"),
                unavailable: _t("Unavailable"),
                waiting: _t("Number under review"),
            }[this.voip.phoneHeaderState] || _t("Available")
        );
    }

    /** @returns {string} */
    get statusIcon() {
        if (this.showsDoNotDisturbStatus) {
            return "phone_disabled";
        }
        return (
            {
                available: "phone",
                demo: "phone",
                no_number: "phone",
                suspended: "warning",
                unavailable: "error",
                waiting: "schedule",
            }[this.voip.phoneHeaderState] || "phone"
        );
    }

    /** @returns {string} */
    get statusIconClass() {
        if (this.showsDoNotDisturbStatus) {
            return "text-danger";
        }
        return (
            {
                available: "text-success",
                demo: "text-400",
                no_number: "text-400",
                suspended: "text-warning",
                unavailable: "text-danger",
                waiting: "text-400",
            }[this.voip.phoneHeaderState] || "text-success"
        );
    }

    /** @returns {string} */
    get badgeTitle() {
        if (this.voip.microphoneError) {
            return this.voip.microphoneError;
        }
        if (this.voip.phoneHeaderState === "demo") {
            return this.voip.demoModeTooltip;
        }
        if (this.voip.phoneHeaderState !== "available") {
            return this.voip.didStatusTooltip || this.statusText;
        }
        if (this.isAvailable) {
            return _t("Available");
        }
        return this.isMutedForever
            ? _t("Do Not Disturb until I turn it off")
            : _t("Do Not Disturb until %(time)s", {
                  time: this.doNotDisturbUntilDt.toLocaleString(luxon.DateTime.DATETIME_MED),
              });
    }

    /** @returns {string} */
    get dndExpiryText() {
        if (this.isMutedForever) {
            return "";
        }
        return _t("Active until %(time)s", {
            time: this.doNotDisturbUntilDt.toLocaleString(luxon.DateTime.DATETIME_MED),
        });
    }

    /** @returns {boolean} */
    get hasLoggedQueue() {
        return this.state.memberships.some((membership) => membership.is_logged);
    }

    /** @returns {{ title: string, raw: string, formatted: string, statusBadge: ?string, isCallerId: boolean }[]} */
    get myNumbers() {
        const { config } = this.voip;
        const numbers = [];
        if (config.pbxExtensionNumber) {
            numbers.push({
                title: _t("Your extension"),
                raw: config.pbxExtensionNumber,
                formatted: config.pbxExtensionNumber,
                isSelectable: false,
                statusBadge: null,
                isCallerId: false,
            });
        }
        const outboundNumbers = config.outboundNumbers || [];
        const selectedCallerId = this.voip.callerIdNumbers.some(
            ({ number }) => number === this.state.selectedCallerId
        )
            ? this.state.selectedCallerId
            : this.voip.fallbackCallerId;
        for (const [index, outboundNumber] of outboundNumbers.entries()) {
            numbers.push({
                countryName: outboundNumber.countryName,
                flagUrl: outboundNumber.flagUrl,
                title:
                    index === 0
                        ? outboundNumbers.length === 1
                            ? _t("Your number")
                            : _t("Your numbers")
                        : "",
                raw: outboundNumber.number,
                formatted: outboundNumber.formatted,
                isSelectable: true,
                showAutoSelect: index === 0 && outboundNumbers.length > 1,
                statusBadge: null,
                isCallerId: selectedCallerId === outboundNumber.number,
            });
        }
        if (
            !config.outboundNumbers?.length &&
            config.mainNumber &&
            config.mainNumber === config.outboundCallerId
        ) {
            numbers.push({
                title: _t("%(company)s's default outgoing number", {
                    company: user.activeCompany.name,
                }),
                countryName: "",
                flagUrl: "",
                raw: config.mainNumber,
                formatted: config.mainNumberFormatted || config.mainNumber,
                isSelectable: false,
                statusBadge: null,
                isCallerId: Boolean(
                    config.outboundCallerId && config.outboundCallerId === config.mainNumber
                ),
            });
        }
        return numbers;
    }

    /** @returns {Object[]} Shared caller IDs available for manual selection. */
    get sharedNumbers() {
        return (this.voip.config.sharedOutboundNumbers || []).map((number) => ({
            ...number,
            raw: number.number,
            isCallerId:
                (this.state.selectedCallerId || this.voip.fallbackCallerId) === number.number,
        }));
    }

    /** @param {{ destinationType: string }} number @returns {string} */
    getSharedNumberIcon(number) {
        return SHARED_NUMBER_DESTINATION_INFO[number.destinationType]?.icon || "share";
    }

    /** @param {{ destinationType: string }} number @returns {string} */
    getSharedNumberIconClass(number) {
        return SHARED_NUMBER_DESTINATION_INFO[number.destinationType]?.iconClass || "";
    }

    /** @param {{ destinationType: string }} number @returns {string} */
    getSharedNumberLabel(number) {
        return SHARED_NUMBER_DESTINATION_INFO[number.destinationType]?.label || _t("Shared number");
    }

    selectCallerId(number) {
        this.voip.setFallbackCallerId(number);
        this.state.selectedCallerId = number;
    }

    toggleAutoSelectCallerId(autoSelect) {
        this.voip.setAutoSelectCallerId(autoSelect);
        this.render();
    }

    /** @returns {string} */
    get queueIndicatorTitle() {
        return _t("You are currently in a queue.");
    }

    /** @param {{ label: string, name: string }} duration @returns {string} */
    getDndDurationName(duration) {
        return duration.label === "forever" ? _t("Until I turn it off") : duration.name;
    }

    openPhoneNumberPurchaseWizard() {
        this.action.doAction("voip.action_voip_did_number_search_wizard");
    }

    openPhoneNumberRequestWizard() {
        this.action.doAction("voip.voip_phone_number_request_action");
    }

    /** @param {{ id: number, is_logged: boolean, queue_id: number }} membership */
    async toggleMembership(membership) {
        const isLogged = !membership.is_logged;
        this.state.pendingAgentIds.add(membership.id);
        try {
            const result = await this.orm.call(
                "voip.queue.agent",
                "set_current_user_queue_membership",
                [membership.id, isLogged]
            );
            if (status(this) === "destroyed") {
                return;
            }
            membership.is_logged = result;
            this.env.bus.trigger("VOIP:QUEUE-AGENTS-UPDATED", membership.queue_id);
        } catch {
            if (status(this) !== "destroyed") {
                this.notification.add(_t("Could not update your queue membership."), {
                    type: "danger",
                });
            }
        } finally {
            if (status(this) !== "destroyed") {
                this.state.pendingAgentIds.delete(membership.id);
            }
        }
    }
}
