# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class ReportHelpFunctions(models.AbstractModel):
    _name = 'hr.report.help.functions'
    _description = _("Funciones de ayuda para reportes contables")

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', string="Compañía", default=lambda self: self.env.user.company_id)


class EmployeeReportPdf(models.AbstractModel):
    _name = 'report.eliterp_hr_reports.report_employee_report'

    @staticmethod
    def _get_civil_status(civil_status):
        """
        Retornamos el estado civil en español (.po)
        :param civil_status:
        :return: string
        """
        if civil_status == 'single':
            return "Soltero(a)"
        elif civil_status == 'married':
            return "Casado(a)"
        elif civil_status == 'widower':
            return "Viudo(a)"
        elif civil_status == 'divorced':
            return "Divorciado(a)"
        else:
            return 'Unión libre'

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        data = []
        arg = [('admission_date', '>=', doc['start_date']), ('admission_date', '<=', doc['end_date'])]
        employees = self.env['hr.employee'].search(arg)
        for employee in employees:
            if employee.id == 1:  # Empleado id=1 no va (Crea el sistema por al realizar la implementación)
                continue
            data.append({
                'name': employee.name,
                'identification_id': employee.identification_id,
                'age': employee.age if employee.birthday else '-',
                'civil_status': self._get_civil_status(employee.marital) if employee.marital else '-',
                'admission_date': employee.admission_date,
                'job_id': employee.job_id.name if employee.job_id else '-',
                'wage': employee.contract_id.wage if employee.contract_id else '-',
                'struct_id': employee.contract_id.struct_id.code if employee.contract_id else '-',
                'bank_account': '{0} [{1}]'.format(employee.bank_account_id.bank_name,
                                                   employee.bank_account_id.acc_number) if employee.bank_account_id else '-'
            })
        return data

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'hr.employee.report',
            'docs': self.env['hr.employee.report'].browse(docids),
            'get_lines': self._get_lines
        }


class EmployeeReport(models.TransientModel):
    _name = 'hr.employee.report'
    _inherit = 'hr.report.help.functions'
    _description = _("Ventana para reporte de empleados")

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        :return:
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr_reports.action_report_employee').report_action(self)


class HolidayReportPdf(models.AbstractModel):
    _name = 'report.eliterp_hr_reports.report_holiday_report'

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        data = []
        arg = [('admission_date', '>=', doc['start_date']), ('admission_date', '<=', doc['end_date']),
               ('company_id', '=', doc['company_id'].id)]
        if doc['type_report'] != 'all':
            arg.append(('id', '=', doc['employee_id'].id))
        for employee in self.env['hr.employee'].search(arg).sorted(key=lambda r: r.name):
            vacations_taken = employee.days_taken
            lines = self.env['hr.leave']._get_holiday_lines(employee)
            data.append({
                'name': employee.name,
                'admission_date': employee.admission_date,
                'holidays': lines
            })
            for line in lines:
                if vacations_taken != 0:
                    if vacations_taken == line['vacations_generated']:
                        line.update({
                            'vacations_taken': vacations_taken,
                            'vacations_available': 0
                        })
                        vacations_taken = 0
                        continue
                    if vacations_taken - line['vacations_generated'] > 0:
                        line.update({
                            'vacations_taken': line['vacations_generated'],
                            'vacations_available': 0
                        })
                        vacations_taken = vacations_taken - line['vacations_generated']
                        continue
                    if vacations_taken - line['vacations_generated'] < 0:
                        line.update({
                            'vacations_taken': vacations_taken,
                            'vacations_available': abs(vacations_taken - line['vacations_generated'])
                        })
                        vacations_taken = 0
                        continue
                if vacations_taken == 0:
                    line.update({
                        'vacations_taken': 0,
                        'vacations_available': line['vacations_generated']
                    })
            if vacations_taken != 0:
                lines[-1].update(
                    {'vacations_available': lines[-1]['vacations_generated'] - vacations_taken})
        return data

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'hr.holiday.report',
            'docs': self.env['hr.holiday.report'].browse(docids),
            'get_lines': self._get_lines
        }


class HolidayReport(models.TransientModel):
    _name = 'hr.holiday.report'
    _inherit = 'hr.report.help.functions'
    _description = _("Ventana para reporte de vacaciones")

    type_report = fields.Selection([('all', 'Todos'), ('one', 'Empleado')], string='Tipo de reporte', default='all',
                                   required=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado')

    @api.multi
    def print_report_pdf(self):
        self.ensure_one()
        return self.env.ref('eliterp_hr_reports.action_report_holiday_report').report_action(self)
