import { t, useProps } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { formatNumber } from "@hr_holidays/views/hooks";
import { TimeOffCard, TimeOffCardPopover } from "@hr_holidays/dashboard/time_off_card";

// Belgian legal-leave types (and their N-1/N-2 postponed counterparts) track an exact hour
// counter alongside the day counter (see l10n_be_hr_payroll's l10n_be_hours_tracked): the day
// count shown everywhere else is rounded for display, so it can silently disagree with the real
// hours left. Surfaced in the popover, muted, only when it actually differs (see the template).
patch(TimeOffCardPopover.prototype, {
    setup() {
        super.setup();

        this.bePayrollProps = useProps({
            l10n_be_hoursRemaining: t.string().optional(),
            l10n_be_negativeBalanceWarning: t.any().optional(),
        });
    },
});

patch(TimeOffCard.prototype, {
    // Same deviation-only hours hint as the popover, but formatted for the card itself (see
    // time_off_card_patch.xml) -- data is already available there via this.props.data.
    formatL10nBeHours(hours) {
        return hours !== undefined ? formatNumber(this.lang, hours) : undefined;
    },
    updateWarning() {
        return super.updateWarning() || Boolean(this.props.data.l10n_be_negative_balance_warning);
    },
    getPopoverProps() {
        return {
            ...super.getPopoverProps(),
            l10n_be_hoursRemaining: this.formatL10nBeHours(this.props.data.l10n_be_hours_remaining),
            l10n_be_negativeBalanceWarning: this.props.data.l10n_be_negative_balance_warning,
        };
    },
});
