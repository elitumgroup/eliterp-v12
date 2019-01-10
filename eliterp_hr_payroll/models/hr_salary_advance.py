# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero


class SalaryAdvanceLine(models.Model):
    _name = 'hr.salary.advance.line'
    _rec_name = "employee_id"
    _order = "employee_id"
    _description = _('Línea de anticipo de sueldo')

    @api.depends('pay_order_ids.pay_order_id.state', 'pay_order_ids.amount')
    def _compute_amount(self):
        """
        Calculamos los pagos del empleado asignado en las órdenes
        :return:
        """
        for record in self:
            paid = 0.00
            for line in record.pay_order_ids:
                if line.pay_order_id.state == 'paid':
                    paid += line.amount
            record.paid_amount = paid
            record.residual = record.amount_advance - record.paid_amount
            if float_is_zero(record.residual, precision_rounding=0.01):
                record.reconciled = True
            else:
                record.reconciled = False

    @api.multi
    def unlink(self):
        """
        No eliminamos líneas contabilizadas
        :return:
        """
        for line in self:
            if line.parent_state == 'posted':
                raise UserError(_("No podemos borrar líneas de anticipo contabilizadas."))
        return super(SalaryAdvanceLine, self).unlink()

    @api.depends('advanced_id.state')
    def _compute_parent_state(self):
        """
        Calculamos el estado del padre
        :return:
        """
        for record in self.filtered('advanced_id'):
            record.parent_state = record.advanced_id.state

    @api.one
    @api.constrains('amount_payable')
    def _check_amount_payable(self):
        """
        Verificamos monto a pagar no sea mayor al  total menos el residuo
        :return:
        """
        if self.amount_payable > self.residual:
            raise ValidationError("Monto a pagar (%.2f) mayor al saldo (%.2f) para %s." % (
                self.amount_payable, self.residual, self.employee_id.name
            ))

    employee_id = fields.Many2one('hr.employee', string='Empleado')
    job_id = fields.Many2one('hr.job', string='Cargo de trabajo', related='employee_id.job_id', store=True)
    admission_date = fields.Date(related='employee_id.admission_date', store=True, string='Fecha ingreso')
    amount_advance = fields.Float('Monto de avance', default=0.00)
    advanced_id = fields.Many2one('hr.salary.advance', 'Anticipo', ondelete="cascade")
    parent_state = fields.Char(compute="_compute_parent_state", string="Estado de anticipo")
    # Órdenes de pago
    selected = fields.Boolean('Seleccionar?', default=False)
    reconciled = fields.Boolean('Conciliado?', compute="_compute_amount", store=True)
    paid_amount = fields.Float('Pagado', compute='_compute_amount', store=True)
    residual = fields.Float('Saldo', compute='_compute_amount', store=True)
    amount_payable = fields.Float('A pagar')
    pay_order_ids = fields.One2many('account.employee.order.line', 'pay_order_salary_advance_line_id',
                                    string="Líneas de ordenes de pago",
                                    readonly=True,
                                    copy=False)


