{
    'name': 'Analytic Distribution Enforcement',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Garantiza que los apuntes contables contengan distribución analítica',
    'description': """
Analytic Distribution Enforcement
==================================

Módulo transversal que asegura la presencia de distribución analítica en todos
los documentos que generan movimientos contables.

Funcionalidades principales
----------------------------

**Facturas de cliente:**
- Hereda analítica desde la orden de venta.
- Si no hay orden de venta, toma la analítica de las líneas de factura.
- Distribución proporcional a CxC, impuestos y retenciones.

**Facturas de proveedor:**
- Hereda analítica desde la orden de compra.
- Si no hay orden de compra, toma la analítica de las líneas de factura.
- Distribución proporcional a CxP, impuestos y retenciones.

**Pagos (CxP y CxC):**
- Si el pago es sobre una factura, hereda la analítica de la factura.
- Si es un pago manual, el campo de analítica es obligatorio.
- La analítica se hereda en todos los apuntes contables del pago.

**Obligatoriedad:**
- No permite confirmar órdenes de venta/compra sin analítica.
- No permite publicar facturas, pagos ni asientos sin analítica.
- No permite validar recepciones, entregas ni costos en destino sin analítica.

**Inventario:**
- Campo analítica en el encabezado del picking con propagación a movimientos.
- Transferencias internas solo requieren analítica si generan asientos de valoración.
    """,
    'author': 'Custom Development',
    'website': '',
    'depends': [
        'analytic',
        'account',
        'sale',
        'purchase',
        'stock_account',
        'stock_landed_costs',
    ],
    'data': [
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'views/account_payment_register_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_landed_cost_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
