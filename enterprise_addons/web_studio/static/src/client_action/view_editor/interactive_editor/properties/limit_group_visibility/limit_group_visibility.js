import { Component, computed, t, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useEditNodeAttributes } from "@web_studio/client_action/view_editor/view_editor_model";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";

export class LimitGroupVisibility extends Component {
    static template = "web_studio.ViewEditor.LimitGroupVisibility";
    static components = {
        MultiRecordSelector,
    };
    props = useProps({
        node: t.object(),
    });

    groupsData = computed(() => {
        const groups = JSON.parse(this.props.node.attrs.studio_groups || "[]");
        const allowGroups = [];
        const forbidGroups = [];
        const currentGroups = [];
        for (const group of groups) {
            const groupId = group.id;
            currentGroups.push(groupId);
            if (group.forbid) {
                forbidGroups.push(groupId);
            } else {
                allowGroups.push(groupId);
            }
        }

        return {
            allowGroups,
            forbidGroups,
            currentGroups,
        };
    });

    setup() {
        this.editNodeAttributes = useEditNodeAttributes();
    }

    handleNodeGroupsChange(allow, forbid) {
        const { allowGroups, forbidGroups } = this.groupsData();
        allow = new Set(allow || allowGroups);
        forbid = new Set(forbid || forbidGroups);
        if (!allow.isDisjointFrom(forbid)) {
            throw new Error("Cannot allow and forbid at the same time");
        }
        const resIds = [];
        for (const g of allow) {
            resIds.push(g);
        }
        for (const g of forbid) {
            resIds.push(`!${g}`);
        }
        return this.editNodeAttributes({ groups: resIds });
    }

    onChangeAttribute(value, name) {
        return this.editNodeAttributes({ [name]: value });
    }

    get allowGroupsProps() {
        const { allowGroups, currentGroups } = this.groupsData();
        return {
            resModel: "res.groups",
            fieldString: _t("Access Groups"),
            domain: [["id", "not in", currentGroups]],
            resIds: allowGroups,
            update: (resIds) => this.handleNodeGroupsChange(resIds, null),
        };
    }

    get forbidGroupsProps() {
        const { forbidGroups, currentGroups } = this.groupsData();
        return {
            resModel: "res.groups",
            fieldString: _t("Access Groups"),
            domain: [["id", "not in", currentGroups]],
            resIds: forbidGroups,
            update: (resIds) => this.handleNodeGroupsChange(null, resIds),
        };
    }
}
