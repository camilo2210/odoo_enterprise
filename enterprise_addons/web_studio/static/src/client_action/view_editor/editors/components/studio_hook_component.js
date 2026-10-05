import { Component, xml, Resource, signal, types as t, useProps } from "@odoo/owl";

const formGrid = xml`
    <div class="o_web_studio_hook"
        t-attf-class="g-col-sm-{{ this.props.colSpan }}"
        t-att-data-xpath="this.props.xpath"
        t-att-data-position="this.props.position"
        t-att-data-type="this.props.type">
            <span class="o_web_studio_hook_separator" />
    </div>
`;

const formPage = xml`
    <div class="o_web_studio_hook o_web_studio_page_hook d-flex h-100 p-0"
        t-attf-class="g-col-sm-{{ this.props.colSpan }} {{ this.isFieldHook ? 'o_web_studio_field_hook' : '' }}"
        t-att-data-xpath="this.props.xpath"
        t-att-data-position="this.props.position"
        t-att-data-structures="this.props.structures"
        t-att-data-hook-id="this.props.hookId"
        t-att-data-type="this.props.type">
            <span class="o_web_studio_page_hook_separator" />
    </div>
`;

const kanbanAsideHook = xml`
    <div t-attf-class="o_web_studio_hook mx-1 o_web_studio_hook position-absolute top-0 h-100 pe-none w-0 {{ this.props.position === 'before' ? 'start-0' : 'end-0'}}" t-att-data-type="this.props.type" t-att-data-xpath="this.props.xpath" t-att-data-position="this.props.position" data-structures="aside" />
`;

const kanbanRibbon = xml`
    <div class="o_web_studio_hook position-absolute top-0 start-0 h-100 overflow-hidden m-0 p-0 pe-none w-0" t-att-data-type="this.props.type" t-att-data-xpath="this.props.xpath" data-position="inside" data-structures="ribbon">
        <div class="bg-primary opacity-0 position-absolute" style="transform:rotate(45deg); height: 25px; width: 140px; top: 10px; right: -30px;" />
    </div>
`;

const kanbanInline = xml`
    <span class="o_web_studio_hook" t-att-data-xpath="this.props.xpath" t-att-data-position="this.props.position" t-att-data-type="this.props.type" t-att-data-infos="this.props.infos" t-att-data-structures="this.props.structures" />
`;

const defaultTemplate = xml`
    <div class="o_web_studio_hook"
        t-att-data-xpath="this.props.xpath"
        t-att-data-position="this.props.position"
        t-att-data-type="this.props.type"
        t-att-data-infos="this.props.infos"
        t-att-data-structures="this.props.structures"
        t-att-data-hook-id="this.props.hookId"
        t-ref="this.ref">
            <span class="o_web_studio_hook_separator" />
    </div>
`;

export class StudioHook extends Component {
    static template = xml`<t t-call="{{ this.getTemplate(this.props.subTemplate) }}" />`;
    static subTemplates = {
        formGrid,
        formPage,
        defaultTemplate,
        kanbanInline,
        kanbanAsideHook,
        kanbanRibbon,
    };

    props = useProps({
        xpath: t.string().optional(),
        position: t.string().optional(),
        type: t.string().optional(),
        colSpan: t.number().optional(),
        subTemplate: t.string().optional(),
        infos: t.string().optional(),
        structures: t.string().optional(),
        hookId: t.string().optional(),
        ref: t.or([t.signal(), t.instanceOf(Resource)]).optional(),
    });

    ref = this.props.ref || signal.ref();

    getTemplate(templateName) {
        return this.constructor.subTemplates[templateName || "defaultTemplate"];
    }
}
