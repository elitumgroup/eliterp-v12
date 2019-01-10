# -*- coding: utf-8 -*-

from odoo import fields, models


class Invoice(models.Model):
    _inherit = 'account.journal'

    bank_sequence_id = fields.Many2one('ir.sequence', 'Secuencia de banco', copy=False)
    exit_code = fields.Char('Código', help='Código para identificación en egresos (Cheques, Transferencias, etc.).',
                            size=3)

    _sql_constraints = [
        ('code_exit_code', 'unique (exit_code, company_id)', "El código de cuenta bancaria es único!")
    ]
