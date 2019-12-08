from collections import defaultdict
import json

from airtable import Airtable

data_sources = json.load(open('data_config.json'))['data_sources']['airtable']
airtable_containers_sheet = Airtable(data_sources['base_key'], 'Containers', data_sources['api_key'])


def get_containers_from_db(view_name):
    containers_by_view_dict = defaultdict(list)

    if view_name == 'Pending ANs':
        airtable_records = airtable_containers_sheet.get_all(
            fields=['Container', 'MBL'],
            view=view_name
        )

        for record in airtable_records:
            container = record['fields']['Container']
            containers_by_view_dict[record['fields']['MBL'][0][:4]].append(container)

    elif view_name == 'Tracing View':
        airtable_records = airtable_containers_sheet.get_all(fields=['Container', 'Container Yard'], view=view_name)
        for record in airtable_records:
            container = record['fields']['Container']
            containers_by_view_dict[record['fields']['Container Yard'][0]].append(container)

    return containers_by_view_dict


def update_container_tracing(container_number, tracing_results, tracing_type=('rail', 'ssl')):
    record = airtable_containers_sheet.search('Container', container_number)

    if 'rail' in tracing_type:
        fields = {'Rail Tracing': tracing_results}
    else:
        fields = {'SSL Tracing': tracing_results}

    airtable_containers_sheet.update(record[0]['id'], fields)


def update_container_lfd(container_number, lfd):
    record = airtable_containers_sheet.search('Container', container_number)
    fields = {'LFD': lfd}
    airtable_containers_sheet.update(record[0]['id'], fields)


def update_container_eta(container_number, eta, eta_type=('rail', 'ssl')):
    record = airtable_containers_sheet.search('Container', container_number)
    if 'rail' in eta_type:
        fields = {'Rail ETA': eta}
    else:
        fields = {'Vessel ETA': eta}
    airtable_containers_sheet.update(record[0]['id'], fields)


def get_mbl_from_container(container_number):
    record = airtable_containers_sheet.search('Container', container_number)
    return record[0]['fields']['MBL'][0]


def get_final_destination(container_number):
    record = airtable_containers_sheet.search('Container', container_number)
    try:
        return record[0]['fields']['Final Destination'][0]
    except KeyError:
        return

