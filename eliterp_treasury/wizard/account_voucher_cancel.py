# -*- coding: utf-8 -*-


from odoo import api, fields, models, _


class Voucher(models.Model):
    _inherit = 'account.voucher'

    @api.multi
    def action_button_cancel(self):
        """
        Abrimos ventana emergente para cancelar comprobante
        :return: dict
        """
        return {
            'name': _("Explique la razón"),
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'account.voucher.cancel',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }


class VoucherCancel(models.TransientModel):
    _name = 'account.voucher.cancel'

    _description = _("Ventana para cancelar comprobante")

    description = fields.Text('Descripción', required=True)

    @api.multi
    def confirm_cancel(self):
        """
        Confirmamos la cancelación del comprobante
        :return:
        """
        voucher = self.env['account.voucher'].browse(self._context['active_id'])
        move = voucher.move_id
        move.reverse_moves(move.date, move.journal_id or False)
        move.write({
            'state': 'cancel',
            'ref': self.description
        })
        voucher.pay_order_id.write({'state': 'cancel'})
        voucher.write({'state': 'cancel'})
        return
