<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <function model="project.task.type" name="unlink">
            <value model="project.task.type" eval="ref('planning_project_stage_0')"/>
        </function>
        <function model="project.task.type" name="unlink">
            <value model="project.task.type" eval="ref('planning_project_stage_3')"/>
        </function>
        <function model="project.task.type" name="unlink">
            <value model="project.task.type" eval="ref('planning_project_stage_4')"/>
        </function>
    </data>
</odoo>
