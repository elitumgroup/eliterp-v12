# -*- coding: utf-8 -*-


from odoo import api, fields, models, _


class BankNote(models.Model):
    _inherit = 'account.bank.note'

    @api.multi
    def action_button_cancel(self):
        """
        Abrimos ventana emergente para cancelar nota bancaria
        :return: dict
        """
        return {
            'name': _("Explique la razón"),
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'account.bank.note.cancel',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }


class BankNoteCancel(models.TransientModel):
    _name = 'account.bank.note.cancel'

    _description = _("Ventana para cancelar nota bancaria")

    description = fields.Text('Descripción', required=True)

    @api.multi
    def confirm_cancel(self):
        """
        Confirmamos la cancelación de la nota de bancaria
        :return:
        """
        bank_note = self.env['account.bank.note'].browse(self._context['active_id'])
        move = bank_note.move_id
        move.reverse_moves(move.date, move.journal_id or False)
        move.write({
            'state': 'cancel',
            'ref': self.description
        })
        bank_note.write({'state': 'cancel'})
        return
