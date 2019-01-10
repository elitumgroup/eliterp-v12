# -*- coding: utf-8 -*-

from odoo import api, models, fields


class Users(models.Model):
    _inherit = 'res.users'

    @api.model
    def create(self, vals):
        """
        Pasamos contexto 'is_user'
        :param vals:
        :return object:
        """
        self = self.with_context(is_user=True)
        res = super(Users, self).create(vals)
        return res


class Partner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def create(self, vals):
        """
        Realizamos está acción para cuando creeemos un usuario del sistema
        no cree un 'res.partner' (Proveedor o Cliente).
        :param vals:
        :return object:
        """
        context = dict(self._context or {})
        if 'is_user' in context:
            vals.update({'customer': False, 'supplier': False})
        if 'parent_id' in vals:
            if vals['parent_id']:
                vals.update({'is_contact': True})
        return super(Partner, self).create(vals)

    is_contact = fields.Boolean('Es contacto?', default=False,
                                help="Campo para identificar si es un contacto creado desde la empresa.")
