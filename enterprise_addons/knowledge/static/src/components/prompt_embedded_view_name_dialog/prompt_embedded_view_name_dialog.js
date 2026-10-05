import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { Component, onMounted, signal, t, useProps } from "@odoo/owl";

export class PromptEmbeddedViewNameDialog extends Component {
    static template = "knowledge.PromptEmbeddedViewNameDialog";
    static components = { Dialog };

    props = useProps({
        defaultName: t.string().optional(),
        isNew: t.boolean().optional(),
        viewType: t.string(),
        save: t.function(),
        close: t.function().optional(),
    });

    inputRef = signal.ref();

    setup () {
        onMounted(() => {
            window.setTimeout(() => {
                this.inputRef()?.focus(); // auto-focus
            }, 0);
        });
    }
    async save () {
        await this.props.save(this.inputRef().value);
        this.props.close();
    }
    /**
     * @returns {String}
     */
    get placeholder () {
        if (this.props.viewType === 'kanban') {
            return _t('e.g. Buildings');
        }
        if (this.props.viewType === 'list') {
            return _t('e.g. Todos');
        }
    }
    /**
     * @returns {String}
     */
    get title () {
        if (this.props.viewType === 'list') {
            return _t('Insert a List View');
        }
        if (this.props.viewType === 'kanban') {
            return _t('Insert a Kanban View');
        }
        return _t('Embed a View');
    }
    /**
     * @param {Event} event
     */
    onInputKeydown (event) {
        if (event.key === 'Enter') {
            this.save();
        }
    }
}
