# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.tools import float_is_zero



class PayOrder(models.Model):
    _inherit = 'account.pay.order'

    def _get_vals_document(self, active_model, active_ids):
        """
        :return dict:
        """
        vals = super(PayOrder, self)._get_vals_document(active_model, active_ids)
        if active_model == 'hr.travel.expenses.liquidation':
            expenses_liquidation_id = self.env['hr.travel.expenses.liquidation'].browse(active_ids)[0]
            vals.update({
                'date': expenses_liquidation_id.date,
                'default_date': expenses_liquidation_id.date,
                'type': 'expenses liquidation',
                'amount': expenses_liquidation_id.residual_pay_order,
                'default_amount': expenses_liquidation_id.residual_pay_order,
                'origin': expenses_liquidation_id.name,
                'expenses_liquidation_id': expenses_liquidation_id.id,
                'company_id': expenses_liquidation_id.company_id.id,
                'beneficiary': expenses_liquidation_id.beneficiary.name
            })
        return vals

    type = fields.Selection(
        selection_add=[('expenses liquidation', 'Liquidación de viático')])
    expenses_liquidation_id = fields.Many2one('hr.travel.expenses.liquidation', 'Liquidación de viático')


class Voucher(models.Model):
    _inherit = 'account.voucher'

    @api.multi
    def data_expenses_liquidation(self):
        """
        Cargamos la información del liquidación de viático
        :return:
        """
        expenses_liquidation = self.pay_order_id.expenses_liquidation_id
        return self.update({
            'beneficiary': self.pay_order_id.beneficiary,
            'reference': expenses_liquidation.name
        })

    @api.onchange('pay_order_id')
    def _onchange_pay_order_id(self):
        if self.type_pay_order == 'expenses liquidation':
            self.data_expenses_liquidation()
        return super(Voucher, self)._onchange_pay_order_id()


class TravelExpensesLiquidation(models.Model):
    _inherit = 'hr.travel.expenses.liquidation'

    @api.one
    @api.depends('pay_order_line.state')
    def _compute_customize_amount(self):
        """
        Calculamos el saldo pendiente de las órdenes de pago
        :return:
        """
        pays = self.pay_order_line.filtered(lambda x: x.state == 'paid')
        if not pays:
            self.state_pay_order = 'no credits'
            self.residual_pay_order = self.amount_total
        else:
            total = 0.00
            for pay in pays:
                total += round(pay.amount, 3)
            self.improved_pay_order = total
            self.residual_pay_order = round(self.amount_total - self.improved_pay_order, 3)
            if float_is_zero(self.residual_pay_order, precision_rounding=0.01):
                self.state_pay_order = 'paid'
            else:
                self.state_pay_order = 'partial_payment'

    @api.depends('pay_order_line')
    def _compute_pay_orders(self):
        """
        Calculamos la ordenes de pago relacionadas a el rpg y su cantidad
        :return:
        """
        object = self.env['account.pay.order']
        for record in self:
            pays = object.search([('expenses_liquidation_id', '=', record.id)])
            record.pay_order_line = pays
            record.pay_orders_count = len(pays)

    @api.multi
    def action_view_pay_orders(self):
        """
        Ver órdenes de pagos vinculadas a liquidación
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
    pay_order_line = fields.One2many('account.pay.order', 'expenses_liquidation_id', string='Órdenes de pago')
    pay_orders_count = fields.Integer('# Ordenes de pago', compute='_compute_pay_orders', store=True)