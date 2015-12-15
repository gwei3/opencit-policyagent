#!/usr/bin/python

import logging
import logging.config
from lxml import builder, etree as ET
from base64 import b64encode, b64decode
from stream import TCBuffer
import commons.utils as utils
from vrtm_invoke import VRTMInvoke

class VRTMReq(object):

    VRTM_REQ_ID = 15
    VRTM_REQ_STATUS = 0
    MODULE_NAME = 'policyagent'

    def __init__(self):
        self.log_obj = logging.getLogger(VRTMReq.MODULE_NAME)
        self.__vrtm = VRTMInvoke()
        self.__tc_buffer = TCBuffer()

    # This function generates xml string to be passed to VRTM server.
    def vrtm_generate_xml(self, method_name, *argv):
        element = builder.ElementMaker()
        xml_root = element.methodCall
        xml_method = element.methodName
        xml_params = element.params
        xml_param = element.param
        xml_value = element.value
        xml_string = element.string
        try:
            new_xml = xml_root(xml_method(method_name))
            for arg in argv:
                encoded_value = b64encode(arg)
                new_xml.append(xml_params(xml_param(xml_value(xml_string(encoded_value)))))
            xml = ET.tostring(new_xml, pretty_print=True)
            new_xml = "".join(xml.split())
            return new_xml
        except Exception as e:
            self.log_obj.exception('Error in Base 64 encoding of values!')
            raise e

    def measure_vm(self, xml_string, dictt):
        try:
            # Create TCBuffer object and set parameter values in it.
            tcbuffer = self.__tc_buffer
            tcbuffer.set_m_reqSize(len(xml_string))
            tcbuffer.set_m_reqID(VRTMReq.VRTM_REQ_ID)
            tcbuffer.set_m_uStatus(VRTMReq.VRTM_REQ_STATUS)
            self.log_obj.info("xml rpc length %d" % (len(xml_string)))
            received_stream = ()
            # Connect to VRTM server.
            self.__vrtm.vrtm_connect(dictt)
            received_stream = self.__vrtm.vrtm_invoke(tcbuffer, xml_string)
            self.log_obj.info("Received response from VRTM : " + str(received_stream))
            stream = received_stream[1]
            # See, if the response from VRTM is positive/successful.
            #root = ET.XML(stream)
            root = utils.get_root_of_xml(stream)
            enc_retcode = root.find('params').find('param').find('value').find('string').text
            dec_retcode = b64decode(enc_retcode)
            if int(dec_retcode) < 0:
                self.log_obj.error("Vrtm not invoked successfully!" + str(dec_retcode))
                raise Exception("Vrtm not invoked successfully!")
            else: self.log_obj.info("Successfully received the response from VRTM. : " + str(dec_retcode))
        except Exception as e:
            raise e
        finally: self.__vrtm.socket_close()


if __name__ == '__main__':

    logging.config.fileConfig(fname='/root/test_vrtm/vrtm_invoke_logging.cfg')
    vrtm = VRTMReq()
    xml_string = vrtm.vrtm_generate_xml('get_verification_status', '-disk', '/root/test_vrtm/de723e27-800d-400a-9f84-9af3686d2d61/ab913bd571e1324a2ac125608b616ba7c4a19c6d', '-manifest', '/root/test_vrtm/de723e27-800d-400a-9f84-9af3686d2d61/trustpolicy.xml')
    vrtm.measure_vm(xml_string, {'VRTM_IP' : '127.0.0.1', 'VRTM_PORT' : '16005'})
