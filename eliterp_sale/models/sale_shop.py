# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class Shop(models.Model):
    _name = 'sale.shop'
    _inherit = ['mail.thread']

    _description = "Tiendas"

    @api.multi
    def name_get(self):
        """
        Nombre de registros a mostrar
        :return:
        """
        result = []
        for shop in self:
            result.append((shop.id, "%s: %s" % (shop.company_id.name, shop.name)))
        return result

    @api.multi
    def toggle_active(self):
        """
        Desactivamos o activamos tienda
        :return:
        """
        for record in self:
            record.active = not record.active

    name = fields.Char('Nombre de tienda', required=True, index=True, track_visibility='onchange')
    logo = fields.Binary('Logo')
    type = fields.Selection([('matrix', 'Matriz'), ('office', 'Oficina')], default='office',
                            string="Tipo",
                            required=True)
    state_id = fields.Many2one("res.country.state", string='Provincia', required=True, track_visibility='onchange')
    street = fields.Char('Dirección', required=True, track_visibility='onchange')
    active = fields.Boolean('Activo', default=True)
    company_id = fields.Many2one('res.company', 'Compañía', default=lambda self: self.env.user.company_id.id)

    _sql_constraints = [
        ('name_unique', 'unique (company_id, name)', _("El nombre de tienda deber ser único por compañía!"))
    ]