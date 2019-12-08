from datetime import datetime, timedelta

import re

from database import get_final_destination
from constants.cn_rail_events import cn_rail_events_dict
from utilities import has_digits


class BNSFTransform:
    def __init__(self, raw_tracing_results, containers_list):
        self.html = raw_tracing_results
        self.containers_list = containers_list

    @staticmethod
    def get_container_number(tag):
        return '{}{}'.format((tag.find('td', {'id': 'UnitInit'})).text,
                             (tag.find('td', {'id': 'UnitNumber'})).text)

    @staticmethod
    def get_estimated_arrival_date(tag):
        eta = tag.find('td', {'id': 'EstDRMPDate'}).text
        if eta:
            return eta

    @staticmethod
    def get_last_location(tag):
        return ', '.join((tag.find('td', {'id': 'LastHub'})).text.split())

    @staticmethod
    def get_final_destination(tag):
        return ', '.join((tag.find('td', {'id': 'DestHub'})).text.split())

    @staticmethod
    def get_last_free_day(tag):
        last_free_day = (tag.find('td', {'id': 'LastFreeDay'})).text
        if has_digits(last_free_day):
            return last_free_day

    def get_tracing_result_list(self):
        tracing_results_list = []
        containers_list = self.containers_list
        container_tags = self.html.find_all('tr', {'id': 'dllRowStyle'})

        for i, tag in enumerate(container_tags):
            last_location = self.get_last_location(tag)
            eta = self.get_estimated_arrival_date(tag)
            final_destination = self.get_final_destination(tag)
            last_free_day = self.get_last_free_day(tag)

            tracing_result_dict = dict(
                container_number=containers_list[i],
                final_destination=final_destination,
                last_location=last_location,
                timestamp=datetime.now()
            )

            if last_free_day:
                tracing_result_dict.update(dict(last_free_day=last_free_day,
                                                most_recent_event='Grounded LFD: {}'.format(last_free_day),
                                                current_status='Grounded'))
            elif not eta and not final_destination:
                tracing_result_dict.update(dict(most_recent_event='Outgated', current_status='Outgated'))
            elif not eta:
                tracing_result_dict.update(dict(current_status='Pending'))
            else:
                tracing_result_dict.update(dict(eta=eta,
                                                most_recent_event='Last seen in {}'.format(last_location),
                                                scheduled_event='Arrival in {} ETA: {}'.format(final_destination, eta),
                                                current_status='On Route'))

            tracing_results_list.append(tracing_result_dict)

        return tracing_results_list


