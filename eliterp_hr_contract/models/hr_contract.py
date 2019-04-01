# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError, UserError


class Employee(models.Model):
    _inherit = 'hr.employee'

    def _compute_contract_id(self):
        """
        MM: Obtenemos el último contrato activo
        :return:
        """
        Contract = self.env['hr.contract']
        for employee in self:
            employee.contract_id = Contract.search(
                [('employee_id', '=', employee.id), ('state_customize', '=', 'active')], order='date_start desc',
                limit=1)


class Contract(models.Model):
    _inherit = 'hr.contract'

    @api.constrains('employee_id')
    def _check_employee_id(self):
        """
        Validamos qué empleado no tenga contrato activo
        :return:
        """
        contract = self.employee_id.contract_id
        if contract and contract.state_customize == 'active':
            raise ValidationError(_("Empleado %s tiene contrato activo en sistema.") % self.employee_id.name)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """
        ME: Traemos la fecha de ingreso si contrato no está finalizado
        """
        res = super(Contract, self)._onchange_employee_id()
        if not self.state_customize == 'finalized':
            self.date_start = self.employee_id.admission_date
        return res

    @api.depends('date_start')
    def _compute_antiquity(self):
        """
        Obtenemos los días de antiguedad del empleado por contrato
        :return:
        """
        for record in self:
            end_date = record.date_start + timedelta(days=record.days_for_trial)
            time = (str(end_date - record.date_start)).strip(', 0:00:00')
            days = 0
            if time:
                days = int("".join([x for x in time if x.isdigit()]))
            record.antiquity = days

    @api.depends('date_start')
    def _compute_days_for_trial(self):
        """
        Contador de los días de prueba
        :return:
        """
        for contract in self:
            result = 0
            if contract.days_for_trial == contract.test_days:
                result = contract.test_days
            else:
                if contract.date_start:
                    days = (fields.Date.today() - contract.date_start).days
                    result = days
                contract.days_for_trial = result

    @api.onchange('is_trial')
    def _onchange_is_trial(self):
        """
        Colocamos las fechas de inicio y fin al cambiar campo Es período de prueba?
        :return:
        """
        if self.is_trial and self.date_start:
            self.trial_date_start = self.date_start
            self.trial_date_end = self.date_start + relativedelta(days=+ self.test_days)

    @api.depends('days_for_trial')
    def _compute_end_trial(self):
        """
        Si contador de días es mayor 90 días terminó pruebas
        :return:
        """
        if self.days_for_trial >= 90:
            self.end_trial = True

    def _get_name(self):
        company = self.company_id
        sequence = self.env['ir.sequence'].with_context(force_company=company.id).next_by_code('hr.contract')
        if not sequence:
            raise UserError(
                _("No está definida la secuencia con código 'hr.contract' para compañía: %s") % company.name)
        return sequence

    @api.model
    def _get_date_format(self):
        return self.env['res.functions']._get_date_format_contract(self.date_start)

    @api.model
    def _get_date_format1(self):
        return self.env['res.functions']._get_date_format_contract(self.date_end)

    @api.model
    def _get_date_format2(self):
        date1 = fields.Date.context_today(self)
        return self.env['res.functions']._get_date_format_contract(date1)

    @api.multi
    def active_contract(self):
        """
        Activamos contrato con fecha de ingreso de empleado y secuencia
        :return:
        """
        number = self._get_name().split('-')
        date_string = self.date_start.strftime('%Y-%m-%d')
        new_name = "%s-%s-%s-%s" % (number[0], date_string[:4], date_string[5:7], number[1])  # Nuevo nombre de contrato
        return self.write({
            'name': new_name,
            'state_customize': 'active'
        })

    @api.multi
    def imprimir_certificate(self):
        """
        Imprimimo certificado
        """
        contract = self.state_customize
        if contract == 'active':
            self.ensure_one()
            return self.env.ref('eliterp_hr_contract.eliterp_action_report_employee_certificate_active').report_action(
                self)
        else:
            self.ensure_one()
            return self.env.ref(
                'eliterp_hr_contract.eliterp_action_report_employee_certificate_inactive').report_action(self)

    @api.multi
    def unlink(self):
        for record in self:
            if record.state_customize != 'draft':
                raise ValidationError(_("No se puede borrar contratos activos o finalizados."))
        return super(Contract, self).unlink()

    @api.multi
    def finalized_contract(self):
        """
        Finalizamos el contrato. TODO: Pendiente acción de finiquito
        :return:
        """
        return self.write({
            'state_customize': 'finalized'
        })

    name = fields.Char('Nº de documento', required=False, copy=False, track_visibility="onchange")  # CM
    test_days = fields.Integer('Días de prueba')  # Configuración RRHH
    antiquity = fields.Integer('Antiguedad (días)', compute='_compute_antiquity', store=True)
    is_trial = fields.Boolean('Es período de prueba?')
    end_trial = fields.Boolean(compute='_compute_end_trial', string='Finalizó prueba?', default=False)
    trial_date_start = fields.Date('Fecha inicio prueba')
    days_for_trial = fields.Integer('Días de prueba', compute='_compute_days_for_trial')
    state_customize = fields.Selection([
        ('draft', 'Nuevo'),
        ('active', 'Activo'),
        ('finalized', 'Finalizado')
    ], 'Estado', default='draft', track_visibility="onchange")
    wage = fields.Monetary('Wage', digits=(16, 2), required=True, track_visibility="onchange",
                           help="Salario bruto mensual del empleado.")  # Configuración RRHH
    document = fields.Binary('Documento', attachment=True)
    document_name = fields.Char('Nombre de documento')
