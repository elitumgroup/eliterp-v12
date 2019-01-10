# -*- coding: utf-8 -*-


from odoo import api, fields, models, tools


class AllPrintingPoints(models.Model):
    _name = "report.all.printing.points"
    _description = "Pedidos de venta agrupados por punto de impresión"
    _auto = False

    name = fields.Char('Referencia de pedido', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Empresa', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    date_order = fields.Datetime(string='Fecha del pedido', readonly=True)
    user_id = fields.Many2one('res.users', 'Vendedor', readonly=True)
    categ_id = fields.Many2one('product.category', 'Categoría de producto', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', 'Plantilla de producto', readonly=True)
    company_id = fields.Many2one('res.company', 'Compañía', readonly=True)
    price_total = fields.Float('Total', readonly=True)
    pricelist_id = fields.Many2one('product.pricelist', 'Lista de precios', readonly=True)
    price_subtotal = fields.Float(string='Subtotal del precio', readonly=True)
    product_qty = fields.Float('Cantidad de producto', readonly=True)
    point_printing_id = fields.Many2one('sri.point.printing', 'Punto de impresión', readonly=True)

    def _so(self):
        so_str = """
            WITH currency_rate as (%s)
                SELECT sol.id AS id,
                    so.name AS name,
                    so.partner_id AS partner_id,
                    sol.product_id AS product_id,
                    pro.product_tmpl_id AS product_tmpl_id,
                    so.date_order AS date_order,
                    so.user_id AS user_id,
                    pt.categ_id AS categ_id,
                    so.company_id AS company_id,
                    sol.price_total / COALESCE(cr.rate, 1.0) AS price_total,
                    so.pricelist_id AS pricelist_id,
                    sol.price_subtotal / COALESCE (cr.rate, 1.0) AS price_subtotal,
                    (sol.product_uom_qty / u.factor * u2.factor) as product_qty,
                    so.point_printing_id AS point_printing_id

            FROM sale_order_line sol
                    JOIN sale_order so ON (sol.order_id = so.id)
                    LEFT JOIN product_product pro ON (sol.product_id = pro.id)
                    LEFT JOIN product_template pt ON (pro.product_tmpl_id = pt.id)
                    LEFT JOIN product_pricelist pp ON (so.pricelist_id = pp.id)
                    LEFT JOIN currency_rate cr ON (cr.currency_id = pp.currency_id AND
                        cr.company_id = so.company_id AND
                        cr.date_start <= COALESCE(so.date_order, now()) AND
                        (cr.date_end IS NULL OR cr.date_end > COALESCE(so.date_order, now())))
                    LEFT JOIN product_uom u on (u.id=sol.product_uom)
                    LEFT JOIN product_uom u2 on (u2.id=pt.uom_id)
            WHERE so.state != 'cancel'
        """ % self.env['res.currency']._select_companies_rates()
        return so_str


    def _from(self):
        return """(%s)""" % (self._so())

    def get_main_request(self):
        request = """
            CREATE or REPLACE VIEW %s AS
                SELECT id AS id,
                    name,
                    partner_id,
                    date_order,
                    user_id,
                    categ_id,
                    company_id,
                    price_total,
                    pricelist_id,
                    point_printing_id,
                    price_subtotal,
                    product_qty
                FROM %s
                AS foo""" % (self._table, self._from())
        return request

    @api.model_cr
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(self.get_main_request())
