# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from datetime import datetime, time
from odoo.exceptions import ValidationError


# TODO: Falta los documentos del empleado (Crear modelo)

class SectorCode(models.Model):
    _name = 'hr.sector.code'

    _description = _('Código sectorial')

    # TODO: Colocar todos los códigos en carga masiva
    name = fields.Char('Código de cargo', size=13, required=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'EL código de cargo debe ser único!'),
    ]


class TypeHistory(models.Model):
    _name = 'hr.type.history'

    _description = _('Tipo de historial')

    name = fields.Char('Nombre', required=True)


class EmployeeHistory(models.Model):
    _name = 'hr.employee.history'
    _rec_name = 'type'
    _description = _('Línea de historial de empleado')

    type = fields.Many2one('hr.type.history', 'Tipo', required=True)
    date = fields.Date('Fecha de registro', default=fields.Date.context_today, required=True)
    date_validity = fields.Date('Fecha de vigencia', default=fields.Date.context_today, required=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado', ondelete="cascade")
    adjunt = fields.Binary('Documento')
    adjunt_name = fields.Char('Nombre de documento')
    comment = fields.Text('Notas')


class EmployeeChildren(models.Model):
    _name = 'hr.employee.children'

    _description = _('Hijos de empleado')

    @api.depends('birthday')
    def _compute_age_children(self):
        """
        Obtenemos la edad de cada hijo
        """
        for children in self:
            age = 0
            if children.birthday:
                age = (datetime.now().date() - datetime.strptime(children.birthday, '%Y-%m-%d').date()).days / 365
            children.age = age

    name = fields.Char('Nombre', required=True)
    documentation_number = fields.Char('Nº de identificación', size=10)
    birthday = fields.Date('Fecha de nacimiento', required=True)
    age = fields.Integer('Edad', compute='_compute_age_children')
    employee_id = fields.Many2one('hr.employee', string='Empleado', ondelete="cascade")


class Employee(models.Model):
    _inherit = 'hr.employee'
    _order = 'surnames'

    @api.onchange('names', 'surnames')
    def _onchange_names(self):
        """
        Actualizamos nombre de empleado utilizando sus nombres y apellidos
        :return: dict
        """
        value = {}
        if self.names and self.surnames:
            value['name'] = self.surnames + ' ' + self.names
            return {'value': value}

    @api.depends('birthday')
    def _compute_age(self):
        """
        Calculamos la edad del empleado
        :return:
        """
        for employee in self:
            age = 0
            if employee.birthday:
                age = (datetime.now().date() - employee.birthday).days / 365
            employee.age = age

    @api.onchange('user_id')
    def _onchange_user(self):
        """
        MM:
        """
        pass

    names = fields.Char('Nombres')
    surnames = fields.Char('Apellidos')
    education_level = fields.Selection([
        ('basic', 'Educación básica'),
        ('graduate', 'Bachiller'),
        ('professional', 'Tercer nivel'),
        ('master', 'Postgrado')
    ], 'Nivel de educación', default='basic')
    blood_type = fields.Selection([
        ('a_most', 'A+'),
        ('a_minus', 'A-'),
        ('b_most', 'B+'),
        ('b_minus', 'B-'),
        ('ab_most', 'AB+'),
        ('ab_minus', 'AB-'),
        ('o_most', 'O+'),
        ('o_minus', 'O-')
    ], 'Tipo de sangre', default='o_most')
    admission_date = fields.Date('Fecha de ingreso', required=True, default=fields.Date.context_today,
                                 groups="hr.group_hr_user")
    extension = fields.Char('Extensión', size=3)
    history_ids = fields.One2many('hr.employee.history', 'employee_id', string='Historial de empleado')
    sector_code = fields.Many2one('hr.sector.code', 'Código sectorial', groups="hr.group_hr_user")
    age = fields.Integer('Edad', compute='_compute_age')
    children_ids = fields.One2many('hr.employee.children', 'employee_id', 'Hijos de empleado')
    bank_id = fields.Many2one('res.bank', 'Banco')
    bank_account = fields.Char('Cuenta bancaria', help="Sirve para futuros pagos de nómina por medio de transferencias.")
    contact_1 = fields.Char('Contacto')
    relationship_1 = fields.Char('Parentesco')
    phone_1 = fields.Char('Teléfono')
    contact_2 = fields.Char('Contacto')
    relationship_2 = fields.Char('Parentesco')
    phone_2 = fields.Char('Teléfono')
