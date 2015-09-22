import logging

class TrustPolicyStore:
    MODULE_NAME = 'policyagent'

    def __init__(self):
        self.log = logging.getLogger(TrustPolicyStore.MODULE_NAME)

    def getPolicy(self, image_id):
        print 'Swift store'
