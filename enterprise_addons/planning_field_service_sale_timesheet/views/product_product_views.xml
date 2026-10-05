<odoo>
    <record id="planning_field_service_product_catalog_kanban_view" model="ir.ui.view">
        <field name="name">planning.field.service.sale.timesheet.product.catalog.kanban.view.inherit</field>
        <field name="model">product.product</field>
        <field name="inherit_id" ref="product.product_view_kanban_catalog"/>
        <!-- make sure it's bigger than existing catalog view -->
        <field name="priority">20</field>
        <field name="mode">primary</field>
        <field name="arch" type="xml">
            <kanban position="attributes">
                <attribute name="js_class">field_service_product_kanban</attribute>
            </kanban>
        </field>
    </record>

<!-- Material kanban -->
    <record id="planning_field_service_product_catalog_inherit_search_view" model="ir.ui.view">
        <field name="name">planning.field.service.sale.timesheet.product.catalog.inherit.search.view</field>
        <field name="inherit_id" ref="product.product_view_search_catalog"/>
        <field name="model">product.product</field>
        <field name="mode">primary</field>
        <field name="priority">1000</field>
        <field name="arch" type="xml">
            <xpath expr="//filter[@name='favorites']" position="before">
                <filter string="Added Products" name="fsm_quantity" domain="[('fsm_quantity', '>', 0)]"/>
                <separator/>
            </xpath>
            <xpath expr="//filter[@name='products_in_sale_order']" position="attributes">
                <attribute name="invisible">1</attribute>
            </xpath>
        </field>
    </record>

    <record id="action_product_catalog" model="ir.actions.act_window">
        <field name="name">Add Products</field>
        <field name="res_model">product.product</field>
        <field name="view_mode">kanban,form</field>
        <field name="view_id" ref="planning_field_service_product_catalog_kanban_view"/>
        <field name="search_view_id" ref="planning_field_service_product_catalog_inherit_search_view"/>
        <field name="domain">
            [
                '|',
                    ('company_id', '=', False),
                    ('company_id', 'in', allowed_company_ids),

                ('sale_ok', '=', True),

                '|',
                    ('type', '=', 'consu'),
                    '&amp;', '&amp;',
                        ('type', '=', 'service'),
                        ('invoice_policy', '=', 'delivery'),
                        ('service_type', '=', 'manual')
            ]
        </field>
        <field name="context">
            {
                'product_catalog_order_model': 'sale.order',
                'child_field': 'order_line',
            }
        </field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                No products found. Let's create one!
            </p>
            <p>
                Keep track of the products you are using to complete your tasks,
                and invoice your customers for the goods.
            </p>
            <p>
                When your task is marked as done, your stock will be updated automatically.
            </p>
        </field>
    </record>

</odoo>
