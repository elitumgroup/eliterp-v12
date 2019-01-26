# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_is_zero


class BankReconciliation(models.Model):
    _inherit = 'account.bank.reconciliation'

    @api.multi
    def print_conciliation(self):
        """
        Imprimimos conciliación bancaria
        :return:
        """
        self.ensure_one()
        return self.env.ref('eliterp_account_bank_reconciliation.action_report_bank_reconciliation').report_action(self)

    @api.model
    def _get_data_journal(self):
        """
        Función para obtener cantidad de registros y sumatorias por diarios contable en
        conciliación bancaria
        :return:
        """
        data = []
        for line in self.bank_reconciliation_line:
            aggregate = any(d['journal'] == line.journal for d in data)
            if not aggregate:
                data.append({
                    'journal': line.journal,
                    'name': line.journal.name,
                    'amount': line.amount,
                    'quantity': 1
                })
            else:
                index = list(map(lambda x: x['journal'], data)).index(line.journal)
                data[index].update({
                    'amount': data[index]['amount'] + line.amount,
                    'quantity': data[index]['quantity'] + 1
                })
        return data