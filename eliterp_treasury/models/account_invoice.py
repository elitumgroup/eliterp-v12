# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.tools import float_is_zero


class Invoice(models.Model):
    _inherit = 'account.invoice'

    @api.one
    @api.depends('state', 'pay_order_line.state')
    def _compute_customize_amount(self):
        """
        Calculamos el saldo pendiente de las órdenes de pago
        :return:
        """
        pays = self.pay_order_line.filtered(lambda x: x.state == 'paid')
        if not pays:
            self.state_pay_order = 'no credits'
            self.residual_pay_order = self.residual
        else:
            total = 0.00
            for pay in pays:  # Soló contabilizadas
                total += round(pay.amount, 3)
            self.improved_pay_order = total
            self.residual_pay_order = round(self.residual + self.improved_pay_order - self.improved_pay_order, 3)
            if float_is_zero(self.residual_pay_order, precision_rounding=0.01) or self.reconciled:
                self.state_pay_order = 'paid'
            else:
                self.state_pay_order = 'partial_payment'

    @api.depends('pay_order_line')
    def _compute_pay_orders(self):
        """
        Calculamos la ordenes de pago relacionadas a la factura y su cantidad
        :return:
        """
        for record in self:
            pays = self.env['account.pay.order'].search([('invoice_ids', 'in', record.id)])
            record.pay_order_line = pays
            record.pay_orders_count = len(pays)

    @api.multi
    def action_view_pay_orders(self):
        """
        Ver órdenes de pagos vinculadas a la factura
        :return:
        """
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('eliterp_treasury.action_pay_order')
        list_view_id = imd.xmlid_to_res_id('eliterp_treasury.view_tree_pay_order')
        form_view_id = imd.xmlid_to_res_id('eliterp_treasury.view_form_pay_order')
        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(self.pay_order_line) > 1:
            result['domain'] = "[('id','in',%s)]" % self.pay_order_line.ids
        elif len(self.pay_order_line) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = self.pay_order_line.ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    state_pay_order = fields.Selection([
        ('no credits', 'Sin abonos'),
        ('partial_payment', 'Abono parcial'),
        ('paid', 'Pagado'),
    ], string="Estado de pago", compute='_compute_customize_amount', readonly=True, copy=False,
        store=True)
    improved_pay_order = fields.Float('Abonado', compute='_compute_customize_amount', store=True)
    residual_pay_order = fields.Float('Saldo', compute='_compute_customize_amount', store=True)
    pay_order_line = fields.Many2many('account.pay.order', compute='_compute_pay_orders', store=True,
                                      string='Órdenes de pago')
    pay_orders_count = fields.Integer('# Ordenes de pago', compute='_compute_pay_orders', store=True)
