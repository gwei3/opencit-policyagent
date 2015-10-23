#!/usr/bin/python

import logging
import logging.config

class ParseProperty(object):

    COMMENT = '#'
    delim = "="
    MODULE_NAME = 'policyagent'

    def __init__(self):
        self.log_obj = logging.getLogger(ParseProperty.MODULE_NAME)

    def create_property_dict(self, prop_file_path):
        """It returns dict. IO Exception will be raised, if property file doesn't exist.
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
            self.log_obj.exception('Error in retrieving properties from properties file.')
            raise e

if __name__ == '__main__':

    #This is just for testing purpose.
    logging.config.fileConfig(fname='logging_properties.cfg')
    p = ParseProperty()
    logging.info(p.create_property_dict("policy_agent.properties"))
