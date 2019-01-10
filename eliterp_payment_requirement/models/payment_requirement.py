# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero


class PayOrder(models.Model):
    _inherit = 'account.pay.order'

    def _get_vals_document(self, active_model, active_ids):
        """
        :return:
        """
        vals = super(PayOrder, self)._get_vals_document(active_model, active_ids)
        if active_model == 'payment.requirement':
            payment_requirement = self.env['payment.requirement'].browse(active_ids)[0]
            vals.update({
                'date': payment_requirement.payment_date,
                'default_date': payment_requirement.payment_date,
                'type': 'request',
                'amount': payment_requirement.residual_pay_order,
                'default_amount': payment_requirement.residual_pay_order,
                'origin': payment_requirement.name,
                'payment_requirement_id': payment_requirement.id,
                'company_id': self.env.user.company_id.id,
                'beneficiary': payment_requirement.beneficiary
            })
        return vals

    type = fields.Selection(selection_add=[('request', 'RPG')])
    payment_requirement_id = fields.Many2one('payment.requirement', 'RPG')


class Voucher(models.Model):
    _inherit = 'account.voucher'

    @api.multi
    def data_payment_requirement(self):
        """
        Cargamos la información del requerimiento
        :return:
        """
        payment_requirement = self.pay_order_id.payment_requirement_id
        beneficiary = payment_requirement.beneficiary
        return self.update({
            'beneficiary': beneficiary,
            'reference': payment_requirement.name
        })

    @api.onchange('pay_order_id')
    def _onchange_pay_order_id(self):
        if self.type_pay_order == 'request':
            self.data_payment_requirement()
        return super(Voucher, self)._onchange_pay_order_id()


class PaymentRequirementLine(models.Model):
    _name = 'payment.requirement.line'
    _order = 'amount desc'
    _description = _('Línea de requerimiento de pago')

    @api.constrains('amount')
    def _check_amount(self):
        """
        Validamos monto no sea menor o iigual a 0
        """
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_("Monto no puede ser menor o igual a 0."))

    payment_requirement_id = fields.Many2one('payment.requirement', string="Requerimiento de pago", ondelete="cascade")
    name = fields.Char('Detalle', required=True)
    amount = fields.Float('Monto', required=True)


