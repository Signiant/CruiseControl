import socket
import boto3
import re
import os

# List of all EIPs
def _list_eips(region, filter):
    print "Connecting to ec2..."
    client = boto3.client('ec2', region_name=region)
    addresses_dict = client.describe_addresses()
    all_eips = []
    for eip_dict in addresses_dict['Addresses']:
        if eip_dict['PublicIp'] not in filter:
            all_eips.append(eip_dict['PublicIp'])
    return all_eips

# List IP of load balancer
def _balancer_ip(lb_name):
    print "Getting load balancer IP for %s..." % lb_name
    return socket.gethostbyname_ex(lb_name)[2]

# Describe the active environment
def _environment_descr(app_name, lb_name, region):
    print "Connecting to beanstalk..."
    eb = boto3.client('elasticbeanstalk', region_name=region)
    ret = eb.describe_environments(ApplicationName=app_name)
    #ret = _decode_dict(ret)
    active_env = None
    print "Looking up active environment..."
    for env in ret['Environments']:
        if lb_name.lower() in env['EndpointURL'].lower():
            active_env = env
            break
    return active_env['EndpointURL']

# Name of active load balancer
def _active_balancer(dns_name, region):
    print "Connecting to route53..."
    rconn = boto3.client('route53', region_name=region)
    if rconn == None:
        print "Failed to connect to route53, check region in config file"
        exit(-1)
    zones = rconn.list_hosted_zones()
    chosen_zone = None
    print "Looking up zone ID..."

    temp_dns_name = dns_name.split('.', 1)[-1]
    print "Temp dns_name is %s" % temp_dns_name

    for zone in zones['HostedZones']:
        print "The zone is: %s, the dns_name is %s" % (zone['Name'][:-1], dns_name)
        
        if zone['Name'][:-1] == dns_name:
            print "Found zone that equals the dns name"
            print zone['Name']
            chosen_zone = zone['Id'][12:]
            break

        elif zone['Name'][:-1] == temp_dns_name:
            print "Found zone that equals the temp dns name"
            print zone['Name']
            chosen_zone = zone['Id'][12:]

    print "Retrieving record sets..."
    rset = rconn.list_resource_record_sets(HostedZoneId=chosen_zone, StartRecordName=dns_name, StartRecordType="A", MaxItems="1")['ResourceRecordSets'][0]
    print "Record set retrieved is : "
    print rset
    lb_name = rset['AliasTarget']['DNSName']
    if 'dualstack' in lb_name:
        lb_name = re.search('dualstack.(.*)-[0-9]{9}', lb_name).group(1)
    else:
        lb_name = re.search('(.*?)-[0-9]{9}', lb_name).group(1)
    return lb_name
    
# IPs of running instances
def _instance_ip(lb_name, region):
    print "Connecting to ec2 elb..."  
    elb = boto3.client('elb', region_name=region)
    print "Connected!"
    print "Retrieving load balancers..."
    all_lbs = elb.describe_load_balancers()['LoadBalancerDescriptions']
    instance_ips = []
    for lb in all_lbs:
        if lb_name in lb['LoadBalancerName'].lower():
            #lb_name = str(lb['LoadBalancerName'])
            instances = [inst['InstanceId'] for inst in lb['Instances']]
            ec2 = boto3.client('ec2', region_name=region)
            reservations = ec2.describe_instances(InstanceIds=instances)['Reservations']
            for r in reservations:
                for instance in r['Instances']:
                    instance_ips.append(instance['PublicIpAddress'])
    return instance_ips

def _get_file(bucket_name, s3_path, local_path):
    if os.path.isfile(local_path):
        print "Deleting current file..."
        os.remove(local_path)
        print "Done"
    print "Retrieving config file..."
    s3 = boto3.resource('s3')
    s3.meta.client.download_file(bucket_name, s3_path, local_path)
    print "Done"

#Return prefixed record sets of a hosted zone ID 
def _get_records_from_zone(zone_id, record_prefix, domain):

    r = boto3.client('route53')
    startname = record_prefix + "." + domain
    res = r.list_resource_record_sets(HostedZoneId=zone_id, StartRecordName=startname, StartRecordType="A")
    entries = []
    for x in res['ResourceRecordSets']:
        if record_prefix.split('.')[0] in x['Name']:
            entries.append(x['ResourceRecords'][0]['Value'])

    return entries

# Decode dict/list
def _decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv

def _decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv
