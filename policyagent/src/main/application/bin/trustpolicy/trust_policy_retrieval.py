import logging

MODULE_NAME = 'policyagent'
global LOG
LOG = logging.getLogger(MODULE_NAME)

#This class is like factory class which returns the store's module
#depending on the location which is being provided by the user.
#To add new module for example 'test' perform the steps as-
#    - Add a new file names trust_store_test.py
#    - Add class named TrustPolicyStore
#    - Implement method named 'getPolicy'
#Refer to trust_store_glance_image_tar.py
class TrustPolicyRetrieval(object):

    @staticmethod
    def trustPolicy(trustPolicyStore):
        try:
            class_inst = None
            class_name = 'TrustPolicyStore'
            module_name = "trust_store_" + trustPolicyStore
            #Here we load the module at runtime depending on the user input and return the class instance
            module = __import__('trustpolicy.' + module_name, globals(), locals(), [module_name], -1)
            if hasattr(module, class_name):
                class_inst = getattr(module, class_name)()
            return class_inst
        except Exception as e:
            LOG.exception("Failed while retrieving trust policy..")
            raise e
        
