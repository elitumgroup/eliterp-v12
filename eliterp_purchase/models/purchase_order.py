# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Invoice(models.Model):
    _inherit = 'account.invoice'

    # Load all unsold PO lines
    @api.onchange('purchase_id')
    def purchase_order_change(self):
        """
        MM: Le aumentamos división y proyecto
        :return:
        """
        if not self.purchase_id:
            return {}
        if not self.partner_id:
            self.partner_id = self.purchase_id.partner_id.id

        if not self.invoice_line_ids:
            # as there's no invoice line yet, we keep the currency of the PO
            self.currency_id = self.purchase_id.currency_id
        new_lines = self.env['account.invoice.line']
        for line in self.purchase_id.order_line - self.invoice_line_ids.mapped('purchase_line_id'):
            data = self._prepare_invoice_line_from_po_line(line)
            new_line = new_lines.new(data)
            new_line._set_additional_fields(self)
            new_lines += new_line

        self.invoice_line_ids += new_lines
        self.payment_term_id = self.purchase_id.payment_term_id

        # New fields
        self.company_division_id = self.purchase_id.company_division_id.id
        self.project_id = self.purchase_id.project_id.id

        self.env.context = dict(self.env.context, from_purchase_order_change=True)
        self.purchase_id = False
        return {}


class Order(models.Model):
    _inherit = 'purchase.order'

    def _get_name(self):
        company = self.env.user.company_id
        sequence = self.env['ir.sequence'].with_context(force_company=company.id).next_by_code('purchase.order')
        if not sequence:
            raise UserError(
                _("No está definida la secuencia con código 'purchase.order' para compañía: %s") % company.name)
        return sequence

    @api.model
    def create(self, vals):
        """
        MM: Le cambiamos qué al crear una orden de compra deba tener su secuencia
        :param vals:
        :return:
        """
        if vals.get('name', 'New') == 'New':
            sequence = self._get_name()
            vals['name'] = sequence
        return super(Order, self).create(vals)

    name = fields.Char('Order Reference', required=True, index=True, copy=False, default='Nuevo pedido')  # CM
    company_division_id = fields.Many2one('account.company.division', string='División', readonly=True,
                                          states={'draft': [('readonly', False)]}, track_visibility='onchange')
    project_id = fields.Many2one('account.project', string='Proyecto', readonly=True,
                                 states={'draft': [('readonly', False)]}, track_visibility='onchange')
    state = fields.Selection([
        ('draft', 'SDP Borrador'),
        ('sent', 'SDP Enviada'),
        ('approve', 'Orden de compra'),
        ('to approve', 'OCS por aprobar'),
        ('purchase', 'OCS Aprobado'),
        ('done', 'Bloqueado'),
        ('cancel', 'Negado')
    ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')  # CM


class OrderLine(models.Model):
    _inherit = 'purchase.order.line'

    company_division_id = fields.Many2one('account.company.division', string='División',
                                          related='order_id.company_division_id', store=True, readonly=True)
