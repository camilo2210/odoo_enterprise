import { Component, onWillStart, onWillUpdateProps, useProps, toRaw, t, proxy } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { ResizablePanel } from "@web/core/resizable_panel/resizable_panel";
import { SelectMenu, selectMenuProps } from "@web/core/select_menu/select_menu";
import { IrUiViewCodeEditor } from "@web/core/ir_ui_view_code_editor/code_editor";

export async function loadResources({
    mainResourceId,
    url = "/web_studio/get_xml_editor_resources",
    defaultResourceId = null,
    checkMainViewKey = false,
}) {
    const resources = await rpc(url, { key: mainResourceId });
    return {
        resources: resources.views.map((res) => ({
            ...res,
            isMainResource:
                res.key === mainResourceId ||
                res.id === mainResourceId ||
                res.xml_id === mainResourceId,
        })),
        defaultResource: getDefaultResource(
            resources.views,
            resources.main_view_key,
            defaultResourceId,
            checkMainViewKey
        ),
    };
}

function getDefaultResource(resources, mainViewKey, defaultResourceId, checkMainViewKey) {
    if (resources.length <= 0) {
        return null;
    }

    let defaultResource;
    if (checkMainViewKey && mainViewKey) {
        defaultResource = resources.find((res) => res.key === mainViewKey);
    }

    if (!defaultResource && (defaultResourceId || mainViewKey)) {
        const defaultId = defaultResourceId || mainViewKey;
        defaultResource = resources.find(
            (resource) =>
                resource.id === defaultId ||
                resource.xml_id === defaultId ||
                resource.key === defaultId
        );
    }
    return defaultResource || resources[0];
}

class ViewSelector extends SelectMenu {
    static template = "web_studio.ViewSelector";
    static choiceItemTemplate = "web_studio.ViewSelector.ChoiceItemRecursive";
    props = useProps({
        ...selectMenuProps,
        choices: t
            .array(
                t.object({
                    value: t.any(),
                    label: t.string(),
                    resource: t.any().optional(),
                })
            )
            .optional([]),
    });

    getMainViews() {
        return this.state.displayedOptions.filter((opt) => opt.resource.isMainResource);
    }

    getInherited(choice) {
        const inheritedChoices = this.state.displayedOptions.filter(
            (opt) => (opt.resource.inherit_id || [])[0] === choice.resource.id
        );
        if (inheritedChoices.length) {
            inheritedChoices.forEach((opt) => (opt.resource.relatedChoice = choice.resource.id));
        }
        return inheritedChoices;
    }

    getComposedBy(choice) {
        const resource = choice.resource;
        if (!resource.called_xml_ids) {
            return [];
        }
        const composedChoices = this.state.displayedOptions.filter(
            (opt) =>
                resource.called_xml_ids.includes(opt.resource.xml_id) ||
                resource.called_xml_ids.includes(opt.resource.key)
        );
        if (composedChoices.length) {
            composedChoices.forEach((opt) => (opt.resource.relatedChoice = resource.id));
        }
        return composedChoices;
    }

    // Parents of displayed options must also be visible when doing a search
    // Based on the filtered choices, they must be added from the list of choices
    sliceDisplayedOptions() {
        const childChoices = this.state.choices.filter((c) => c.resource.relatedChoice);
        childChoices.forEach((c) => this.addRelatedChoice(c.resource.relatedChoice));
        super.sliceDisplayedOptions();
    }

    addRelatedChoice(parentId) {
        if (this.state.choices.findIndex((c) => c.resource.id === parentId) === -1) {
            const parent = this.props.choices.find((c) => c.resource.id === parentId);
            if (!parent.resource.isMainResource) {
                this.addRelatedChoice(parent.resource.relatedChoice);
            }
            this.state.choices.push(parent);
        }
    }
}

export const xmlResourceEditorProps = {
    onClose: t.function(),
    onCodeChange: t.function().optional(),
    onSave: t.function().optional(),
    mainResourceId: t.any(),
    defaultResourceId: t.any().optional(),
    getDefaultResource: t.function().optional(() => () => {}),
    canSave: t.boolean().optional(true),
    minWidth: t.number().optional(400),
    initialWidth: t.number().optional(400),
    displayAlerts: t.boolean().optional(true),
    onResourceChange: t.function().optional(() => () => {}),
};

