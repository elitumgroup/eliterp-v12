# -*- coding: utf-8 -*-


from odoo.exceptions import ValidationError
from odoo import api, fields, models, _


class Project(models.Model):
    _inherit = 'account.project'

    analytic_account_ids = fields.Many2many('account.analytic.account', 'project_analytic_account_rel', 'project_id',
                                            'analytic_account_id',
                                            string='Centros de costo')


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
    project_ids = fields.Many2many('account.project', 'project_analytic_account_rel', 'analytic_account_id',
                                   'project_id',
                                   string='Proyectos')