class CanadianNationalTransform:
    def __init__(self, raw_tracing_results):
        self.raw_results_dict = raw_tracing_results
        self.location_html_index = 0
        self.eta_html_index = 1

    @staticmethod
    def extract_eta(eta_str, starting_index):
        now = datetime.now()
        last_index = starting_index + 4
        final_eta_datetime = datetime.strptime(eta_str[starting_index:last_index], '%m%d')
        return datetime.strftime(final_eta_datetime, '%m/%d/{}'.format(now.year))

    def get_recent_event_description(self, html_list):
        rail_status_key = html_list[self.location_html_index].split()[7]
        event_datetime_str = self.remove_at(4, (''.join(html_list[self.location_html_index].split()[4:6])))
        raw_event_datetime = datetime.strptime(event_datetime_str, '%m%d%H%M')
        event_datetime = datetime.strftime(raw_event_datetime, '%m/%d/{} %H:%M'.format(datetime.now().year))
        return dict(description=cn_rail_events_dict[rail_status_key], datetime=event_datetime)

    def get_most_recent_location(self, html_list):
        location_list = html_list[self.location_html_index].split()[2:4]
        return ', '.join(location_list)

    def get_next_destination(self, html_list):
        location_list = html_list[self.location_html_index].split()[9:11]
        return ', '.join(location_list)

    def get_estimated_arrival_date(self, html_list):
        global eta
        tracing_result_list = html_list[self.eta_html_index].split()
        first_int_index = re.search("\d", tracing_result_list[-1])
        if first_int_index and tracing_result_list[-1].isdigit():
            eta = self.extract_eta(tracing_result_list[-1], first_int_index.start())
        elif first_int_index and not tracing_result_list[-1].isdigit():
            eta = ''
        elif not first_int_index:
            eta = ''
        else:
            first_int_index = re.search("\d", tracing_result_list[-2])
            eta = self.extract_eta(tracing_result_list[-2], first_int_index.start())

        return eta

    @staticmethod
    def get_last_free_day(final_eta):
        final_eta_datetime = datetime.strptime(final_eta, '%m/%d/%Y')
        last_free_day_datetime = final_eta_datetime + timedelta(days=2)
        return dict(last_free_day=datetime.strftime(last_free_day_datetime, '%m/%d/%Y'))

    @staticmethod
    def remove_at(index, s):
        return s[:index] + s[index + 1:]

    def get_tracing_results_list(self):
        tracing_results_list = []
        for k, v in self.raw_results_dict.items():
            most_recent_location = self.get_most_recent_location(v)
            if 'RECORD' not in most_recent_location:
                eta = self.get_estimated_arrival_date(v)
                next_destination = self.get_next_destination(v)
                recent_event_description = self.get_recent_event_description(v)
                tracing_result_dict = dict(
                    container_number=k,
                    recent_event_description=recent_event_description['description'],
                    recent_event_datetime=recent_event_description['datetime'],
                    most_recent_event='{} {} {}'.format(recent_event_description['description'],
                                                        most_recent_location,
                                                        recent_event_description['datetime']),
                    most_recent_location=most_recent_location,
                    timestamp=datetime.now()
                )

                if 'constructive' not in recent_event_description['description']:
                    tracing_result_dict.update(dict(
                        scheduled_event='Arrival in {} ETA: {}'.format(next_destination, eta),
                        next_destination=next_destination,
                        eta=eta,
                        current_status='On Route'))
                elif 'constructive' in recent_event_description['description']:
                    last_free_day = self.get_last_free_day(tracing_result_dict['recent_event_datetime'].split()[0])
                    tracing_result_dict.update(dict(current_status='Grounded',
                                                    most_recent_event='Grounded'))
                    tracing_result_dict.update(last_free_day)

                tracing_results_list.append(tracing_result_dict)
            else:
                tracing_results_list.append(dict(container_number=k,
                                                 timestamp=datetime.now(),
                                                 current_status='Pending'))

        return tracing_results_list


class CanadianPacificTransform:
    def __init__(self, raw_tracing_results, containers_list):
        self.raw_html = raw_tracing_results
        self.containers_list = containers_list

    def get_estimated_arrival_date(self, _list):
        if _list[7].text.strip():
            return dict(eta=_list[7].text.strip()[1:11])

    def get_last_free_day(self, _list):
        if _list[-2].text.strip():
            return dict(last_free_day=_list[-2].text.strip().split()[0])

    def get_tracing_results_list(self):
        tracing_results_table = self.raw_html.find('table', {'id': 'rowTable'})
        tracing_results_rows = tracing_results_table.find_all('tr')
        tracing_results_list = []

        for i, row in enumerate(tracing_results_rows[1:]):
            tracing_results_columns = row.find_all('td')

            tracing_result_dict = dict(
                container_number=self.containers_list[i],
                timestamp=datetime.now(),
            )

            last_free_day = self.get_last_free_day(tracing_results_columns)
            eta = self.get_estimated_arrival_date(tracing_results_columns)

            if not last_free_day and not eta:
                tracing_result_dict.update(dict(current_status='Pending'))
            elif last_free_day:
                tracing_result_dict.update(dict(
                    most_recent_event=tracing_results_columns[4].text.strip()),
                    current_status='Grounded')
                tracing_result_dict.update(last_free_day)
            else:
                tracing_result_dict.update(dict(
                    most_recent_event=tracing_results_columns[4].text.strip(),
                    current_event=tracing_results_columns[3].text.strip(),
                    scheduled_event='Arrival in {} ETA: {}'.format(get_final_destination(self.containers_list[i]),
                                                                   eta['eta']),
                    current_status='On Route',
                    )
                )

                tracing_result_dict.update(eta)
            tracing_results_list.append(tracing_result_dict)

        return tracing_results_list


