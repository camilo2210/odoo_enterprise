<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="knowledge.KnowledgeArticleProperties">
        <div class="o_field_highlight o_knowledge_properties_panel" t-if="this.panelState.isDisplayed('properties') and this.props.record.data.parent_id">
            <div t-if="!this.hasProperties()" class="o_properties_helper text-center d-flex flex-column align-items-center justify-content-end my-3">
                <img t-attf-src="/knowledge/static/img/property-fields.svg" alt="Add Property Fields"/>
                <h5>Add Property Fields</h5>
                <p class="mb-2">
                    Organize your database with custom fields
                    (Text, Selection, ...). <br/>
                    Those fields will be available on all articles that share the same parent.
                </p>
            </div>
            <div class="o_field_widget o_field_properties">
                <PropertiesField
                    columns="1"
                    editMode="this.userIsInternal"
                    name="'article_properties'"
                    record="this.props.record"
                    readonly="this.props.record.data.is_locked || !this.props.record.data.user_can_write"
                    context="this.props.record.context"
                />
            </div>
        </div>
    </t>
</templates>