class PaymentRequirement(models.Model):
    _name = 'payment.requirement'
    _inherit = ['mail.thread']
    _order = 'payment_date desc'

    _description = _('Requerimiento de pago')

    @api.one
    @api.depends('line_ids.amount')
    def _compute_amount_total(self):
        """
        Total de cada línea del requerimiento
        """
        self.amount_total = round(sum(line.amount for line in self.line_ids), 2)

    @api.multi
    def print_payment_requirement(self):
        """
        TODO: Imprimimos requerimiento de pago
        """
        self.ensure_one()

    @api.multi
    def action_button_approve(self):
        """
        Acción para aprobar requerimiento
        :return:
        """
        self.write({
            'state': 'approve',
            'approval_user': self._uid,
        })

    @api.multi
    def action_button_deny(self):
        """
        Negar requerimiento
        :return:
        """
        self.write({
            'state': 'deny'
        })

    def _get_name(self):
        company = self.company_id
        sequence = self.env['ir.sequence'].with_context(force_company=company.id).next_by_code('payment.requirement')
        if not sequence:
            raise UserError(
                _("No está definida la secuencia con código 'payment.requirement' para compañía: %s") % company.name)
        return sequence

    @api.multi
    def to_approve(self):
        """
        Solicitar aprobación de requerimiento
        :return:
        """
        for request in self:
            if not request.line_ids:
                raise UserError(_('No existen líneas de detalle en requerimiento.'))
        self.write({
            'state': 'to_approve',
            'name': self._get_name()
        })

    @api.one
    @api.depends('type', 'supplier_id', 'employee_id', 'other')
    def _compute_beneficiary(self):
        if self.type == 'other':
            self.beneficiary = self.other
        elif self.type == 'employee':
            self.beneficiary = self.employee_id.name
        else:
            self.beneficiary = self.supplier_id.name

    @api.multi
    def copy(self, default=None):
        default = default or {}
        default['line_ids'] = [(0, 0, line.copy_data()[0]) for line in self.line_ids]
        return super(PaymentRequirement, self).copy(default=default)

    @api.multi
    def unlink(self):
        for payment in self:
            if not payment.state == 'draft':
                raise UserError("No se puede eliminar un requerimiento diferente a estado borrador.")
        return super(PaymentRequirement, self).unlink()

    @api.one
    @api.constrains('payment_date')
    def _check_payment_date(self):
        """
        Verificamos la fecha de pago no sea menor a la del requerimiento
        """
        if self.payment_date < self.request_date:
            raise ValidationError(_('La fecha de pago no puede ser menor a la de requerimiento.'))

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
            pays = object.search([('payment_requirement_id', '=', record.id)])
            record.pay_order_line = pays
            record.pay_orders_count = len(pays)

    @api.multi
    def action_view_pay_orders(self):
        """
        Ver órdenes de pagos vinculadas a el rpg
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
    pay_order_line = fields.One2many('account.pay.order', 'payment_requirement_id' ,string='Órdenes de pago')
    pay_orders_count = fields.Integer('# Ordenes de pago', compute='_compute_pay_orders', store=True)

    name = fields.Char('No. Documento', copy=False, index=True)
    request_date = fields.Date('Fecha requerimiento', default=fields.Date.context_today, required=True, readonly=True,
                               states={'draft': [('readonly', False)]})
    payment_date = fields.Date('Fecha de pago', default=fields.Date.context_today, required=True, readonly=True,
                               states={'draft': [('readonly', False)]}, track_visibility='onchange')
    supplier_id = fields.Many2one('res.partner', string='Responsable', readonly=True,
                                  states={'draft': [('readonly', False)]}, domain=[('supplier', '=', True)])
    employee_id = fields.Many2one('hr.employee', string='Responsable', readonly=True,
                                  states={'draft': [('readonly', False)]})
    other = fields.Char(string='Responsable', readonly=True,
                        states={'draft': [('readonly', False)]})
    beneficiary = fields.Char('Titular', track_visibility='onchange', compute='_compute_beneficiary', store=True,
                              index=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Por aprobar'),
        ('approve', 'Aprobado'),
        ('deny', 'Negado'), ], string='Estado', default='draft', copy=False, track_visibility='always')
    comment = fields.Text('Notas', track_visibility='onchange')
    document = fields.Binary('Documento', attachment=True, copy=False)
    document_name = fields.Char('Nombre de documento', copy=False)
    line_ids = fields.One2many('payment.requirement.line', 'payment_requirement_id',
                               string='Líneas de requerimiento', readonly=True,
                               states={'draft': [('readonly', False)]})
    amount_total = fields.Float(compute='_compute_amount_total', string="Total", store=True,
                                track_visibility='onchange')
    approval_user = fields.Many2one('res.users', 'Aprobado por', readonly=True, states={'draft': [('readonly', False)]},
                                    copy=False)

    @api.multi
    def action_cancel(self):
        if any(po.state != 'draft' for po in self.lines_pay_order):
            raise UserError("No se puede cancelar, RPG si tiene ordenes cerradas o anuladas.")
        self.write({'state': 'deny'})

    type = fields.Selection([
        ('other', 'Otro'),
        ('employee', 'Empleado'),
        ('supplier', 'Proveedor'),
    ], string="Para", default='other', readonly=True, states={'draft': [('readonly', False)]},
        help="Sirve para saber a quién está destinado el requerimiento.")
    company_id = fields.Many2one('res.company', string="Compañía", default=lambda self: self.env.user.company_id)