export class XmlResourceEditor extends Component {
    static template = "web_studio.XmlResourceEditor";
    static components = {
        ResizablePanel,
        CodeEditor: IrUiViewCodeEditor,
        SelectMenu: ViewSelector,
    };
    props = useProps(xmlResourceEditorProps);

    setup() {
        this.state = proxy({
            resourcesOptions: [],
            currentResourceId: null,
            _codeChanges: null,
        });
        onWillStart(() => this.loadResources(this.props.mainResourceId));

        onWillUpdateProps(async (nextProps) => {
            const resourceChanged = nextProps.mainResourceId !== this.props.mainResourceId;
            const nextResourceId =
                nextProps.mainResourceId !== this.props.mainResourceId
                    ? nextProps.mainResourceId
                    : this.state.currentResourceId;

            if (resourceChanged) {
                this.state._codeChanges = null;
                await this.loadResources(nextProps.mainResourceId);
                this.state.currentResourceId = nextResourceId;
            }
        });

        this.alerts = proxy({
            "built-in-file": {
                message: _t(
                    "Editing a built-in file through this editor is not advised, as it will prevent it from being updated during future App upgrades."
                ),
                display: true,
            },
        });
    }

    get minWidth() {
        return this.props.minWidth;
    }

    get arch() {
        const currentResourceId = this.state.currentResourceId;
        if (!currentResourceId) {
            return "";
        }
        const resource = this.getResourceFromId(currentResourceId);
        return this.tempCode || resource[this.getResourceArchField(resource)];
    }

    get tempCode() {
        if (!this.state.currentResourceId) {
            return "";
        }
        return this.state._codeChanges && this.state._codeChanges[this.state.currentResourceId];
    }

    set tempCode(value) {
        if (!this.state.currentResourceId) {
            return;
        }
        this.state._codeChanges = this.state._codeChanges || {};
        this.state._codeChanges[this.state.currentResourceId] = value;
    }

    get invalidLocators() {
        const res = this.getResourceFromId(this.state.currentResourceId);
        return res.invalid_locators;
    }

    getResourceArchField(resource) {
        if ("combined_arch" in resource) {
            return "combined_arch";
        } else {
            return "arch";
        }
    }

    getResourceFromId(resourceId) {
        const opt = this.state.resourcesOptions.find((opt) => opt.value === resourceId) || {};
        return opt.resource;
    }

    onFormat() {
        this.tempCode = window.vkbeautify.xml(this.tempCode || this.arch, 4);
    }

    hideAlert(alertKey) {
        this.alerts[alertKey].display = false;
    }

    onCloseClick() {
        this.props.onClose();
    }

    getChanges() {
        return { ...toRaw(this.state._codeChanges) };
    }

    onCodeChange(code) {
        this.tempCode = code;
        if (this.props.onCodeChange) {
            this.props.onCodeChange(this.getChanges());
        }
    }

    async onSaveClick() {
        if (!this.tempCode) {
            return;
        }
        const resource = this.getResourceFromId(this.state.currentResourceId);
        await this.props.onSave({
            resourceId: resource.id,
            newCode: this.tempCode,
            oldCode: resource.oldArch,
        });
        await this.loadResources(this.props.mainResourceId);
    }

    onResourceChange(resourceId) {
        this.state.currentResourceId = resourceId;
        this.props.onResourceChange(this.getResourceFromId(this.state.currentResourceId));
    }

    async loadResources(resourceId) {
        const { resources, defaultResource } = await loadResources({
            mainResourceId: resourceId,
            defaultResourceId: this.props.defaultResourceId,
        });

        const resourcesOptions = resources.map((res) => ({
            label: `${res.name} (${res.xml_id})`,
            value: res.id,
            resource: {
                ...res,
                oldArch: res[this.getResourceArchField(res)],
            },
        }));
        this.state.resourcesOptions = resourcesOptions;

        if (defaultResource) {
            this.state.currentResourceId = defaultResource.id;
        }

        return resourcesOptions;
    }
}
