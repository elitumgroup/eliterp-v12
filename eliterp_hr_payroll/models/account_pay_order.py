# -*- coding: utf-8 -*-


from odoo import api, fields, models, _


class EmployeeOrderLine(models.Model):
    _name = 'account.employee.order.line'
    _description = _('Línea de empleado en orden de pago')

    @api.multi
    def generate_check(self):
        """
        TODO: Creamos cheque de empleado
        :return:
        """
        self.ensure_one()
        new_voucher = self.env['account.voucher'].with_context({'voucher_type': 'purchase'})._voucher(self)
        action = self.env.ref('eliterp_treasury.eliterp_action_voucher_purchase')
        result = action.read()[0]
        res = self.env.ref('eliterp_treasury.eliterp_view_form_voucher_purchase', False)
        result['views'] = [(res and res.id or False, 'form')]
        result['res_id'] = new_voucher.id
        return result

    name = fields.Many2one('hr.employee', 'Nombre de empleado')
    amount = fields.Float('Monto')
    pay_order_id = fields.Many2one('account.pay.order', 'Orden de pago', ondelete="cascade")
    pay_order_salary_advance_line_id = fields.Many2one('hr.salary.advance.line', 'Línea de empleado',
                                                       ondelete="cascade",
                                                       index=True,
                                                       readonly=True)
    pay_order_payslip_run_line_id = fields.Many2one('hr.payslip.run.line', 'Línea de empleado',
                                                    ondelete="cascade",
                                                    index=True,
                                                    readonly=True)


class PayOrder(models.Model):
    _inherit = 'account.pay.order'

    def _get_vals_document(self, active_model, active_ids):
        """
        :return dict:
        """
        vals = super(PayOrder, self)._get_vals_document(active_model, active_ids)
        if active_model == 'hr.salary.advance':
            salary_advance = self.env['hr.salary.advance'].browse(active_ids)[0]
            vals.update({
                'date': salary_advance.date,
                'default_date': salary_advance.date,
                'type': 'salary advance',
                'amount': salary_advance.total_pay_order,
                'default_amount': salary_advance.total_pay_order,
                'origin': salary_advance.name,
                'salary_advance_id': salary_advance.id,
                'company_id': self.env.user.company_id.id,
                'beneficiary': '/'
            })
        if active_model == 'hr.payslip.run':
            payslip_run = self.env['hr.payslip.run'].browse(active_ids)[0]
            vals.update({
                'date': payslip_run.date_end,
                'default_date': payslip_run.date_end,
                'type': 'payslip run',
                'amount': payslip_run.total_pay_order,
                'default_amount': payslip_run.total_pay_order,
                'origin': payslip_run.move_id.name,
                'payslip_run_id': payslip_run.id,
                'company_id': self.env.user.company_id.id,
                'beneficiary': '/'
            })
        return vals

    @api.model
    def create(self, vals):
        res = super(PayOrder, self).create(vals)
        if res.type in ['salary advance', 'payslip run']:
            if res.salary_advance_id:
                employees = self._salary_advance_employee_ids(res.salary_advance_id)
                res['employee_ids'] = employees

            else:
                employees = self._pasylip_run_employee_ids(res.payslip_run_id)
                res['employee_ids'] = employees
            if len(employees) == 1:
                employee = self.env['hr.employee'].browse(employees[0][2]['name']   )
                res['beneficiary'] = employee.name
        return res

    def _salary_advance_employee_ids(self, salary_advance):
        employees = []
        for line in salary_advance.line_ids:
            if line.selected and not line.reconciled:
                employees.append([0, 0, {'name': line.employee_id.id,
                                         'amount': line.amount_payable,
                                         'pay_order_salary_advance_line_id': line.id}])
                line.update(
                    {'selected': False, 'amount_payable': 0})  # Le quitamos la selección y colocamos monto a pagar en 0
        return employees

    def _pasylip_run_employee_ids(self, pasylip_run):
        employees = []
        for line in pasylip_run.line_ids:
            if line.selected and not line.reconciled:
                employees.append([0, 0, {'name': line.role_id.employee_id.id,
                                         'amount': line.amount_payable,
                                         'pay_order_payslip_run_line_id': line.id}])
                line.update(
                    {'selected': False, 'amount_payable': 0})  # Le quitamos la selección y colocamos monto a pagar en 0
        return employees

    type = fields.Selection(
        selection_add=[('salary advance', 'Anticipo de quincena'), ('payslip run', 'Rol consolidado')])
    salary_advance_id = fields.Many2one('hr.salary.advance', 'Anticipo de quincena')
    payslip_run_id = fields.Many2one('hr.payslip.run', 'Rol consolidado')
    employee_ids = fields.One2many('account.employee.order.line', 'pay_order_id', string='Empleados')


class Voucher(models.Model):
    _inherit = 'account.voucher'

    @api.multi
    def data_salary_advance(self):
        """
        Cargamos la información del anticipo de quincena
        :return:
        """
        salary_advance = self.pay_order_id.salary_advance_id
        company = salary_advance.company_id.id
        if company in [1, 2]:
            code = '2.1.6.1'
        account = self.env['account.account'].search([('code', '=', code), ('company_id', '=', company)])
        list_accounts = []
        if account:
            list_accounts.append([0, 0, {'account_id': account.id,
                                     'amount': self.amount_cancel,
                                     }])
        return self.update({
            'account_line': list_accounts,
            'beneficiary': self.pay_order_id.beneficiary,
            'reference': salary_advance.name
        })

    @api.multi
    def data_payslip_run(self):
        """
        Cargamos la información del rol consolidado
        :return:
        """
        payslip_run_id = self.pay_order_id.payslip_run_id
        company = payslip_run_id.company_id.id
        if company in [1, 2]:
            code = '2.1.6.1'
        account = self.env['account.account'].search([('code', '=', code), ('company_id', '=', company)])
        list_accounts = []
        if account:
            list_accounts.append([0, 0, {'account_id': account.id,
                                     'amount': self.amount_cancel,
                                     }])
        return self.update({
            'account_line': list_accounts,
            'beneficiary': self.pay_order_id.beneficiary,
            'reference': payslip_run_id.move_id.name
        })

    @api.onchange('pay_order_id')
    def _onchange_pay_order_id(self):
        if self.type_pay_order == 'salary advance':
            self.data_salary_advance()
        if self.type_pay_order == 'payslip run':
            self.data_payslip_run()
        return super(Voucher, self)._onchange_pay_order_id()
