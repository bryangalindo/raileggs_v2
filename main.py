from database import update_container_tracing, update_container_eta, update_container_lfd
from scrapers import BNSFScraper, CanadianNationalScraper, CanadianPacificScraper, \
    CSXScraper, UnionPacificScraper
from transform import BNSFTransform, CanadianNationalTransform, CanadianPacificTransform, \
    CSXTransform, UnionPacificTransform

# EXTRACT
bnsf = BNSFScraper()
cn = CanadianNationalScraper()
cp = CanadianPacificScraper()
csx = CSXScraper()
up = UnionPacificScraper()

# TRANSFORM
bnsf_transform = BNSFTransform(bnsf.get_tracing_results_html(), bnsf.containers_list)
cn_transform = CanadianNationalTransform(cn.get_tracing_results_dict())
cp_transform = CanadianPacificTransform(cp.get_tracing_results_html(), cp.containers_list)
csx_transform = CSXTransform(csx.get_tracing_results_list(), csx.get_containers_dict())
up_transform = UnionPacificTransform(up.get_tracing_results_dict(), up.containers_list)

# LOAD
cn_transformed_results = cn_transform.get_tracing_results_list()
bnsf_transformed_results = bnsf_transform.get_tracing_result_list()
cp_transformed_results = cp_transform.get_tracing_results_list()
csx_transformed_results = csx_transform.get_tracing_results_list()
up_transformed_results = up_transform.get_tracing_results_list()

tracing_results = bnsf_transformed_results + cn_transformed_results + \
                  cp_transformed_results + csx_transformed_results + up_transformed_results


for result in tracing_results:
    if 'Pending' in result['current_status']:
        update_container_tracing(result['container_number'],
                                 'Pending\nTimestamp: {}'.format(result['timestamp']),
                                 'rail')

    elif 'Outgated' in result['current_status']:
        update_container_tracing(result['container_number'],
                                 'Most Recent Event: {}\nTimestamp: {}'.format(result['most_recent_event'],
                                                                               result['timestamp']))
    elif 'Grounded' in result['current_status']:
        tracing_result = 'Most Recent Event: {}\nTimestamp: {}'.format(result['most_recent_event'],
                                                                               result['timestamp'])
        update_container_tracing(result['container_number'], tracing_result, 'rail')
        try:
            update_container_lfd(result['container_number'], result['last_free_day'])
        except KeyError:
            print(result)
    elif 'Grounding' in result['current_status']:
        tracing_result = 'Most Recent Event: {}\nTimestamp: {}'.format(result['most_recent_event'],
                                                                       result['timestamp'])
        update_container_tracing(result['container_number'], tracing_result, 'rail')
        update_container_eta(result['container_number'], result['eta'], 'rail')
    else:
        tracing_result = 'Most Recent Event: {}\nScheduled Event: {}\nTimestamp: {}'.format(result['most_recent_event'],
                                                                                            result['scheduled_event'],
                                                                                            result['timestamp'])
        try:
            update_container_tracing(result['container_number'], tracing_result, 'rail')
            update_container_eta(result['container_number'], result['eta'], 'rail')
        except TypeError:
            print(result)

