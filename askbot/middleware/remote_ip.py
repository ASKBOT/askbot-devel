"""Fixes REMOTE_IP meta value
based on the HTTP_X_FORWARDED_FOR value, if used.
Enable this middleware if using django site behind a proxy
server or a load balancer.

Add to the MIDDLEWARE:

    'askbot.middleware.remote_ip.SetRemoteIPFromXForwardedFor',
"""

class SetRemoteIPFromXForwardedFor:
    def __init__(self, get_response=None): # i think get_reponse is never None. If it's not another middleware it's the view, I think
        if get_response is None:
            get_response = lambda x:x
        self.get_response = get_response

    def __call__(self, request):
        self.process_request(request)
        response = self.get_response(request) # i think this simply chains all middleware
        return response

    def process_request(self, request):
        try:
            real_ip = request.META['HTTP_X_FORWARDED_FOR']
        except KeyError:
            pass
        else:
            # HTTP_X_FORWARDED_FOR can be a comma-separated list of IPs.
            # Take just the first one.
            real_ip = real_ip.split(",")[0]
            request.META['REMOTE_ADDR'] = real_ip
