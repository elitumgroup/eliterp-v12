# -*- coding: utf-8 -*-


from odoo.exceptions import ValidationError
from odoo import api, fields, models, _


class CompanyDivision(models.Model):
    _inherit = 'account.company.division'

    def _compute_analytic_account_count(self):
        """
        Calcular la cantidad de centros de costo por división
        :return:
        """
        object_analytic_account = self.env['account.analytic.account']
        for division in self:
            analytic_account_count = len(object_analytic_account.search([('company_division_id', '=', division.id)]))
            division.analytic_account_count = analytic_account_count

    analytic_account_count = fields.Integer('# Centros de costo', compute='_compute_analytic_account_count')


class AnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'
    _rec_name = 'complete_name'
    _order = 'complete_name'

    @api.depends('name', 'group_id.complete_name')
    def _compute_complete_name(self):
        """
        Calculamos el nombre a mostrar dependiendo si tiene padre o no
        :return:
        """
        for analytic in self:
            if analytic.group_id:
                analytic.complete_name = '%s / %s' % (analytic.group_id.complete_name, analytic.name)
            else:
                analytic.complete_name = analytic.name

    @api.model
    def name_create(self, name):
        return self.create({'name': name}).name_get()[0]

    complete_name = fields.Char('Nombre completo', compute='_compute_complete_name', store=True)
    company_division_id = fields.Many2one('account.company.division', string='División', required=True)
