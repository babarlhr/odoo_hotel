# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    John W. Viloria Amaris <john.viloria.amaris@gmail.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import logging
import pytz

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import api, models, fields
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF

_logger = logging.getLogger(__name__)

def extract_date(date):
    try:
        return datetime.strptime(date, DTF).date()
    except:
        return False

def str_to_datetime(strdate):
    return datetime.strptime(strdate, DTF)

class RoomReservationSummary(models.Model):

    _inherit = 'room.reservation.summary'

    @api.model
    def default_get(self, fields):
        if self._context is None:
            self._context = {}
        res = super(RoomReservationSummary, self).default_get(fields)
        res.update({'date_from': datetime.today().strftime(DTF)})
        return res

    def _lctime_to_utctime(self, strdate):
        if self._context is None:
            self._context = {}
        user_tz = pytz.timezone(self._context['tz']) if 'tz' in self._context \
                                      else pytz.timezone('America/Bogota')
        dt = datetime.strptime(strdate, DTF)
        user_dt = user_tz.localize(dt, is_dst=None)
        return user_dt.astimezone(pytz.utc).strftime(DTF) or False

    def _utc_to_lctime(self, strdate):
        if self._context is None:
            self._context = {}
        user_tz = pytz.timezone(self._context['tz']) if 'tz' in self._context \
                                else pytz.timezone('America/Bogota')
        date = str_to_datetime(strdate)
        today = datetime.today()
        tzoffset = user_tz.utcoffset(today)
        date = date + tzoffset
        return date.strftime(DTF)

    def _get_convention_image(self):
        image = self.env['ir.attachment'].search(
                [('name','=','summary_convention.png')]
                )
        return image.datas

    date_from = fields.Datetime('Date From', default=datetime.today())
    date_to = fields.Datetime('Date To', default=datetime.today()
                              + relativedelta(days=14))
    convention_image = fields.Binary('Conventions', readonly=False,
                                      default=_get_convention_image)

    def get_reservation_draft(self, room, date, room_info):
        date_end = self._lctime_to_utctime(date[:10] + ' 15:00:00')
        date = self._lctime_to_utctime(date)
        state_dict = {'draft':'Draft',
                      'confirm':'Reserved',
                      'done':'Occupied'}
        records = self.env['hotel.reservation'].search([
                                      ('checkin','<=',date),
                                      ('checkout','>=',date_end)
                                     ])
        for record in records:
            if record.reservation_line:
                for line in record.reservation_line:
                    if room.name == line.name and \
                            record.state not in ['done','cancel']:
                        _logger.critical('ROOM NAME: %s-%s'%(room.name,date))
                        checkout_date = datetime.strptime(
                                        record.checkout, DTF)
                        checkout_date = str_to_datetime(self._utc_to_lctime(
                                        checkout_date.strftime(DTF)))\
                                        .strftime('%Y-%m-%d  %I:%M %p')
                        room_info['tooltip_info'] = '%s\nCheckout: %s\n\
                                    Reserva: %s'%(record.partner_id.name, 
                                    checkout_date, record.reservation_no)
                        room_info['reservation'] = record.id
                        return state_dict[record.state], record.id
        return False, False

    def get_occupied_room(self, room, date, room_info):
        date_end = self._lctime_to_utctime(date[:10] + ' 15:00:00')
        date = self._lctime_to_utctime(date)
        records = self.env['hotel.folio.line'].search([
                                      ('checkin_date','<=',date),
                                      ('checkout_date','>=',date_end)
                                     ])
        for record in records:
            if record.product_id.name == room.name and \
                    record.folio_id.state not in ['done','cancel']:
                checkout_date = datetime.strptime(
                        record.folio_id.checkout_date, DTF)
                checkout_date = str_to_datetime(self._utc_to_lctime(
                                checkout_date.strftime(DTF)))\
                                .strftime('%Y-%m-%d  %I:%M %p')
                room_info['folio_id'] = record.folio_id.id
                room_info['tooltip_info'] = '%s\nCheckout: %s\n\
                            Folio: %s'%(record.folio_id.partner_id.name, 
                            checkout_date, record.folio_id.name)
                return 'Occupied'
        return False

    def get_block_room(self, room, date, room_info):
        records = self.env['hotel.room.maintenance'].search([
                                      ('block_start_time','<=',date),
                                      ('block_end_time','>=',date)
                                     ])
        for record in records:
            if record.room_no.name == room.name:
                room_info['tooltip_info'] = record.description
                return 'Blocked'
        return False

    @api.onchange('date_from', 'date_to')
    def get_room_summary(self):
        '''
        @param self: object pointer
         '''
        res = {}
        all_detail = []
        room_obj = self.env['hotel.room']
        reservation_line_obj = self.env['hotel.room.reservation.line']
        date_range_list = []
        main_header = []
        summary_header_list = ['Rooms']
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                raise except_orm(_('User Error!'),
                                 _('Please Check Time period Date \
                                 From can\'t be greater than Date To !'))
            d_frm_obj = datetime.strptime(self._utc_to_lctime(
                                          self.date_from), DTF)
            d_to_obj = datetime.strptime(self._utc_to_lctime(
                                          self.date_to), DTF)
            temp_date = d_frm_obj
            while(temp_date <= d_to_obj):
                val = ''
                val = (str(temp_date.strftime("%a")) + ' ' +
                       str(temp_date.strftime("%b")) + ' ' +
                       str(temp_date.strftime("%d")))
                summary_header_list.append(val)
                date_range_list.append(temp_date.strftime
                                       (DTF))
                temp_date = temp_date + timedelta(days=1)
            all_detail.append(summary_header_list)
            room_ids = room_obj.search([])
            all_room_detail = []
            for room in room_ids:
                room_detail = {}
                room_list_stats = []
                room_detail.update({'name': room.name or ''})
                for chk_date in date_range_list:
                    folio_id = False
                    tooltip_info = False
                    folio_data = {'folio_id': False, 'partner_id':False,
                                  'checkout_date':False, 'state': False,
                                  'partner_name': False}
                    room_info = {}
                    reservation_id = False
                    state_draft, reservation_id = self.get_reservation_draft(
                                                  room, chk_date, room_info)
                    state_occupied = self.get_occupied_room(room, chk_date, 
                                                            room_info)
                    state_blocked = self.get_block_room(room, chk_date, 
                                                        room_info)
 
                    state = 'Free'
                    if state_occupied:
                        state = state_occupied
                        folio_id = folio_data['folio_id']
                    elif state_blocked:
                        state = state_blocked
                    elif state_draft:
                        state = state_draft
                    room_info['state'] = state
                    room_info['date'] = chk_date
                    room_info['room_id'] = room.id
                    room_list_stats.append(room_info)
                room_detail.update({'value': room_list_stats})
                all_room_detail.append(room_detail)
            main_header.append({'header': summary_header_list})
            self.summary_header = str(main_header)
            self.room_summary = str(all_room_detail)
        return res


