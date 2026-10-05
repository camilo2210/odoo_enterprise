<odoo>
    <div t-name="documents_spreadsheet.TopBar" t-inherit="o-spreadsheet-TopBar" t-inherit-mode="extension">
        <xpath expr="//div[hasclass('o-topbar-responsive')]" position="after">
            <div t-if="this.env.isArchived and this.env.isArchived()" class="topbar-banner trash-banner d-flex align-items-center justify-content-between">
                <div t-if="!this.uiService.isSmall"
                    class="h-100 d-flex align-items-center text-info px-3"
                    t-att-title="this.trashDescription">
                    <t t-call="o-spreadsheet-Icon.TRASH_FILLED" />
                    <span class="ps-1 pe-3">File is in trash</span>
                </div>
                <div
                    class="h-100 flex-fill d-flex justify-content-between rounded-0 alert alert-info ps-2 py-0 my-0">
                    <span class="d-flex align-items-center">
                        <t t-out="this.trashDescription"/>
                    </span>
                    <div
                        t-if="this.env.hasWriteAccess()"
                        class="btn btn-link flex-shrink-0"
                        t-on-click="() => this.env.takeOutOfTrash()">
                        Take out of trash
                    </div>
                </div>
            </div>
        </xpath>
    </div>
</odoo>
