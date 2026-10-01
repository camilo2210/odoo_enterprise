<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data>
        <record id="view_account_report_file_download_error_wizard_form" model="ir.ui.view">
            <field name="name">account.report.file.download.error.wizard.form</field>
            <field name="model">account.report.file.download.error.wizard</field>
            <field name="arch" type="xml">
                <form string="File Download Errors">
                    <field name="file_content" invisible="1"/>
                    <div invisible="file_content">
                        <span>One or more error(s) occurred during file generation:</span>
                    </div>
                    <div>
                        <field name="actionable_errors" class="o_field_html w-100" widget="actionable_errors"/>
                        <p invisible="not has_danger_actionable_errors"><i>Errors marked with <i class="oi" data-icon="warning"/> are critical and will produce an invalid file.</i></p>
                    </div>
                    <footer>
                        <button string="Download Anyway"
                                name="button_download"
                                type="object"
                                class="btn btn-primary"
                                close="1"
                                data-hotkey="d"/>
                        <button string="Close"
                                class="btn btn-secondary"
                                special="cancel"
                                data-hotkey="z"/>
                    </footer>
                </form>
            </field>
        </record>
    </data>
</odoo>
