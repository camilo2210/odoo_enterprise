<templates id="template" xml:space="preserve">
    <t t-name="account.BankRecListUploadButtons" t-inherit="web.ListView.Buttons" t-inherit-mode="primary">
        <xpath expr="." position="inside">
            <t t-if="this.showUploadButton" t-call="account.AccountViewUploadButton"/>
        </xpath>
    </t>

    <t t-name="account.BankRecListUploadRenderer" t-inherit="web.ListRenderer" t-inherit-mode="primary">
        <xpath expr="//div[@t-ref='this.rootRef']" position="before">
            <UploadDropZone
                t-if="this.showUploadButton"
                visible="this.dropzoneState.visible"
                hideZone="() => this.dropzoneState.visible = false"/>
        </xpath>

        <xpath expr="//div[@t-ref='this.rootRef']" position="attributes">
            <attribute name="t-on-dragenter.stop.prevent">this.onDragStart</attribute>
        </xpath>
    </t>
</templates>
