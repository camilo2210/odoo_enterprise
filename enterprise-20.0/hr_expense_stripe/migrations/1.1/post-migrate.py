def migrate(cr, version):
    # Since the product_id of product_mcc_stripe_tag is stored in a template file, changes to the category are not loaded
    # when a upgrade of the module is done, we need to manually load them here.
    # Using a template file was deliberate to prevent a change to that file to change the product_id of existing tags.
    cr.execute("""
        WITH target_codes(code, xmlid_name) AS (
            VALUES
                ('0763', 'product_product_no_cost'),
                ('5111', 'product_product_no_cost'),
                ('6010', 'product_product_no_cost'),
                ('6011', 'product_product_no_cost'),
                ('6399', 'product_product_no_cost'),
                ('7273', 'product_product_no_cost'),
                ('7699', 'product_product_no_cost'),
                ('3000-3350', 'expense_product_travel_accommodation'),
                ('3351-3500', 'expense_product_travel_accommodation'),
                ('3501-3999', 'expense_product_travel_accommodation'),
                ('5552', 'expense_product_travel_accommodation'),
                ('7011', 'expense_product_travel_accommodation'),
                ('7512', 'expense_product_travel_accommodation'),
                ('7542', 'expense_product_travel_accommodation')
        ), expense_products AS (
            SELECT name AS xmlid_name, res_id AS product_id
            FROM ir_model_data
            WHERE module = 'hr_expense'
              AND name IN ('product_product_no_cost', 'expense_product_travel_accommodation')
        ), company_product_map AS (
            SELECT ep.xmlid_name, jsonb_object_agg(c.id::text, ep.product_id) AS product_id
            FROM expense_products ep
            JOIN product_product pp ON pp.id = ep.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN res_company c ON pt.company_id IS NULL OR pt.company_id = c.id
            GROUP BY ep.xmlid_name
        )
        UPDATE product_mcc_stripe_tag AS mcc
        SET product_id = cpm.product_id
        FROM target_codes tc
        JOIN company_product_map cpm ON cpm.xmlid_name = tc.xmlid_name
        WHERE mcc.code = tc.code
    """)
