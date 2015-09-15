
class TrustPolicyRetrieval(object):

    @staticmethod
    def trustPolicy(trustPolicyStore):
        
        class_inst = None
        class_name = 'TrustPolicyStore'
        module_name = "trust_store_" + trustPolicyStore

        module = __import__('trustpolicy.' + module_name, globals(), locals(), [module_name], -1)

        if hasattr(module, class_name):
            class_inst = getattr(module, class_name)()

        return class_inst
        
