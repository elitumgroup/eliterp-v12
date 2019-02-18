# -*- coding: utf-8 -*-


from odoo import api, fields, models, tools, _
from datetime import datetime
import time
from odoo.tools.safe_eval import safe_eval
import babel
from odoo.exceptions import ValidationError


class PayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    provisions = fields.Boolean('Provisiones?', default=True,
                                help="Algunas estructuras salariales no acumulan beneficios sociales, por lo tanto no se marca.")


class SalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    account_id = fields.Many2one('account.account', string="Cuenta contable")

    _sql_constraints = [
        ('code_unique', 'unique (code,company_id)', "El código de la regla salarial debe ser único!")
    ]


class PayslipInput(models.Model):
    _inherit = 'hr.payslip.input'
    _order = 'amount desc'

    account_id = fields.Many2one('account.account', string='Cuenta contable',
                                 domain=[('account_type', '=', 'movement')])
    total = fields.Float('Total')
    contract_id = fields.Many2one('hr.contract', string='Contract', required=False,
                                  help="The contract for which applied this input")  # CM


class PayslipInput2(models.Model):
    _name = 'hr.payslip.input.2'
    _description = 'Egresos de rol'
    _order = 'amount desc'

    name = fields.Char(string='Descripción', required=True)
    payslip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(required=True, index=True, default=10)
    code = fields.Char(required=True, help="The code that can be used in the salary rules")
    amount = fields.Float(help="It is used in computation. For e.g. A rule for sales having "
                               "1% commission of basic salary for per product can defined in expression "
                               "like result = inputs.SALEURO.amount * contract.wage*0.01.")
    contract_id = fields.Many2one('hr.contract', string='Contract', required=False,
                                  help="The contract for which applied this input")
    account_id = fields.Many2one('account.account', string="Cuenta contable",
                                 domain=[('account_type', '=', 'movement')])
    total = fields.Float('Total')


class PayslipInput3(models.Model):
    _name = 'hr.payslip.input.3'
    _description = 'Provisión de rol'
    _order = 'amount desc'

    name = fields.Char(string='Descripción', required=True)
    payslip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(required=True, index=True, default=10)
    code = fields.Char(required=True, help="The code that can be used in the salary rules")
    amount = fields.Float(help="It is used in computation. For e.g. A rule for sales having "
                               "1% commission of basic salary for per product can defined in expression "
                               "like result = inputs.SALEURO.amount * contract.wage*0.01.")
    contract_id = fields.Many2one('hr.contract', string='Contract', required=False,
                                  help="The contract for which applied this input")
    account_id = fields.Many2one('account.account', string="Cuenta contable",
                                 domain=[('account_type', '=', 'movement')])
    employee_id = fields.Many2one('hr.employee', related='payslip_id.employee_id', store=True)
    date_from = fields.Date('hr.employee', related='payslip_id.date_from', store=True)
    total = fields.Float('Total')


