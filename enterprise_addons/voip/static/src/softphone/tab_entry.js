import { useLayoutEffect } from "@web/owl2/utils";
import { Component, useProps, signal, t } from "@odoo/owl";

import { DiscussAvatar } from "@mail/core/common/discuss_avatar";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { scrollTo } from "@web/core/utils/scrolling";

export class TabEntry extends Component {
    static components = { DiscussAvatar };
    props = useProps({
        // Main record of the entry, should have a phone-related field. The rest
        // of the data must be provided either explicitly or through a "contact"
        // record (see below).
        record: t.object(),
        // TODO See _phone_get_number_fields, ideally this should be automatic
        phoneNumberField: t.string().optional("phone"),
        // Contact (res.partner) record related to the entry. Non-provided data
        // will be retrieved from there, except for the phone number, which will
        // only be retrieved from the main record.
        contactRecord: t.object().optional(),
        // If not provided, will use the contact voipName. If empty, the phone
        // number will be used.
        title: t.or([t.string(), t.object()]).optional(),

        extraClass: t.string().optional(""),
        subtitle: t.or([t.string(), t.object()]).optional(),
        subtitleClass: t.string().optional(""),
        subtitleIcon: t.string().optional(),
        subtitleIconClass: t.string().optional(),
        subtitleExtraIcons: t.array().optional([]),
        /**
         * The name of the section of the tab to which this entry belongs.
         */
        section: t.string(),
    });
    static template = "voip.TabEntry";

    activeRecordRef = signal.ref();

    setup() {
        this.softphone = useService("voip").softphone;
        useLayoutEffect(
            (scrollToActiveRecord) => {
                if (!scrollToActiveRecord || !this.activeRecordRef()) {
                    return;
                }
                scrollTo(this.activeRecordRef());
                this.softphone.callSummary.scrollToActiveRecord = false;
            },
            () => [this.softphone.callSummary.scrollToActiveRecord]
        );
        useLayoutEffect(
            (isActiveRecord) => {
                if (!isActiveRecord || !this.activeRecordRef()) {
                    return;
                }
                scrollTo(this.activeRecordRef());
            },
            () => [this.isActiveRecord]
        );
    }

    /** @returns {string} */
    get flagAlt() {
        return _t("%(country)s flag", { country: this.props.record.phone_country_id.name });
    }

    /** @returns {boolean} */
    get isActiveRecord() {
        return (
            this.softphone.activeTabSection === this.props.section &&
            this.props.record.eq(this.softphone.activeRecord)
        );
    }

    /**
     * Updates the active section and the active record. These two variables
     * determine which record to unfold and which record to return to after the
     * call summary is hidden.
     *
     * @param {MouseEvent} ev
     */
    onClickSummary(ev) {
        if (ev.target instanceof Element && ev.target.closest("button")) {
            return;
        }
        if (this.isActiveRecord) {
            this.softphone.activeRecord = null;
            this.softphone.activeTabSection = "";
        } else {
            this.softphone.activeTabSection = this.props.section;
            this.softphone.activeRecord = this.props.record;
        }
    }
}
