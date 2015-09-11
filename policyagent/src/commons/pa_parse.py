#!/usr/bin/python

from StringIO import StringIO
from lxml import builder, etree as ET
import logging
import logging.config
import os

class ParseProperty(object):

    COMMENT = '#'
    delim="="
    def __init__(self):
        self.log_obj = logging.getLogger(__name__)

    def pa_create_property_dict(self, prop_file_path):
        """It returns dict, IO Exception will get raise,
        if file_path does not exist.
        Keyword arguments:
        file_path : path to property file.
        delim : default is = (as per standard).
        
        """
        try:
            prop_dict = {}
            with open(prop_file_path.strip()) as f:
                for line in f:
                    if line.startswith(ParseProperty.COMMENT) : continue
                    index = line.find(ParseProperty.delim)
                    if index == -1 : continue
                    key = line[0:index]
                    val = line[index+1:]
                    prop_dict[key.strip()] = val.strip()
            return prop_dict

        except Exception as e:
            self.log_obj.exception('Exception: %s' % str(e))
            raise e


class ParseXML(object):

    def __init__(self, xml_file_path):

        self.log_obj = logging.getLogger(__name__)
        with open(xml_file_path, 'r') as f:
            xmlstring = f.read().replace('\n', '')
        tree = ET.iterparse(StringIO(xmlstring))
        for tagg, node in tree:
            if '}' in node.tag:
                node.tag = node.tag.split('}', 1)[1] # Strip all namespaces.
        self.root = tree.root

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
            self.log_obj.exception('Exception: %s' %str(e))
            raise e

    def generate_xml(self, instance_dir):
        try:
            new_manifest_file_path = os.path.join(instance_dir, 'manifestlist.xml')
            #new_manifest_file_path = 'new_manifest2.xml'
            i = 0
            path = []
            try:
                for child in self.root.find('Whitelist'):
                    path.append(child.attrib['Path'])
                    i+=1
            except Exception as e:
                self.log_obj.exception('Exception: %s' %str(e))
                raise e

            E = builder.ElementMaker()
            ROOT = E.Whitelist
            DIR = E.Dir
            FILE = E.File
            TEXT = E.Text
            try:
                new_xml = ROOT(DIR(Path=path[0]), DigestAlg='sha1')
                for i in range(1, len(path)):
                    new_xml.append(FILE(Path=path[i]))
                xml = ET.tostring(new_xml, pretty_print=True)
                with open (new_manifest_file_path, 'w') as f:
                    f.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"+'\n')
                    f.write(xml)
                return new_manifest_file_path
            except Exception as e:
                self.log_obj.exception('Exception: %s' %str(e))
                raise e
        except Exception as e:
            self.log_obj.exception('Exception: %s' %str(e))
            raise e

    
if __name__ == '__main__':

    logging.config.fileConfig(fname='workflow_launcher_logging.cfg')
    p = ParseProperty()
    logging.info(p.pa_create_property_dict("policy_agent.properties"))

    xml = ParseXML('fmanifest.xml')
    dictt = xml.retrieve_chksm()
    file_path = xml.generate_xml()