class SalaryAdvance(models.Model):
    _name = 'hr.salary.advance'
    _inherit = ['mail.thread']
    _order = 'date desc'
    _description = _('Anticipo de sueldo')

    @api.multi
    def print_advance(self):
        """
        Imprimimos anticipo
        :return:
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr_payroll.action_report_salary_advance').report_action(self)

    def load_employees(self):
        """
        Cargamos empleados para total de anticipo, debe tener un contrato (Activo) el empleado
        :return:
        """
        line_ids = []
        if self.line_ids:
            self.line_ids.unlink()  # Borramos líneas anteriores, no montar
        for employee in self.env['hr.employee'].search([
            ('active', '=', True),
            ('contract_id', '!=', False)
        ]):
            contract_id = employee.contract_id
            amount_advance = round(float((contract_id.wage * 40) / 100), 2)
            line_ids.append([0, 0, {
                'employee_id': employee.id,
                'amount_advance': amount_advance,
            }])
        return self.write({'line_ids': line_ids})

    @api.one
    @api.depends('line_ids')
    def _compute_amount_total(self):
        """
        Total del anticipo
        :return:
        """
        self.amount_total = sum(line.amount_advance for line in self.line_ids)

    @api.multi
    def to_approve(self):
        """
        Solicitar aprobación de anticipo de sueldo
        :return:
        """
        if not self.line_ids:
            raise UserError(_("No hay líneas de anticipo creadas."))
        self.update({'state': 'to_approve'})

    @api.multi
    def action_approve(self):
        """
        Aprobar anticipo de sueldo
        :return:
        """
        self.update({'state': 'approve', 'approval_user': self._uid})

    @api.multi
    def action_deny(self):
        """
        Negar anticipo de sueldo
        :return:
        """
        self.update({'state': 'deny'})

    def _get_journal(self):
        """
        Obtenemos el diario de la nota bancaria
        :return:
        """
        company = self.company_id
        domain = [
            ('name', '=', 'Anticipo de quincena'),
            ('company_id', '=', company.id)
        ]
        journal = self.env['account.journal'].search(domain, limit=1)
        if not journal:
            raise UserError(_("No está definido el diario Anticipo de quincena para compañía: %s") % company.name)
        return journal

    @api.multi
    def posted_advance(self):
        """
        Contabilizar anticipo, TODO: Revisar diario por empresa
        :return:
        """
        journal_id = self._get_journal()
        ref = "Anticipo de " + self.period
        move_id = self.env['account.move'].create({
            'journal_id': journal_id.id,
            'date': self.date,
            'ref': ref
        })
        account_debit = journal_id.default_debit_account_id.id
        account_credit = journal_id.default_credit_account_id.id
        if not account_credit or not account_debit:
            raise UserError(_("No existe cuenta acredora y/o deudora en diario."))
        self.env['account.move.line'].with_context(check_move_validity=False).create({
            'name': ref,
            'journal_id': journal_id.id,
            'account_id': account_credit,
            'move_id': move_id.id,
            'debit': 0.0,
            'credit': self.amount_total,
            'date': self.date
        })
        self.env['account.move.line'].with_context(check_move_validity=True).create({
            'name': ref,
            'journal_id': journal_id.id,
            'account_id': account_debit,
            'move_id': move_id.id,
            'debit': self.amount_total,
            'credit': 0.0,
            'date': self.date
        })
        move_id.post()
        return self.write({
            'name': move_id.name,
            'state': 'posted',
            'move_id': move_id.id
        })

    @api.one
    @api.depends('date')
    def _compute_period(self):
        """
        Calculamos el período con la fecha de emisión
        :return:
        """
        self.period = self.env['res.functions']._get_period_string(self.date)

    @api.depends('line_ids')
    def _compute_count_lines(self):
        """
        Cantidad de líneas de anticipo
        :return:
        """
        for record in self:
            record.count_lines = len(record.line_ids)

    @api.multi
    def unlink(self):
        """
        No eliminamos roles diferentes de borrador
        :return:
        """
        for line in self:
            if line.state != 'draft':
                raise ValidationError(_("No podemos borrar anticipos diferentes de borrador."))
        return super(SalaryAdvance, self).unlink()

    name = fields.Char('No. Documento', index=True, default='Nuevo anticipo')
    period = fields.Char('Período', compute='_compute_period', store=True)
    date = fields.Date('Fecha de emisión', default=fields.Date.context_today, required=True,
                       readonly=True, states={'draft': [('readonly', False)]})
    line_ids = fields.One2many('hr.salary.advance.line', 'advanced_id', string='Líneas de anticipo')
    move_id = fields.Many2one('account.move', string='Asiento contable', group="hr_payroll.group_hr_payroll_manager")
    amount_total = fields.Float('Total de anticipo', compute='_compute_amount_total', store=True,
                                track_visibility='onchange')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Por aprobar'),
        ('approve', 'Aprobado'),
        ('posted', 'Contabilizado'),
        ('deny', 'Negado')], string="Estado", default='draft', track_visibility='onchange')
    approval_user = fields.Many2one('res.users', string='Aprobado por', group="hr_payroll.group_hr_payroll_manager")
    count_lines = fields.Integer('Nº empleados', compute='_compute_count_lines')
    comment = fields.Text('Notas y comentarios', readonly=True, states={'draft': [('readonly', False)]})
    company_id = fields.Many2one('res.company', string="Compañía", default=lambda self: self.env.user.company_id)

    # Ordenes de pago
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
            pays = object.search([('salary_advance_id', '=', record.id)])
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

    @api.one
    @api.depends('line_ids.selected')
    def _compute_total_pay_order(self):
        """
        Valor a pagar en la orden de pago sumando los empleados seleccionados
        :return:
        """
        total = 0.00
        for line in self.line_ids:
            if line.selected and not line.reconciled:
                total += line.amount_payable
        self.total_pay_order = round(total, 2)

    state_pay_order = fields.Selection([
        ('no credits', 'Sin abonos'),
        ('partial_payment', 'Abono parcial'),
        ('paid', 'Pagado'),
    ], string="Estado de pago", compute='_compute_customize_amount', readonly=True, copy=False,
        store=True)
    improved_pay_order = fields.Float('(-) Abonado', compute='_compute_customize_amount', store=True)
    residual_pay_order = fields.Float('Saldo', compute='_compute_customize_amount', store=True)
    pay_order_line = fields.One2many('account.pay.order', 'salary_advance_id', string='Órdenes de pago')
    pay_orders_count = fields.Integer('# Ordenes de pago', compute='_compute_pay_orders', store=True)
    total_pay_order = fields.Float('Total a pagar', compute='_compute_total_pay_order')
