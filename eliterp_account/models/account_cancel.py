# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MoveCancel(models.TransientModel):
    _name = 'account.move.cancel'

    _description = _("Ventana para cancelar asiento contable")

    description = fields.Text('Descripción', required=True)

    @api.multi
    def confirm_cancel(self):
        """
        Cancelamos asiento contable
        :return: boolean
        """
        move = self.env['account.move'].browse(self._context['active_id'])
        move.reverse_moves(move.date, move.journal_id)
        move.write({
            'state': 'cancel',
            'ref': self.description
        })
        return True


class Move(models.Model):
    _inherit = 'account.move'

    @api.multi
    def button_cancel(self):
        """
        MM: Aumentamos ventana para cancelar asiento contable
        :return dict:
        """
        for move in self:
            if not move.journal_id.update_posted:
                raise UserError(_(
                    'You cannot modify a posted entry of this journal.\nFirst you should set the journal to allow cancelling entries.'))
            for line in move.line_ids:
                if line.full_reconcile_id:
                    raise UserError(_("Hay asientos conciliados, consulte con el departamento Contable."))
        return {
            'name': _("Explique motivo"),
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'account.move.cancel',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }


class InvoiceCancel(models.TransientModel):
    _name = 'account.invoice.cancel'

    _description = _("Ventana para cancelar factura")

    description = fields.Text('Descripción', required=True)

    @api.multi
    def confirm_cancel(self):
        """
        TODO: Operación para cancelar facturas, se crea un nuevo asiento contable.
        Se deja una función para futuras operaciones.
        :return:
        """
        invoice = self.env['account.invoice'].browse(self._context['active_id'])
        invoice.action_cancel()
        invoice._other_actions()
        invoice.write({
            'comment': _("Cancelada") + ": %s" % self.description,
        })
        return True


class Invoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def _other_actions(self):
        """
        Dejamos está función para agregar otras operaciones al cancelar factura
        :return:
        """
        return True

    @api.multi
    def action_cancel(self):
        """
        MM: Cancelamos la factura si no tiene pagos/cobros realizados
        """
        moves = self.env['account.move']
        for inv in self:
            if inv.move_id:
                moves += inv.move_id
            if inv.payment_move_line_ids:
                raise UserError(_(
                    'You cannot cancel an invoice which is partially paid. You need to '
                    'unreconcile related payment entries first.'))
        if moves:
            moves.reverse_moves(self.date_invoice, self.journal_id or False)
        self.write({
            'state': 'cancel'
        })
        return True

    @api.multi
    def action_invoice_cancel(self):
        """
        MM: Abrimos ventana para cancelar factura
        :return:
        """
        if self.filtered(lambda inv: inv.state not in ['draft', 'open']):
            raise UserError(_("Invoice must be in draft or open state in order to be cancelled."))
        context = dict(self._context or {})
        return {
            'name': _("Explique motivo"),
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'account.invoice.cancel',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context,
        }
