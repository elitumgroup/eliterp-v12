# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from stdnum import ec

LIST_TYPE_DOCUMENTATION = [
    ('0', 'RUC'),
    ('1', 'Cédula'),
    ('2', 'Pasaporte'),
]


class Partner(models.Model):
    _inherit = 'res.partner'

    @api.onchange('documentation_number')
    def _onchange_documentation_number(self):
        """
        Al ir cambiando número de identificación vamos actualizando el campo VAT (Sirve para búsquedas)
        :return object:
        """
        vat = ""
        if self.documentation_number:
            vat = "EC" + self.documentation_number
        res = {'value': {'vat': vat}}
        return res

    @api.constrains('documentation_number')
    def _check_documentation_number(self):
        """
        Validar dígitos de documento y verificar qué no exista empresa.
        Se utiliza la clase ec de la librería stdnum.
        :return:
        """
        if not self.documentation_number:
            return True
        if self.documentation_number and len(self.documentation_number) not in [10, 13]:
            raise ValidationError(_("Debe ingresar 10 o 13 dígitos según tipo de documento."))
        if self.type_documentation == '0':
            ec.ruc.is_valid(self.documentation_number)
        if self.type_documentation == '1':
            ec.ci.is_valid(self.documentation_number)

    @api.one
    @api.depends('documentation_number')
    def _compute_kind_person(self):
        """
        Calculamos el tipo de persona
        :return:
        """
        if not self.documentation_number:
            return
        if len(self.documentation_number) < 3:
            return
        if int(self.documentation_number[2]) <= 6:
            self.kind_person = '6'
        elif int(self.documentation_number[2]) in [6, 9]:
            self.kind_person = '9'
        else:
            self.kind_person = '0'

    @api.model
    def create(self, vals):
        """
        Si es una empresa creada dentro de otra se lo coloca cómo contacto
        :param vals:
        :return:
        """
        if 'parent_id' in vals:
            if vals['parent_id']:
                vals.update({'is_contact': True})
        return super(Partner, self).create(vals)

    @api.multi
    def name_get(self):
        """
        Cambiamos nombre a mostrar de registros
        :return list:
        """
        res = []
        for data in self:
            if data.documentation_number:
                display_name = '{0} [{1}]'.format(data.name, data.documentation_number)
            else:
                display_name = data.name
            res.append((data.id, display_name))
        return res

    type_documentation = fields.Selection(LIST_TYPE_DOCUMENTATION, string='Tipo de identificación')
    documentation_number = fields.Char('Nº Identificación',
                                       copy=False,
                                       size=13,
                                       help='Identificación o registro único de contribuyente (RUC).')
    kind_person = fields.Selection(
        compute='_compute_kind_person',
        selection=[
            ('6', 'Persona Natural'),
            ('9', 'Persona Jurídica'),
            ('0', 'Otro')
        ],
        string='Tipo de persona',
        store=True
    )
    country_id = fields.Many2one('res.country', string='País',
                                 ondelete='restrict',
                                 default=lambda self: self.env.ref('base.ec'))  # CM: Por defecto dejamos Ecuador
    canton_id = fields.Many2one('canton', string='Cantón')
    parish_id = fields.Many2one('parish', string='Parroquia')
    related_party = fields.Selection([('yes', 'Si'),
                                      ('not', 'No')], string='Parte relacionada', default='not', required=True)
    is_company = fields.Boolean(string='Is a Company', default=True,
                                help="Check if the contact is a company, otherwise it is a person")  # CM

    _sql_constraints = [
        (
            'documentation_number', 'unique(documentation_number,company_id)',
            _("Ya existe empresa con este nº de identificación.")),
    ]
