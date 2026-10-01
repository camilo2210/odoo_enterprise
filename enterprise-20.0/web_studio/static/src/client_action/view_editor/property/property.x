<?xml version="1.0" encoding="utf-8"?>
<templates>

    <t t-name="web_studio.Property">
        <div t-ref="this.rootRef" t-attf-class="o_web_studio_property {{this.className}}">
            <div t-if="this.props.type === 'selection'" class="o_web_studio_sidebar_select mt-2 mb-2">
                <label t-att-for="this.props.name">
                    <t t-call-slot="default" />
                    <sup t-if="this.props.tooltip" class="text-info p-1" t-att-data-tooltip="this.props.tooltip" t-out="'?'"/>
                </label>
                <t t-set="choices" t-value="this.props.childProps.choices" />
                <SelectMenu t-if="choices"
                    t-props="this.props.childProps"
                    autoSort="false"
                    id="this.props.name"
                    name="this.props.name"
                    value="this.props.value"
                    placeholder="this.props.inputAttributes?.placeholder"
                    onSelect="(value) => this.props.onChange(value, this.props.name)"
                    class="'border-0'"
                    required="this.props.childProps.required === true"
                    disabled="this.props.isReadonly"
                />
            </div>

            <t t-elif="this.props.type === 'boolean'">
                <div class="clearfix o_web_studio_sidebar_checkbox d-flex">
                    <CheckBox
                        id="this.props.name"
                        name="this.props.name"
                        value="!!this.props.value"
                        onChange="(value) => this.props.onChange(value, this.props.name)"
                        disabled="this.props.isReadonly"
                    >
                        <t t-call-slot="default" />
                        <sup t-if="this.props.tooltip" class="text-info p-1" t-att-data-tooltip="this.props.tooltip" t-out="'?'"/>
                    </CheckBox>
                </div>
            </t>
            <div t-elif="this.props.type === 'domain'" class="o_web_studio_sidebar_text my-2 d-flex flex-column">
                <label t-att-for="this.props.name">
                    <t t-call-slot="default" />
                    <sup t-if="this.props.tooltip" class="text-info p-1" t-att-data-tooltip="this.props.tooltip" t-out="'?'"/>
                </label>
                <span t-if="this.props.isReadonly" t-att-name="this.props.name" t-out="this.props.value"  class="ps-2"/>
                <input
                    t-else=""
                    t-att="this.props.inputAttributes"
                    t-att-name="this.props.name"
                    t-att-id="this.props.name"
                    t-att-value="this.props.value"
                    t-on-click.prevent.stop="this.onDomainClicked"
                />
            </div>

            <div t-elif="this.props.type === 'icon'" class="o_web_studio_sidebar_select my-2 d-flex flex-column">
                <label t-att-for="this.props.name">
                    <t t-call-slot="default" />
                    <sup t-if="this.props.tooltip" class="text-info p-1" t-att-data-tooltip="this.props.tooltip" t-out="'?'"/>
                </label>
                <div class="fs-2">
                    <StudioIconSelector
                        className="'o_select_menu btn btn-light bg-light w-100'"
                        onSelect="(value) => this.props.onChange(value, this.props.name)"
                        value="this.props.value || ''"
                        required="this.props.childProps.required ?? false"/>
                </div>
            </div>

            <div t-else="" class="o_web_studio_sidebar_text my-2 d-flex flex-column">
                <label t-att-for="this.props.name">
                    <t t-call-slot="default" />
                    <sup t-if="this.props.tooltip" class="text-info p-1" t-att-data-tooltip="this.props.tooltip" t-out="'?'"/>
                </label>
                <span t-if="this.props.isReadonly" t-att-name="this.props.name" t-out="this.props.value" class="ps-2" />
                <input
                    t-else=""
                    t-att-name="this.props.name"
                    t-att-id="this.props.name"
                    t-att="this.props.inputAttributes"
                    t-att-value="this.props.value"
                    t-on-change="(ev) => this.props.onChange(ev.target.value, this.props.name)"
                />
            </div>
        </div>
    </t>

</templates>
