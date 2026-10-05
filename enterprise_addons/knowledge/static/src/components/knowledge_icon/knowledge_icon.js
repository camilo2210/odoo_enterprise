import { useEmojiPicker } from "@web/core/emoji_picker/emoji_picker";
import { registry } from "@web/core/registry";
import { exprToBoolean } from "@web/core/utils/strings";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { getRandomIcon } from "@knowledge/js/knowledge_utils";

import { Component, signal, t, useProps, xml } from "@odoo/owl";

export default class KnowledgeIcon extends Component {
    static template = "knowledge.KnowledgeIcon";

    props = useProps({
        record: t.object(),
        readonly: t.boolean(),
        iconClasses: t.string().optional(),
        allowRandomIconSelection: t.boolean().optional(),
        autoSave: t.boolean().optional(),
        fallbackDefaultIcon: t.boolean().optional(),
    });

    iconRef = signal.ref();

    setup() {
        super.setup();
        this.emojiPicker = useEmojiPicker(this.iconRef, { hasRemoveFeature: true, onSelect: this.updateIcon.bind(this) });
    }

    get icon() {
        return this.props.record.data.icon;
    }

    get useFallbackFaIcon() {
        return !this.props.record.data.icon && this.props.fallbackDefaultIcon;
    }

    async selectRandomIcon() {
        this.updateIcon(await getRandomIcon());
    }

    updateIcon(icon) {
        this.props.record.update({icon});
        if (this.props.autoSave) {
            this.props.record.save();
        }
    }
}

class KnowledgeIconField extends KnowledgeIcon {
    static template = xml`<KnowledgeIcon t-props="this.props"/>`;
    static components = { KnowledgeIcon };

    props = useProps({
        ...standardFieldProps,
        allowRandomIconSelection: t.boolean(),
        autoSave: t.boolean(),
    });
}

registry.category("fields").add("knowledge_icon", {
    component: KnowledgeIconField,
    extractProps({ attrs, viewType }, dynamicInfo) {
        return {
            autoSave: viewType === "card",
            readonly: dynamicInfo.readonly,
            allowRandomIconSelection: exprToBoolean(attrs.allow_random_icon_selection),
        };
    },
});
