<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">

    <t t-name="planning.PlanningGanttRenderer" t-inherit="web_gantt.GanttRenderer">
        <xpath expr="//div[hasclass('o_gantt_cells')]">
            <PlanningSplitTool reactive="this.splitToolHelperReactive"/>
        </xpath>
    </t>

    <t t-name="planning.PlanningGanttRenderer.RowHeader" t-inherit="web_gantt.GanttRenderer.RowHeader">
        <xpath expr="//t[@t-out='row.name']" position="replace">
            <Avatar t-if="this.hasAvatar(row)" t-props="this.getAvatarProps(row)"/>
            <Material t-elif="this.hasMaterial(row)" t-props="this.getMaterialProps(row)"/>
            <t t-else="" t-out="row.name"/>
        </xpath>
    </t>

    <t t-name="planning.PlanningGanttRenderer.ProgressBarLabel" t-inherit="web_gantt.GanttRenderer.ProgressBarLabel">
        <xpath expr="//span" position="attributes">
            <attribute name="t-att-class">{ 'text-danger': !(progressBar.is_fully_flexible_hours or progressBar.all_group_by_resources_fully_flexible) and progressBar.ratio gt 100 }</attribute>
            <attribute name="t-att-data-tooltip">!(progressBar.is_fully_flexible_hours or progressBar.all_group_by_resources_fully_flexible) and this.getProgressBarTooltip(progressBar)</attribute>
        </xpath>
        <xpath expr="//t[@t-out='progressBar.available_formatted']" position="replace">
            <t t-if="progressBar.is_fully_flexible_hours or progressBar.all_group_by_resources_fully_flexible" t-out="progressBar.value_formatted"/>
            <t t-else="" t-out="progressBar.available_formatted"/>
        </xpath>
    </t>

    <t t-name="planning.PlanningGanttRenderer.Pill" t-inherit="web_gantt.GanttRenderer.Pill">
        <xpath expr="//span[hasclass('o_gantt_pill_title')]" position="after">
            <t t-if="pill.hasAvatar">
                <div class="ms-auto o_gantt_pill_avatar" t-att-title="pill.record.employee_id.display_name">
                    <Avatar t-props="pill.avatarProps"/>
                </div>
            </t>
        </xpath>
    </t>

    <t t-name="planning.PlanningGanttRenderer.GroupPill" t-inherit="web_gantt.GanttRenderer.GroupPill" owl="1">
        <xpath expr="//div[hasclass('o_gantt_group_pill')]/div" position="before">
            <t t-set="workHours" t-value="this._computeWorkHours(pill, row)"/>
        </xpath>
        <xpath expr="//div[hasclass('o_gantt_group_pill')]/div" position="attributes">
            <attribute name="t-attf-class" add="{{ this._computeResourceOvertimeColors(pill, workHours, row) }}"/>
        </xpath>
        <xpath expr="//span[hasclass('o_gantt_pill_title')]" position="attributes">
            <attribute name="t-out">this._computeDisplayName(pill, workHours, row)</attribute>
        </xpath>
    </t>

    <t t-name="planning.GanttSidePanel.Panel" t-inherit="web.GanttSidePanel.Panel" t-inherit-mode="extension">
        <xpath expr="//div[hasclass('o_event_to_schedule_draggable')]/span" position="attributes">
            <attribute name="t-att-class" add="event.id === this.props.model.searchParams.context.active_id ? 'text-primary fw-bold' : ''"  separator=" "/>
        </xpath>
    </t>

</templates>
