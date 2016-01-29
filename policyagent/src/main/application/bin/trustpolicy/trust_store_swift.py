import logging
import swiftclient

class TrustPolicyStore:
    MODULE_NAME = 'policyagent'

    def __init__(self):
        self.log = logging.getLogger(TrustPolicyStore.MODULE_NAME)

    def getPolicy(self, args, config):
        print 'Swift store'