class HotelSelectorWizard(models.TransientModel):
    _name = 'hotel.selector.wizard'

    def _lctime_to_utctime(self, strdate):
        if self._context is None:
            self._context = {}
        user_tz = pytz.timezone(self._context['tz']) if 'tz' in self._context \
                                      else pytz.timezone('America/Bogota')
        dt = datetime.strptime(strdate, DTF)
        user_dt = user_tz.localize(dt, is_dst=None)
        return user_dt.astimezone(pytz.utc).strftime(DTF) or False

    check_in = fields.Datetime('Date', required=True)
    room_id = fields.Many2one('hotel.room', 'Room', required=True)

    @api.multi
    def housekeeping_service(self):
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'hotel.housekeeping',
                'view_type': 'form',
                'view_mode': 'form',
                #'res_id': 'quick_room_reservation_form_view',
                'target': 'new',
                'flags': {'form': {'action_buttons': True}},
            }

    @api.multi
    def new_reservation(self):
        room_id = self.room_id.id
        checkin_date = self.check_in
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'hotel.reservation',
                'view_type': 'form',
                'view_mode': 'form',
                #'res_id': 'quick_room_reservation_form_view',
                'context': {'room_id': room_id,
                            'checkin_date': checkin_date},
                'target': 'new',
                'flags': {'form': {'action_buttons': True}},
            }

    @api.multi
    def new_checkin(self):
        room_id = self.room_id.id
        checkin_date = self.check_in
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'hotel.folio',
                'view_type': 'form',
                'view_mode': 'form',
                #'res_id': 'quick_room_reservation_form_view',
                'context': {'room_id': room_id,
                            'checkin_date': checkin_date},
                'target': 'new',
                'flags': {'form': {'action_buttons': True}},
            }

    @api.multi
    def room_blocking(self):
        room_id = self.room_id.id
        block_date = self.check_in
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'hotel.room.maintenance',
                'view_type': 'form',
                'view_mode': 'form',
                'context': {'room_no': room_id,
                            'date': block_date},
                'target': 'new',
                'flags': {'form': {'action_buttons': True}},
            }

    @api.model
    def default_get(self, fields):
        """
        To get default values for the object.
        @param self: The object pointer.
        @param fields: List of fields for which we want default values
        @return: A dictionary which of fields with values.
        """
        if self._context is None:
            self._context = {}
        res = super(HotelSelectorWizard, self).default_get(fields)
        if self._context:
            keys = self._context.keys()
            if 'date' in keys:
                date = self._lctime_to_utctime(self._context['date'])
                date = (str_to_datetime(date) + \
                        relativedelta(minutes=3)).strftime(DTF)
                res.update({'check_in': date})
            if 'room_id' in keys:
                roomid = self._context['room_id']
                res.update({'room_id': int(roomid)})
        return res

class QuickRoomReservation(models.TransientModel):
    _inherit = 'quick.room.reservation'

    @api.model
    def default_get(self, fields):
        """
        To get default values for the object.
        @param self: The object pointer.
        @param fields: List of fields for which we want default values
        @return: A dictionary which of fields with values.
        """
        if self._context is None:
            self._context = {}
        res = super(QuickRoomReservation, self).default_get(fields)
        if self._context:
            keys = self._context.keys()
            if 'date' in keys:
                res.update({'check_in': self._context['date']})
            if 'room_id' in keys:
                roomid = self._context['room_id']
                res.update({'room_id': int(roomid)})
        return res

