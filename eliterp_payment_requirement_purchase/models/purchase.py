# -*- coding: utf-8 -*-


from odoo import api, models, _


class Order(models.Model):
    _inherit = 'purchase.order'

    @api.multi
    def action_view_requirement(self):
        action = self.env.ref('eliterp_payment_requirement.action_payment_requirement')
        result = action.read()[0]
        result['context'] = {
            'default_type': 'supplier',
            'default_purchase_id': self.id,
            'default_company_id': self.company_id.id,
            'default_comment': _('Adelanto de compra %s') % self.name,
        }
        res = self.env.ref('eliterp_payment_requirement.view_form_payment_requirement', False)
        result['views'] = [(res and res.id or False, 'form')]
        return result
