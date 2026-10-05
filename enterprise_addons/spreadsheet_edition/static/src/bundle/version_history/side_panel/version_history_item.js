import { Component, onMounted, onPatched, proxy, signal, t, useProps } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { components } from "@odoo/o-spreadsheet";

import { formatToLocaleString } from "../../helpers/misc";
import { _t } from "@web/core/l10n/translation";
import { pyToJsLocale } from "@web/core/l10n/utils";

export class VersionHistoryItem extends Component {
    static template = "spreadsheet_edition.VersionHistoryItem";
    static components = { Dropdown, TextInput: components.TextInput };

    props = useProps({
        active: t.boolean(),
        revision: t.object(),
        onActivation: t.function(),
        onBlur: t.function(),
        getRevisions: t.function(),
        renameRevision: t.function(),
        restoreRevision: t.function(),
        forkHistory: t.function(),
        getLocale: t.function(),
        editable: t.boolean().optional(),
    });

    menuButtonRef = signal.ref();
    itemRef = signal.ref();
    labelRef = signal.ref();

    setup() {
        this.menuState = proxy({ isOpen: false });
        this.state = proxy({ editName: this.defaultName });

        const scrollIntoViewIfActive = () => {
            if (this.props.active) {
                this.itemRef()?.scrollIntoView({
                    behavior: "smooth",
                    block: "nearest",
                    inline: "nearest",
                });
            }
        };
        onMounted(scrollIntoViewIfActive);
        onPatched(scrollIntoViewIfActive);
    }

    get revision() {
        return this.props.revision;
    }

    get defaultName() {
        return (
            this.props.revision.name || this.formatRevisionTimeStamp(this.props.revision.timestamp)
        );
    }

    get formattedTimeStamp() {
        return this.formatRevisionTimeStamp(this.props.revision.timestamp);
    }

    get isLatestVersion() {
        return this.props.getRevisions()[0].nextRevisionId === this.revision.nextRevisionId;
    }

    renameRevision(newName) {
        this.state.editName = newName;
        if (!this.state.editName) {
            this.state.editName = this.defaultName;
        }
        if (this.state.editName !== this.defaultName) {
            this.props.renameRevision(this.revision.id, this.state.editName);
        }
    }

    get menuItems() {
        return [
            {
                label: _t("Make a copy"),
                onSelected: () => this.props.forkHistory(this.revision.id),
                id: "copy_" + this.revision.id,
            },
            {
                label: _t("Restore this version"),
                onSelected: () => this.props.restoreRevision(this.revision.id),
                id: "restore_" + this.revision.id,
            },
        ];
    }

    activate() {
        this.props.onActivation(this.revision.nextRevisionId);
    }

    formatRevisionTimeStamp(ISOdatetime) {
        const code = pyToJsLocale(this.props.getLocale().code);
        return formatToLocaleString(ISOdatetime, code);
    }
}
