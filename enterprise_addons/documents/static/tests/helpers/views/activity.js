import { mountView } from "@web/../tests/web_test_helpers";
import { getEnrichedSearchArch } from "@documents/../tests/helpers/views/search";

export const basicDocumentsActivityArch = /* xml */ `
<activity string="Documents" js_class="documents_activity">
    <field name="folder_id" required="True"/>
    <field name="access_token" invisible="1"/>

    <!-- Load fields for the details panel -->
    <field name="tag_ids" widget="many2many_tags" options="{'color_field': 'color'}"/>
    <field name="partner_id"/>
    <field name="owner_id"/>
    <field name="type"/>
    <field name="file_size"/>
    <field name="company_id"/>
    <field name="id"/>
    <field name="active"/>
    <field name="user_permission"/>
    <field name="attachment_id"/>
    <field name="res_id"/>
    <field name="res_model"/>
    <field name="res_model_name"/>
    <field name="res_name"/>
    <field name="shortcut_document_id"/>
    <field name="mimetype"/>
    <!-- We use many2many_tags to force loading display_name -->
    <field name="available_embedded_actions_ids" groups="base.group_user" widget="many2many_tags"/>

    <templates>
        <div t-name="activity-box">
            <field name="owner_id" widget="many2one_avatar_user"/>
            <div>
                <field class="o_text_block" name="name" display="full" required="True"/>
            </div>
        </div>
    </templates>
</activity>
`;

export async function mountDocumentsActivityView(params = {}) {
    return mountView({
        actionMenus: {},
        type: "activity",
        resModel: "documents.document",
        arch: basicDocumentsActivityArch,
        searchViewArch: getEnrichedSearchArch(),
        ...params,
    });
}
