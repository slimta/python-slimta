
from socket import getfqdn
from itertools import product

# Configures the banners to use.
fqdn = getfqdn()
inbound_banner = '{0} ESMTP example.com Mail Delivery Agent'.format(fqdn)
outbound_banner = '{0} ESMTP example.com Mail Submission Agent'.format(fqdn)

# Calculates a list of all deliverable inbound addresses.
deliverable_domains = ['example.com']
deliverable_users = ['user', 'postmaster', 'abuse']
deliverable_addresses = set(['@'.join(pair) for pair in
                            product(deliverable_users, deliverable_domains)])

# Dictionary of acceptable outbound credentials.
credentials = {'user@example.com': 'secretpw'}

# vim:et:fdm=marker:sts=4:sw=4:ts=4
