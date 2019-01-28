# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class PayslipRunLine(models.Model):
    _name = 'hr.payslip.run.line'
    _order = 'name asc'
    _description = _('Línea de rol consolidado')

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
            record.residual = record.net_receive - record.paid_amount
            if float_is_zero(record.residual, precision_rounding=0.01):
                record.reconciled = True
            else:
                record.reconciled = False

    @api.depends('payslip_run_id')
    def _compute_parent_state(self):
        """
        Obtenemos el estado del padre
        :return:
        """
        for record in self.filtered('payslip_run_id'):
            record.parent_state = record.payslip_run_id.state

    @api.one
    @api.constrains('amount_payable')
    def _check_amount_payable(self):
        """
        Verificamos monto a pagar no sea mayor al  total menos el residuo
        :return:
        """
        if self.amount_payable > self.residual:
            raise ValidationError("Monto a pagar (%.2f) mayor al saldo (%.2f) para %s." % (
                self.amount_payable, self.residual, self.name
            ))

    name = fields.Char('Empleado')
    departament = fields.Char('Departamento')
    admission_date = fields.Date('Fecha de ingreso')
    identification_id = fields.Char('No. identificación')
    worked_days = fields.Integer('Días trabajados')
    # Ingresos
    wage = fields.Float('Sueldo')
    extra_hours = fields.Float('HE 100%')  # TODO: No se usan en estás empresas
    additional_hours = fields.Float('HE 50%')  # TODO: No se usan en estás empresas
    reserve_funds = fields.Float('Fondos reserva')
    tenth_3 = fields.Float('Décimo tercero')
    tenth_4 = fields.Float('Décimo cuarto')
    other_income = fields.Float('Otros ingresos')
    total_income = fields.Float('Total de ingresos')
    # Egresos
    payment_advance = fields.Float('Anticipo de quincena')
    iess_personal = fields.Float('IESS 9.45%')
    iess_patronal = fields.Float('IESS 17.60%')  # Gerente general
    loan_payment_advance = fields.Float('Préstamo de quincena')
    loan_unsecured = fields.Float('Préstamo quirografário')
    loan_mortgage = fields.Float('Préstamo hipotecario')
    penalty = fields.Float('Multas')
    absence = fields.Float('Faltas y atrasos')
    cellular_plan = fields.Float('Plan celular')
    other_expenses = fields.Float('Otros egresos')
    total_expenses = fields.Float('Total de egresos')
    # Suma
    net_receive = fields.Float('Neto a recibir')
    role_id = fields.Many2one('hr.payslip', 'Rol individual')
    payslip_run_id = fields.Many2one('hr.payslip.run', 'Rol consolidado', ondelete="cascade")
    parent_state = fields.Char(compute="_compute_parent_state", string="Estado de rol")
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

class PayslipRun(models.Model):
    _name = 'hr.payslip.run'
    _order = 'date_start desc'
    _inherit = ['hr.payslip.run', 'mail.thread']

    @api.multi
    def print_payslip_run(self):
        """
        Imprimimos rol consolidado
        :return:
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr_payroll.action_report_payslip_run').report_action(self)

    @api.multi
    def to_approve(self):
        """
        Solicitar aprobación de rol consolidado
        :return:
        """
        if not self.line_ids:
            raise UserError(_("No hay líneas de roles en período creadas en el sistema."))
        self.update({'state': 'to_approve'})

    @api.multi
    def action_approve(self):
        """
        Aprobar rol consolidado
        :return:
        """
        for rol in self.line_ids:  # Roles individuales, los aprobamos uno a uno
            rol.role_id.action_payslip_done()
        # Rol consolidado
        self.update({
            'state': 'approve',
            'approval_user': self._uid
        })

    def _create_line_expenses(self, code_rule, journal_id, move, amount):
        """
        Creamos líneas de movimientos para egresos
        :param rule:
        :param move:
        :param amount:
        :return: object
        """
        rule = self.env['hr.salary.rule'].search([('code', '=', code_rule)])[0]
        amount = round(amount, 3)
        self.env['account.move.line'].with_context(check_move_validity=False).create({
            'name': rule.name,
            'journal_id': journal_id.id,
            'account_id': rule.account_id.id,
            'move_id': move.id,
            'debit': 0.00,
            'credit': amount,
            'date': self.date_end
        })
        _logger.info(rule.name + ': ' + str(amount))

    def _create_line_income(self, code_rule, journal_id, move, amount, check):
        """
        Creamos líneas de movimientos para ingresos
        :param rule:
        :param move:
        :param amount:
        :param check:
        :return: object
        """
        rule = self.env['hr.salary.rule'].search([('code', '=', code_rule)])[0]
        amount = round(amount, 3)
        self.env['account.move.line'].with_context(check_move_validity=check).create({
            'name': rule.name,
            'journal_id': journal_id.id,
            'account_id': rule.account_id.id,
            'move_id': move.id,
            'debit': amount,
            'credit': 0.00,
            'date': self.date_end
        })
        _logger.info(rule.name + ': ' + str(amount))

    def _get_journal(self):
        """
        Obtenemos el diario de la nota bancaria
        :return:
        """
        company = self.company_id
        domain = [
            ('name', '=', 'Rol consolidado'),
            ('company_id', '=', company.id)
        ]
        journal = self.env['account.journal'].search(domain, limit=1)
        if not journal:
            raise UserError(_("No está definido el diario Rol consolidado para compañía: %s") % company.name)
        return journal

    @api.one
    def confirm_payslip_run(self):
        """
        Confirmamos y contabilizamos el rol consolidado
        :return:
        """
        journal_id = self._get_journal()
        move_id = self.env['account.move'].create({
            'journal_id': journal_id.id,
            'date': self.date_end,
        })
        # Ingresos
        wage = 0.00
        tenth_3 = 0.00
        tenth_4 = 0.00
        reserve_funds = 0.00
        other_income = 0.00
        total_income = 0.00
        # Egresos
        payment_advance = 0.00
        loan_payment_advance = 0.00
        iess_personal = 0.00
        loan_unsecured = 0.00
        loan_mortgage = 0.00
        penalty = 0.00
        absence = 0.00
        cellular_plan = 0.00
        iess_patronal = 0.00
        other_expenses = 0.00
        total_expenses = 0.00
        # Provisiones
        net_receive = 0.00
        provision_tenth_3 = []
        provision_tenth_4 = []
        provision_reserve_funds = 0.00
        advances = []
        reserve_funds = False  # Bandera para fondos de reserva
        for role in self.line_ids:  # Comenzamos a sumar los roles individuales para creación del consolidado
            wage += round(role.wage, 3)
            other_income += round(role.other_income, 3)
            iess_personal += round(role.iess_personal, 3)
            iess_patronal += round(role.iess_patronal, 3)
            loan_payment_advance += round(role.loan_payment_advance, 3)
            loan_unsecured += round(role.loan_unsecured, 3)
            loan_mortgage += round(role.loan_mortgage, 3)
            # Añadimos ADQ
            advances.append(
                {
                    'amount': round(role.payment_advance, 3),
                })
            penalty += round(role.penalty, 3)
            absence += round(role.absence, 3)
            cellular_plan += round(role.cellular_plan, 3)
            other_expenses += round(role.other_expenses, 3)
            net_receive += round(role.net_receive, 3)
            if role.role_id.struct_id.provisions:  # Para no colocar nada a las ES sin provisiones
                # DT y DT
                if role.tenth_3 == 0.00:
                    provision_tenth_3.append(role)
                else:
                    tenth_3 += round(role.tenth_3, 3)
                if role.tenth_4 == 0.00:
                    provision_tenth_4.append(role)
                else:
                    tenth_4 += round(role.tenth_4, 3)
                # Fondos de reserva retenidos
                if role.role_id.employee_id.accumulate_reserve_funds == 'yes' and role.role_id.employee_id.working_time:
                    reserve_funds = True
                    provision_reserve_funds += round((float(role.wage) * float(8.33)) / float(100),
                                                     3)
                # Fondos de reserva cobrados
                if role.role_id.employee_id.working_time:
                    reserve_funds += round((float(role.wage) * float(8.33)) / float(100), 3)
        # Décimos
        amount_provision_tenth_3 = 0.00
        for tenth_3_object in provision_tenth_3:
            amount_provision_tenth_3 += round((tenth_3_object.wage + tenth_3_object.additional_hours) / 12.00, 3)
        amount_provision_tenth_4 = 0.00
        for tenth_4_object in provision_tenth_4:
            amount_provision_tenth_4 += round((float(394) / 360) * tenth_4_object.worked_days, 3)
        # Creamos líneas de movimiento de egresos
        _logger.info('***EGRESOS***')
        amount_advances = 0.00
        for advance in advances:  # Anticipos de quincena
            amount_advances += round(advance['amount'], 3)
        self._create_line_expenses('ADQ', journal_id, move_id, amount_advances)  # ADQ
        self._create_line_expenses('IESS_9.45%', journal_id, move_id, iess_personal)  # IESS 9.45%
        self._create_line_expenses('PRES_QUIRO', journal_id, move_id, loan_unsecured)  # Préstamo quirografario
        self._create_line_expenses('PRES_HIPO', journal_id, move_id, loan_mortgage)  # Préstamo hipotecario
        self._create_line_expenses('MUL', journal_id, move_id, penalty)  # Multas
        self._create_line_expenses('FALT_ATRA', journal_id, move_id, absence)  # Faltas y atrasos
        self._create_line_expenses('PLAN', journal_id, move_id, cellular_plan)  # Plan celular
        self._create_line_expenses('PRES_ANTIC', journal_id, move_id,
                                   loan_payment_advance)  # Préstamo anticipo quincena
        self._create_line_expenses('IESS_17.60%', journal_id, move_id, iess_patronal)  # IEES 17.60%
        self._create_line_expenses('OEG', journal_id, move_id, other_expenses)  # Otros egresos

        # Creamos líneas de movimiento de provisión, PROVISIÓN VACACIONES
        _logger.info('***PROVISIONES***')
        if reserve_funds:  # Si acumula beneficios (Fondos de reserva) se crea está línea de movimiento
            self._create_line_expenses('PFR', journal_id, move_id, provision_reserve_funds)
        patronal = round((float(wage * 12.15)) / 100, 3)
        self._create_line_expenses('PDT', journal_id, move_id, amount_provision_tenth_3)  # Provisión de DT
        self._create_line_expenses('PDC', journal_id, move_id, amount_provision_tenth_4)  # Provisión de DC
        self._create_line_expenses('IESS_12.15%', journal_id, move_id, patronal)  # IEES 12.15%
        self._create_line_expenses('NPP', journal_id, move_id, net_receive)  # Nómina a pagar

        total_credit = 0.00
        total_credit = amount_advances + iess_personal + loan_unsecured + loan_mortgage + penalty + absence
        total_credit = total_credit + cellular_plan + loan_payment_advance + + iess_patronal
        total_credit = total_credit + other_expenses + provision_reserve_funds + amount_provision_tenth_3
        total_credit = total_credit + amount_provision_tenth_4 + patronal + net_receive
        _logger.critical('-TOTAL HABER = %f\n' % round(total_credit, 2))

        # Creamos líneas de movimiento de ingresos
        _logger.info('***INGRESOS***')
        self._create_line_income('PGA', journal_id, move_id, patronal, False)  # Patronal (Gastos)
        amount_tenth_3 = round(tenth_3, 3) + round(amount_provision_tenth_3, 3)
        self._create_line_income('DT_MENSUAL', journal_id, move_id, amount_tenth_3, False)  # Décimo tercero mensual
        amount_tenth_4 = round(tenth_4, 3) + round(amount_provision_tenth_4, 3)
        self._create_line_income('DC_MENSUAL', journal_id, move_id, amount_tenth_4, False)  # Décimo cuarto mensual
        self._create_line_income('FR_MENSUAL', journal_id, move_id, reserve_funds, False)  # Fondos de reserva mensual
        self._create_line_income('OIN', journal_id, move_id, other_income, False)  # Otros ingresos

        total_debit = 0.00
        total_debit = patronal + amount_tenth_3 + amount_tenth_4 + reserve_funds
        total_debit = total_debit + other_income + wage
        _logger.critical('-TOTAL DEBE = %f\n' % round(total_debit, 2))
        _logger.critical('-DIFERENCIA = %f' % round((total_credit - total_debit), 2))

        self._create_line_income('SUE', journal_id, move_id, wage, True)  # Sueldo, se verifica asiento cuadrado

        move_id.post()
        move_id.write({
            'ref': "Rol consolidado" + "-" + self.name,
            'name': move_id.name,
            'date': self.date_end
        })
        self.update({'state': 'closed', 'move_id': move_id.id})

    @api.multi
    def unlink(self):
        """
        No eliminamos roles diferentes de borrador
        :return:
        """
        for line in self:
            if line.state != 'draft':
                raise ValidationError(_("No podemos borrar rol consolidado diferente de borrador."))
        return super(PayslipRun, self).unlink()

    @api.multi
    def add_roles(self):
        """
        Añadimos los roles de cada uno de los empleados creados
        en el mismo período
        """
        roles = self.env['hr.payslip'].search(
            [
                ('date_from', '>=', self.date_start),
                ('date_from', '<=', self.date_end),
                ('state', '=', 'draft'),
            ]
        )
        if not roles:
            raise UserError(_("No hay roles en borrador en el período selecionado."))
        else:
            line_ids = self.line_ids.browse([])
            for role in roles:
                data = {
                    'name': role.employee_id.name,
                    'departament': role.employee_id.department_id.name,
                    'admission_date': role.employee_id.admission_date,
                    'identification_id': role.employee_id.identification_id,
                    'worked_days': role.worked_days,
                    # Ingresos
                    'wage': role.input_line_ids.filtered(lambda x: x.code == 'SUE')[0].amount,
                    'reserve_funds': role.input_line_ids.filtered(lambda x: x.code == 'FR_MENSUAL')[
                        0].amount if role.input_line_ids.filtered(
                        lambda x: x.code == 'FR_MENSUAL') else 0.00,
                    'tenth_3': role.input_line_ids.filtered(lambda x: x.code == 'DT_MENSUAL')[
                        0].amount if role.input_line_ids.filtered(
                        lambda x: x.code == 'DT_MENSUAL') else 0.00,
                    'tenth_4': role.input_line_ids.filtered(lambda x: x.code == 'DC_MENSUAL')[
                        0].amount if role.input_line_ids.filtered(
                        lambda x: x.code == 'DC_MENSUAL') else 0.00,
                    'other_income': role.input_line_ids.filtered(lambda x: x.code == 'OIN')[
                        0].amount if role.input_line_ids.filtered(
                        lambda x: x.code == 'OIN') else 0.00,
                    'total_income': sum(line.amount for line in role.input_line_ids),

                    # Egresos
                    'payment_advance': role.input_line_ids_2.filtered(lambda x: x.code == 'ADQ')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'ADQ') else 0.00,
                    'iess_personal': role.input_line_ids_2.filtered(lambda x: x.code == 'IESS_9.45%')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'IESS_9.45%') else 0.00,
                    'iess_patronal': role.input_line_ids_2.filtered(lambda x: x.code == 'IESS_17.60%')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'IESS_17.60%') else 0.00,
                    'loan_payment_advance': role.input_line_ids_2.filtered(lambda x: x.code == 'PRES_ANTIC')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'PRES_ANTIC') else 0.00,
                    'loan_unsecured': role.input_line_ids_2.filtered(lambda x: x.code == 'PRES_QUIRO')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'PRES_QUIRO') else 0.00,
                    'loan_mortgage': role.input_line_ids_2.filtered(lambda x: x.code == 'PRES_HIPO')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'PRES_HIPO') else 0.00,
                    'penalty': role.input_line_ids_2.filtered(lambda x: x.code == 'MUL')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'MUL') else 0.00,
                    'absence': role.input_line_ids_2.filtered(lambda x: x.code == 'FALT_ATRA')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'FALT_ATRA') else 0.00,
                    'cellular_plan': role.input_line_ids_2.filtered(lambda x: x.code == 'PLAN')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'PLAN') else 0.00,
                    'other_expenses': role.input_line_ids_2.filtered(lambda x: x.code == 'OEG')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'OEG') else 0.00,
                    'total_expenses': sum(line.amount for line in role.input_line_ids_2),
                    'net_receive': role.net_receive,
                    'role_id': role.id
                }
                line_ids += line_ids.new(data)
            self.line_ids = line_ids

    @api.one
    @api.depends('line_ids')
    def _compute_amount_total(self):
        """
        Calculamos el total del rol consolidado
        """
        self.amount_total = sum(line.net_receive for line in self.line_ids)

    @api.one
    @api.depends('line_ids')
    def _compute_count_employees(self):
        """
        Calculamos en # de empleados en rol consolidado
        :return:
        """
        self.count_employees = len(self.line_ids)

    @api.multi
    def action_deny(self):
        """
        Negar rol consolidado
        :return:
        """
        self.update({'state': 'deny'})

    @api.onchange('date_start')
    def _onchange_date_start(self):
        """
        Nombre por defecto al cambiar fecha de rol consolidado
        :return:
        """
        if self.date_start:
            self.name = self.env['res.functions']._get_period_string(self.date_start)

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Por aprobar'),
        ('approve', 'Aprobado'),
        ('closed', 'Contabilizado'),
        ('deny', 'Negado')
    ], string='Estado', index=True, readonly=True, copy=False, default='draft', track_visibility='onchange')  # CM
    line_ids = fields.One2many('hr.payslip.run.line', 'payslip_run_id',
                               string="Líneas de rol consolidado")
    move_id = fields.Many2one('account.move', string="Asiento contable", copy=False)
    amount_total = fields.Float('Total de rol', compute='_compute_amount_total', store=True,
                                track_visibility='onchange')
    count_employees = fields.Integer('No. Empleados', compute='_compute_count_employees', track_visibility='onchange')
    approval_user = fields.Many2one('res.users', 'Aprobado por', copy=False, track_visibility='onchange')
    comment = fields.Text('Notas y comentarios', track_visibility='onchange')
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
