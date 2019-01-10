# -*- coding: utf-8 -*-


from odoo import fields, api, models, _


class Move(models.Model):
    _inherit = 'account.move.line'

    project_id = fields.Many2one('account.project', string='Proyecto',
                                 related='move_id.project_id', store=True)


class Move(models.Model):
    _inherit = 'account.move'

    project_id = fields.Many2one('account.project', string='Proyecto', readonly=True,
                                 states={'draft': [('readonly', False)]}, track_visibility='onchange')


class Invoice(models.Model):
    _inherit = 'account.invoice'

    project_id = fields.Many2one('account.project', string='Proyecto', readonly=True,
                                 states={'draft': [('readonly', False)]}, track_visibility='onchange')


class CompanyDivision(models.Model):
    _inherit = 'account.company.division'

    def _compute_project_count(self):
        """
        Calcular la cantidad de proyecto por división
        :return:
        """
        object_project = self.env['account.project']
        for division in self:
            project_count = len(object_project.search([('company_division_id', '=', division.id)]))
            division.project_count = project_count

    project_count = fields.Integer('# Proyectos', compute='_compute_project_count')


class Project(models.Model):
    _name = 'account.project'
    _description = 'Proyecto'
    _inherit = ['mail.thread']

    @api.multi
    def name_get(self):
        """
        Cambiamos nombre a mostrar de registros
        :return list:
        """
        res = []
        for data in self:
            res.append((data.id, "[{0}] {1}".format(data.code, data.name)))
        return res

    company_division_id = fields.Many2one('account.company.division', string='División', required=True)
    name = fields.Char('Nombre', index=True, required=True, track_visibility='onchange')
    code = fields.Char(required=True, string="Código", track_visibility='onchange')
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.user.company_id)

    _sql_constraints = [
        ('name_uniq', 'unique (name, company_id)',
         'El nombre debe ser único por compañía!'),
        ('code_uniq', 'unique (code)',
         'El código debe ser único!')
    ]
