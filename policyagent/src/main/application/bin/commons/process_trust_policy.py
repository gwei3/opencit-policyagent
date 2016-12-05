#!/usr/bin/python

import copy
from lxml import builder, etree as ET
import logging
import logging.config
import os
import utils as utils

class ProcessTrustpolicyXML(object):

    MODULE_NAME = 'policyagent'
    XML_HEADER = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"+"\n"
    VERIFY_TRUST_SIG = "verify-trustpolicy-signature"

    def __init__(self, xml_file_path):
        self.log_obj = logging.getLogger(ProcessTrustpolicyXML.MODULE_NAME)
        self.root = None
        self.namespace = None
        self.xml_file_path = xml_file_path
        self.__get_root()

    def __get_root(self):
        try:
            with open(self.xml_file_path, 'r') as f:
                xmlstring = f.read().replace('\n', '')
            root, namespace = utils.get_root_of_xml(xmlstring)
            self.root = root
            self.namespace = namespace
        except Exception as e:
            self.log_obj.exception("Error in getting root of XML file")
            raise e

    def retrieve_chksm(self):
        try:
            chksum_dct = {}
            if self.root.find('Encryption') is not None:
                dek_url = self.root.find('Encryption').find('Key').text
                checksum = self.root.find('Encryption').find('Checksum').text
                chksum_dct['DEK_URL'] = dek_url
                chksum_dct['CHECKSUM'] = checksum
                return chksum_dct
            else:
               return None
        except Exception as e:
            self.log_obj.exception('Error in retrieving decryption key and checksum from XML.')
            raise e

    def retrieve_image_id(self):
        try:
            if self.root.find('Image').find('ImageId') is not None:
                return self.root.find('Image').find('ImageId').text
            else:
               return None
        except Exception as e:
            self.log_obj.exception('Error in retrieving image id from XML.')
            raise e

    def generate_manifestlist_xml(self, instance_dir):
        new_manifest_file_path = os.path.join(instance_dir, 'manifest.xml')
        element = builder.ElementMaker()
        xml_root = element.Manifest
        try:
            for node in self.root.iter('Whitelist'):
                attr_val = node.attrib.get('DigestAlg')
            new_xml = xml_root(xmlns=self.namespace, DigestAlg=attr_val)
            for child in self.root.find('Whitelist'):
                final = copy.deepcopy(child)
                final.text=None
                new_xml.append(final)

            xml = ET.tostring(new_xml, pretty_print=True)
            #formatted_xml = "".join(xml.split())
            with open (new_manifest_file_path, 'w') as f:
                f.write(ProcessTrustpolicyXML.XML_HEADER)
                f.write(xml)
            return new_manifest_file_path
        except Exception as e:
            self.log_obj.exception('Error in creating manifest xml file.')
            raise e

    def verify_trust_policy_signature(self, tagent_location, policy_location):
        try:
            poutput = utils.create_subprocess([tagent_location, ProcessTrustpolicyXML.VERIFY_TRUST_SIG, policy_location])
            utils.call_subprocess(poutput)
            if poutput.returncode == 0:
                self.log_obj.debug("Trust policy signature verified.")
                return True
            else:
                self.log_obj.error("Trust policy signature verification failed.")
                return False
        except Exception as e:
            self.log_obj.exception("Failed while doing verification of trust policy signature!")
            raise e
    
if __name__ == '__main__':

    #This is just for testing purpose.
    logging.config.fileConfig(fname='/opt/policyagent/configuration/logging_properties.cfg')
    xml = ProcessTrustpolicyXML('trustpolicy-201509111507.xml')
    dictt = xml.retrieve_chksm()
    logging.info(dictt)
    logging.info(xml.retrieve_image_id())
    file_path = xml.generate_manifestlist_xml('/opt/')
    file_path = xml.generate_manifestlist_xml('/tmp/')