class CSXTransform:
    def __init__(self, raw_tracing_results, containers_dict):
        self.raw_results_list = raw_tracing_results
        self.containers_mapping_dict = containers_dict

    @staticmethod
    def get_estimated_arrival_date(_dict):
        try:
            if _dict['tripPlan']:
                return dict(eta=_dict['tripPlan']['updatedEtn'].split('T')[0], current_status='On Route')
        except KeyError:
            return

    @staticmethod
    def get_most_recent_event(_dict):
        try:
            if _dict['lastReportedEvent']:
                event_description = _dict['lastReportedEvent']['eventTypeDescription']
                city = _dict['lastReportedEvent']['city']
                state = _dict['lastReportedEvent']['state']
                timestamp = _dict['lastReportedEvent']['actualDateTime']
                return dict(most_recent_event='{} {}, {} {}'.format(event_description, city, state, timestamp))
        except KeyError:
            return

    @staticmethod
    def check_if_outgated(_dict):
        try:
            if 'OUTGATE' in _dict['errorCode']:
                return dict(most_recent_event='Outgated', current_status='Outgated')
        except KeyError:
            return

    @staticmethod
    def get_last_free_day(_dict):
        try:
            if _dict['referenceNumber']:
                if 'NOTIFIED' in _dict['shipmentStatus']:
                    try:
                        return dict(most_recent_event='Grounded',
                                    last_free_day=_dict['premise']['lastFreeDate'],
                                    current_status='Grounded')
                    except KeyError:
                        return
        except KeyError:
            return

    def get_tracing_results_list(self):
        tracing_results_list = []

        for result in self.raw_results_list:
            container_key = result['equipment']['equipmentID']['equipmentInitial'] + \
                            result['equipment']['equipmentID']['equipmentNumber']
            container_number = self.containers_mapping_dict[container_key]

            tracing_result = dict(
                container_number=container_number,
                timestamp=datetime.now(),
            )

            outgate_verified = self.check_if_outgated(result)
            last_free_day = self.get_last_free_day(result)
            eta = self.get_estimated_arrival_date(result)
            most_recent_event = self.get_most_recent_event(result)

            if outgate_verified:
                tracing_result.update(outgate_verified)
            elif last_free_day:
                tracing_result.update(last_free_day)
            elif eta and most_recent_event:
                scheduled_event = 'Arrival in {} ETA: {}'.format(get_final_destination(container_number), eta['eta'])
                tracing_result.update(most_recent_event)
                tracing_result.update(eta)
                tracing_result.update(dict(scheduled_event=scheduled_event))
            else:
                tracing_result.update(dict(current_status='Pending'))

            tracing_results_list.append(tracing_result)

        return tracing_results_list

# class NorfolkSouthernTransform:
#     def __init__(self, raw_results_list, containers_list):
#         self.raw_results_list = raw_results_list
#         self.containers_list = containers_list
#
#     def get_most_recent_event(self, _dict, index, event_codes):
#         event_code_key = _dict['result']['validEquipmentDataList'][index]['lastAAREventCode']
#         event_description = event_codes[event_code_key]
#         location = _dict['result']['validEquipmentDataList'][index]['currentTerminalLocation']
#         event_date_time = _dict['result']['validEquipmentDataList'][index]['eventTime']
#         return '{} {} {}'.format(event_description, location, event_date_time)
#
#     def get_eta(self, _dict, index):
#         return _dict['result']['validEquipmentDataList'][index]['etg']
#
#     def get_last_free_day(self, _dict, index):
#         return _dict['result']['validEquipmentDataList'][index]['lastFreeDateTime']
#
#     def get_scheduled_event(self, _dict, index):
#         eta = self.get_eta(_dict, index)
#         location = _dict['result']['validEquipmentDataList'][index]['onlineDestination']
#         return 'On route to {} ETA: {}'.format(location, eta)
#
#     def get_tracing_results_list(self):
#
#         for i, container in enumerate(self.containers_list):
#
#             tracing_result = dict(
#                 container_number=container,
#                 timestamp=datetime.now(),
#             )
#
#             eta = self.get_eta(self.raw_results_list, i)


