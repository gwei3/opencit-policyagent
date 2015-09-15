#!/usr/bin/python

import argparse
import os
import shutil
import logging
import logging.config
#from trustpolicy.trust_policy_retrieval import TrustPolicyRetrieval
#from commons.pa_parse import ParseXML, ParseProperty
#import commons.pa_utils as pa_utils
#from encryption.pa_crypt import PA_Crypt

#take from properties file
config = None
LOG = None

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
                LOG.info('calling tagent')
                if pa_utils.verify_trust_policy_signature(config['TAGENT_LOCATION'], policy_location):
                    #call commons for parsing policy
                    xml_parser = ParseXML(policy_location)
                    #generate stripped xml with whitelist
                    xml_parser.generate_xml(instance_dir)
                    #retrieve encryption element which has dek_url and checksum
                    encryption_element = xml_parser.retrieve_chksm()

                    if encryption_element is not None:
                        #call pa_decrypt
                        crypt = PA_Crypt(infile=os.path.join(config['INSTANCES_DIR'],'_base', args['image_id']), image_id=args['image_id'], dek_url=encryption_element['DEK_URL'], instance_dir=instance_dir, root_disk_size_gb=args['root_disk_size_gb'], instance_id=args['instance_id'], config=config)

                        decfile = crypt.pa_decrypt()
                        current_md5 = pa_utils.generate_md5(decfile)
                        if current_md5 != encryption_element['CHECKSUM']:
                            #LOG and Exception
                            LOG.exception("checksum mismatch")
                            raise Exception("checksum mismatch")
            else:
                #LOG
                LOG.exception("policy location has None value")
                raise Exception("policy location has None value")
                #pass
        else:
            #LOG
            LOG.exception("File not found"+args['base_image'])
            raise Exception("File not found")
            #pass
    except Exception as e:
        LOG.exception("Failed during launch call")
        raise e

def delete(args):
    try :
        enc_inst = PA_Crypt(instance_path=args['instance_path'], config=config)
        enc_inst.pa_delete()
    except Exception as e:
        LOG.exception("Failed during delete call")

def init_logger():
    logging.config.fileConfig(fname='/opt/policyagent/configuration/logging_properties.cfg')
    global LOG
    LOG = logging.getLogger(__name__)

def init_config():
    #initialize properties and logger
    prop_parser = ParseProperty()
    global config
    config = prop_parser.pa_create_property_dict("/opt/policyagent/configuration/policy_agent.properties")

if __name__ == "__main__":
    # execute only if imported as module
    init_logger()
    from trustpolicy.trust_policy_retrieval import TrustPolicyRetrieval
    from commons.pa_parse import ParseXML, ParseProperty
    import commons.pa_utils as pa_utils
    from encryption.pa_crypt import PA_Crypt
    init_config()
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    version_parser = subparsers.add_parser("version")
    version_parser.set_defaults(func=version)

    launch_parser = subparsers.add_parser("launch")
    launch_parser.add_argument("base_image")
    launch_parser.add_argument("image_id")
    launch_parser.add_argument("instance_id")
    launch_parser.add_argument("mtwilson_trustpolicy_location")
    launch_parser.add_argument("root_disk_size_gb")
    launch_parser.set_defaults(func=launch)

    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("instance_path")
    delete_parser.set_defaults(func=delete)
    args = parser.parse_args()
    args.func(vars(args))
