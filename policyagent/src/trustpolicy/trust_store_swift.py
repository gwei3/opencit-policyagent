class TrustPolicyStore:

    def __init__(self):
        self.log = logging.getLogger(__name__)

    def getPolicy(self, image_id):
        print 'Swift store'