class UnionPacificTransform:
    def __init__(self, raw_tracing_results, containers_list):
        self.containers_list = containers_list
        self.raw_tracing_results_list = raw_tracing_results

    def get_last_free_day(self, _dict):
        try:
            storage_charge_date_str = _dict['fields']['storage_details']['storageChargeBegins'].split('T')[0]
            storage_charge_datetime = datetime.strptime(storage_charge_date_str, '%Y-%m-%d')
            last_free_date = storage_charge_datetime - timedelta(days=1)
            return dict(last_free_day=str(datetime.strftime(last_free_date, '20%y-%m-%d')), current_status='Grounded')
        except TypeError:
            return

    def get_outgate_date(self, _dict):
        if 'Delivered to Truck Line' in _dict['fields']['accomplished_events'][0]['name']:
            outgate_date_str = _dict['fields']['accomplished_events'][0]['dateTime'].split('T')[0]
            outgate_date_object = datetime.strptime(outgate_date_str, '%Y-%m-%d')
            return dict(current_status='Outgated',
                        most_recent_event='Outgated on {}'.format(datetime.strftime(outgate_date_object, '%m/%d/%y')))

    def get_container_eta(self, _dict):
        arrival_eta_str = _dict['fields']['scheduled_events'][0]['dateTime'].split('T')[0]
        arrival_eta_datetime = datetime.strptime(arrival_eta_str, '%Y-%m-%d')
        return dict(eta=datetime.strftime(arrival_eta_datetime, '%Y-%m-%d'), current_status='On Route')

    def get_uprr_event(self, _dict, event):
        event_dict = {
            'past': 'accomplished_events',
            'scheduled': 'scheduled_events',
        }
        try:
            return '{}, {}\t{} {}'.format(
                _dict['fields'][event_dict[event]][0]['location']['city'],
                _dict['fields'][event_dict[event]][0]['location']['state'],
                _dict['fields'][event_dict[event]][0]['name'],
                _dict['fields'][event_dict[event]][0]['dateTime'])
        except (IndexError, KeyError):
            pass

    def get_tracing_results_list(self):

        traced_containers_list = []
        for container in self.raw_tracing_results_list:
            traced_containers_list.append({
                'fields': {
                    'storage_details': container['storageCharges'],
                    'scheduled_events': container['scheduledEvents'],
                    'accomplished_events': container['accomplishedEvents'],
                    'billed_status': container['billedStatus'],
                }
            }
            )
        traced_containers_dict = dict(zip(self.containers_list, traced_containers_list))
        tracing_results_list = []

        for k, v in traced_containers_dict.items():
            scheduled_event = self.get_uprr_event(v, 'scheduled')
            past_event = self.get_uprr_event(v, 'past')
            billed_status = v['fields']['billed_status']

            tracing_result = dict(
                container_number=k,
                timestamp=datetime.now()
            )

            if 'Pending' in billed_status:
                tracing_result.update(dict(current_status='Pending'))
            elif 'Van Notification' in past_event:
                tracing_result.update(self.get_last_free_day(v))
                tracing_result.update(most_recent_event=past_event)
            elif 'Delivered to Truck Line' in past_event:
                tracing_result.update(self.get_outgate_date(v))
            elif 'Placed at Ramp' in past_event:
                tracing_result.update(most_recent_event=past_event,
                                      current_status='Grounding',
                                      eta=past_event.split()[-1].split('T')[0])
            elif 'Scheduled Departure' in scheduled_event:
                tracing_result.update(most_recent_event=past_event,
                                      scheduled_event=scheduled_event,
                                      current_status='On Route',
                                      eta='12/31/1950')
            else:
                eta_keywords = ['Estimated', 'Arrival', 'Scheduled']
                try:
                    if any(keyword in scheduled_event for keyword in eta_keywords):
                        tracing_result.update(self.get_container_eta(v))
                        tracing_result.update(most_recent_event=past_event)
                        tracing_result.update(scheduled_event=scheduled_event)
                except TypeError:
                    pass

            tracing_results_list.append(tracing_result)

        return tracing_results_list
