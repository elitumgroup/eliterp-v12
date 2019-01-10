# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo import api, fields, models, _


class Move(models.Model):
    _inherit = 'account.move'

    @api.multi
    def print_move(self):
        """
        TODO: Imprimimos asiento contable
        :return:
        """
        self.ensure_one()
        return self.env.ref('eliterp_account.action_report_account_move').report_action(self)

    @api.model
    def create(self, vals):
        """
        Al crear asiento contable validamos el período contable
        :param vals:
        :return:
        """
        if 'date' in vals:
            self.env['account.period'].valid_period(vals['date'])
        res = super(Move, self).create(vals)
        return res

    @api.multi
    def post(self, invoice=False):
        """
        MM: Le agregamos el 'my_moves' al contexto para poder colocar nuevo nombre.
        :return:
        """
        self._post_validate()
        for move in self:
            move.line_ids.create_analytic_lines()
            if move.name == '/':
                new_name = False
                journal = move.journal_id

                if invoice and invoice.move_name and invoice.move_name != '/':
                    new_name = invoice.move_name
                else:
                    if 'my_moves' in self._context:
                        if 'internal_voucher' in self._context:
                            # Secuencia por compañía
                            new_name = self.env['ir.sequence'].with_context(force_company=self.company_id.id).next_by_code('internal.process')
                            if not new_name:
                                raise UserError(_('Definir una secuencia para procesos internos (internal.process).'))
                        if 'move_name' in self._context:
                            new_name = self._context['move_name']
                    else:
                        if journal.sequence_id:
                            # If invoice is actually refund and journal has a refund_sequence then use that one or use the regular one
                            sequence = journal.sequence_id
                            if invoice and invoice.type in ['out_refund', 'in_refund'] and journal.refund_sequence:
                                if not journal.refund_sequence_id:
                                    raise UserError(_('Please define a sequence for the credit notes'))
                                sequence = journal.refund_sequence_id

                            new_name = sequence.with_context(ir_sequence_date=move.date).next_by_id()
                        else:
                            raise UserError(_('Please define a sequence on the journal.'))

                if new_name:
                    move.name = new_name

            if move == move.company_id.account_opening_move_id and not move.company_id.account_bank_reconciliation_start:
                # For opening moves, we set the reconciliation date threshold
                # to the move's date if it wasn't already set (we don't want
                # to have to reconcile all the older payments -made before
                # installing Accounting- with bank statements)
                move.company_id.account_bank_reconciliation_start = move.date

        return self.write({'state': 'posted'})

    @api.multi
    def _reverse_move(self, date=None, journal_id=None, auto=None):
        """
        ME: Aumentamos el campo 'reversed' al diccionario, para saber qué el asiento está reversado y
        así poder identificar en reportes u otro uso.
        :param date:
        :param journal_id:
        :return dict:
        """
        reversed_move = super(Move, self)._reverse_move(date, journal_id)
        reversed_move['reversed'] = True
        return reversed_move

    date = fields.Date(required=True, readonly=True, states={'draft': [('readonly', False)]}, index=True, default=fields.Date.context_today)  # CM
    state = fields.Selection([('draft', 'Sin validar'),
                              ('posted', 'Validado'),
                              ('cancel', 'Cancelado')],
                             string='Estado', required=True, readonly=True, copy=False, default='draft')  # CM
    reversed = fields.Boolean('Reversado?', default=False, copy=False)