class Payslip(models.Model):
    _name = 'hr.payslip'
    _order = 'employee_id asc, date_from desc'
    _inherit = ['hr.payslip', 'mail.thread']

    @api.multi
    def unlink(self):
        """
        No eliminamos roles diferentes de borrador
        :return:
        """
        for line in self:
            if line.state != 'draft':
                raise ValidationError(_("No podemos borar roles realizados o anulados."))
        return super(Payslip, self).unlink()

    @api.multi
    def print_role(self):
        """
        Imprimimos rol individual
        :return:
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr_payroll.action_report_payslip').report_action(self)

    @api.one
    @api.depends('date_from')
    def _compute_reference(self):
        """
        Obtenemos referencia de rol
        :return:
        """
        self.reference = self.env['res.functions']._get_period_string(self.date_from)

    @api.one
    @api.depends('input_line_ids', 'input_line_ids_2')
    def _compute_net_receive(self):
        """
        Obtenemos el valor neto a recibir (INGRESOS - EGRESOS)
        :return:
        """
        self.net_receive = round(sum(round(line.amount, 3) for line in self.input_line_ids), 3) - round(sum(
            round(line2.amount, 3) for line2 in self.input_line_ids_2), 3)

    @api.multi
    def action_payslip_done(self):
        """
        MM
        """
        self.write({
            'approval_user': self._uid,
            'state': 'done',
        })

    @api.model
    def get_inputs(self, employee_id):
        """
        MM: Obtenemos la lista de reglas salariales
        :param employee_id:
        :return: list
        """
        res = []
        contract = employee_id.contract_id
        rule_ids = self.env['hr.payroll.structure'].browse(contract.struct_id.id).get_all_rules()
        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x: x[1])]
        inputs = self.env['hr.salary.rule'].browse(sorted_rule_ids)

        local_dict = {
            'contract': contract,  # Último contrato de empleado
            'employee': employee_id,
            'minimum_wage': 394.00,
            'payslip': self,
            'result': 0.00
        }

        for input in inputs:  # Operaciones de reglas salariales
            if input.condition_select == 'python' and input.code != 'ADQ':
                safe_eval(input.condition_python, local_dict, mode='exec', nocopy=True)
                amount = round(local_dict['result'], 3)
            elif input.code == 'ADQ':
                advance_payment = self.env['hr.salary.advance.line'].search([
                    ('parent_state', '=', 'posted'),
                    ('employee_id', '=', employee_id.id),
                    ('advanced_id.date', '>=', self.date_from),
                    ('advanced_id.date', '<=', self.date_to)
                ])
                if advance_payment:
                    # Si existen se suman todos los anticipos contabilizados en ese período
                    amount = round(sum(line.amount_advance for line in advance_payment), 3)
                else:
                    amount = 0.00
            else:
                amount = 0.00
            input_data = {
                'name': input.name,
                'code': input.code,
                'account_id': input.account_id.id,
                'amount': amount,
                'type': input.category_id.name  # Para verificar si es de ingresos, egresos, etc
            }
            res += [input_data]
        return res

    @api.onchange('employee_id', 'date_from', 'date_to')
    def onchange_employee(self):
        """
        MM: Cálculo de ingresos, egresos y provisiones
        """
        res = {}
        if (not self.employee_id) or (not self.date_from) or (not self.date_to):
            return res

        employee = self.employee_id
        date_from = self.date_from
        contract = employee.contract_id

        if not contract:
            res['warning'] = {'title': _('Warning'), 'message': _(
                'Empleado %s no tiene contrato activo.') % employee.name}
            return res

        name_date = self.env['res.functions']._get_period_string(date_from)
        self.name = 'Rol de %s por %s' % (
            employee.name, name_date)
        self.company_id = employee.company_id
        self.number = name_date
        self.contract_id = contract.id
        self.struct_id = contract.struct_id
        input_line_ids = self.get_inputs(employee)  # Obtenemos todos las reglas salariales a calcular
        # Vacíamos las líneas para nuevo cálculo
        input_lines = self.input_line_ids.browse([])
        input_lines_2 = self.input_line_ids_2.browse([])
        input_lines_3 = self.input_line_ids_3.browse([])
        for r in input_line_ids:
            if r['type'] == 'INGRESOS':
                input_lines += input_lines.new(r)
            if r['type'] == 'EGRESOS':
                input_lines_2 += input_lines_2.new(r)
            if r['type'] == 'PROVISIÓN':
                input_lines_3 += input_lines_3.new(r)
        # Actualizamos categoría de rol
        self.input_line_ids = input_lines
        self.input_line_ids_2 = input_lines_2
        self.input_line_ids_3 = input_lines_3
        return

    @api.constrains('worked_days')
    def _check_worked_days(self):
        if self.worked_days > 30:
            raise ValidationError(_('No puede haber más de 30 días trabajados en período.'))

    worked_days = fields.Integer(string="Días trabajados", track_visibility='onchange', default=30, required=True,
                                 readonly=True, states={'draft': [('readonly', False)]})
    number_absences = fields.Integer(string="Nº de ausencias", default=0, readonly=True,
                                     states={'draft': [('readonly', False)]})
    # Egresos
    input_line_ids_2 = fields.One2many('hr.payslip.input.2', 'payslip_id', string='Egresos rol',
                                       readonly=True, states={'draft': [('readonly', False)]})
    # Provisión
    input_line_ids_3 = fields.One2many('hr.payslip.input.3', 'payslip_id', string='Provisión rol')
    net_receive = fields.Float('Neto a recibir', compute='_compute_net_receive', store=True,
                               track_visibility='onchange')
    approval_user = fields.Many2one('res.users', 'Aprobado por')
    comment = fields.Text('Notas y comentarios', track_visibility='onchange')
