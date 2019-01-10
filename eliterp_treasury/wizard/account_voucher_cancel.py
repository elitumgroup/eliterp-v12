# -*- coding: utf-8 -*-


from odoo import api, fields, models, _


class Voucher(models.Model):
    _inherit = 'account.voucher'

    @api.multi
    def action_button_cancel(self):
        """
        TODO: Abrimos ventana emergente para cancelar comprobante
        :return: dict
        """
        context = dict(self._context or {})
        if 'voucher_type' not in context:
            del context['form_view_ref']
            context['voucher_type'] = 'purchase'
            context['default_voucher_type'] = 'purchase'
            context['params']['action'] = 517
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
