<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-inherit="mail.Message" t-inherit-mode="extension">
        <xpath expr="//div[hasclass('o-mail-Message-textContent')]" position="after">
            <AIRecordsPreview t-if="this.hasRecordPreviews" message="this.props.message" thread="this.props.thread"/>
        </xpath>
    </t>
</templates>
