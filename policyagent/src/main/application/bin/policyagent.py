#!/usr/bin/python

import argparse
import os
import shutil

config = None
LOG = None

import logging as loging
import logging.config as logging_config

MODULE_NAME = 'policyagent'
POLICY_AGENT_PROPERTIES_FILE = '/opt/policyagent/configuration/policyagent.properties'

def version(args):
    LOG.info('policyagent-0.1')

def launch(args):
    try:
        if os.path.isfile(args['base_image']):
            policy_location = None
            instance_dir = os.path.join(config['INSTANCES_DIR'],args['instance_id'])
            store = TrustPolicyRetrieval.trustPolicy(args['mtwilson_trustpolicy_location'])
            if store is not None:
                policy_location = store.getPolicy(args['image_id'], config)
                shutil.copy(policy_location, os.path.join(instance_dir,'trustpolicy.xml'))
            else:
                LOG.exception("Mtwilson_trustpolicy_location is None")
                raise Exception("Mtwilson_trustpolicy_location is None")
            if policy_location is not None:
                LOG.info('Verifiying trust policy signature ...')
                xml_parser = ProcessTrustpolicyXML(policy_location)
                if xml_parser.verify_trust_policy_signature(config['TAGENT_LOCATION'], policy_location):
                    #generate stripped xml with whitelist
                    xml_parser.generate_manifestlist_xml(instance_dir)
                    #retrieve encryption element which has dek_url and checksum
                    encryption_element = xml_parser.retrieve_chksm()
                    if encryption_element is not None:
                        crypt = Crypt(image = os.path.join(config['INSTANCES_DIR'],'_base', args['image_id']),\
                                     image_id = args['image_id'], dek_url = encryption_element['DEK_URL'], \
                                     instance_dir = instance_dir, root_disk_size_gb = args['root_disk_size_gb'],\
                                     instance_id = args['instance_id'], config = config)
                        decfile = crypt.decrypt()
                        current_md5 = utils.generate_md5(decfile)
                        if current_md5 != encryption_element['CHECKSUM']:
                            LOG.exception("checksum mismatch")
                            raise Exception("checksum mismatch")
            else:
                LOG.exception("policy location has None value")
                raise Exception("policy location has None value")
        else:
            LOG.exception("File not found" + args['base_image'])
            raise Exception("File not found")
    except Exception as e:
        LOG.exception("Failed during launch call " + str(e.message))
        raise e

def delete(args):
    try :
        enc_inst = Crypt(instance_path = args['instance_path'], config = config)
        enc_inst.delete()
    except Exception as e:
        LOG.exception("Failed during delete call " + str(e.message))
        raise e

def init_logger():
    #initialize logger
    logging_config.fileConfig(fname = config['LOGGING_CONFIG_PATH'])
    #logging_config.fileConfig(fname = LOGGING_CONFIG_PATH)
    global LOG
    LOG = loging.getLogger(MODULE_NAME)

def init_config():
    #initialize properties
    prop_parser = ParseProperty()
    global config
    config = prop_parser.create_property_dict(POLICY_AGENT_PROPERTIES_FILE)

# execute only if imported as module
if __name__ == "__main__":
    from commons.parse import ParseProperty
    init_config()
    init_logger()
    try:
        #init_logger()
        #from commons.parse import ParseProperty
        #init_config()
        from trustpolicy.trust_policy_retrieval import TrustPolicyRetrieval
        from commons.process_trust_policy import ProcessTrustpolicyXML
        import commons.utils as utils
        from encryption.crypt import Crypt
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        version_parser = subparsers.add_parser("version")
        version_parser.set_defaults(func = version)
        launch_parser = subparsers.add_parser("launch")
        launch_parser.add_argument("base_image")
        launch_parser.add_argument("image_id")
        launch_parser.add_argument("instance_id")
        launch_parser.add_argument("mtwilson_trustpolicy_location")
        launch_parser.add_argument("root_disk_size_gb")
        launch_parser.set_defaults(func = launch)
        delete_parser = subparsers.add_parser("delete")
        delete_parser.add_argument("instance_path")
        delete_parser.set_defaults(func = delete)
        args = parser.parse_args()
        args.func(vars(args))
    except Exception as e:
        LOG.exception("Failed while executing policyagent..")
        raise e

