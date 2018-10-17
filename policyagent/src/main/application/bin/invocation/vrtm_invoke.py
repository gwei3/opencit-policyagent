#!/usr/bin/python

import logging
import logging.config
from socket import socket as Socket
import socket
import errno
from stream import PAStream, TCBuffer

class VRTMInvoke(object):

    MODULE_NAME = 'policyagent'
    
    def __init__(self):
        self.log_obj = logging.getLogger(VRTMInvoke.MODULE_NAME)
        self.__socket = None
        self.__tc_buffer = TCBuffer()
        self.__pa_stream = PAStream()
        self.__connection_time_out = 100.0

    def vrtm_connect(self, prop_dict):
        try:
            ip_addr = prop_dict['VRTM_IP']
            port_no = prop_dict['VRTM_PORT']
            self.__socket = Socket(socket.AF_INET, socket.SOCK_STREAM, 0)
            self.__socket.connect((ip_addr.replace('\n', ''), int(port_no.replace('\n', ''))))
        except socket.error as serr:
            if serr.errno == errno.ECONNREFUSED:
                self.log_obj.exception("Connection refused from server!")
            else:
                raise serr
        except Exception as e:
            self.log_obj.exception('Exception in communication with vrtm server!')
            raise e
        #finally:
        #    self.close()

    # This function sends xml string with encoded contents to VRTM.
    # It also returns response received to the calling function.
    def vrtm_invoke(self, tcbuffer, xml_string):
        try:
            stream = self.__pa_stream.pack_pa_stream(tcbuffer, xml_string, 's')
        except Exception as e:
            self.log_obj.exception("Error in packing into structure!")

        self.log_obj.info("TC Buffer before sending:" + str(tcbuffer.list()))
        try:
            self.__send(self.__socket, stream)
        except Exception as e:
            self.log_obj.exception("Failed during sending data to vrtm core!")
        try:
            tcbuffer, stream = self.__recv(self.__socket)
        except Exception as e:
            self.log_obj.exception("Failed while receiving data from vrtm!")

        return (tcbuffer, stream)

    def __send(self, __socket, stream):
        totalsent = 0
        _buffer = stream.tostring()
        length = len(_buffer)
        while totalsent < length :
            sent = __socket.send(_buffer[totalsent:])
            if sent == 0:
                raise Exception('Connection is broken!')
            totalsent = totalsent + sent

    def __recv(self, __socket):
        chunk = __socket.recv(TCBuffer.SIZE)
        if chunk is None :
            raise Exception("Connection is broken!")

        # Make TCBuffer object containing structure of format TCBuffer.FORMAT and unpack received buffer into it.
        tcbuffer = TCBuffer(*(self.__pa_stream.unpack_pa_stream(chunk, TCBuffer.FORMAT)))
        # Get size of data to be received from TCBuffer object created above.
        message_size = tcbuffer.get_m_reqSize()
        self.log_obj.info("TC Buffer received:" + str(tcbuffer.list()))
        if message_size == 0 :
            return (tcbuffer, None)

        # Receive data from VRTM equal to the size set in the TCBuffer object.
        stream = __socket.recv(message_size)
        if stream is None :
            self.log_obj.error("VRTM response is Null!!")
            return (tcbuffer, None)

        # Check, if response received is equal to the size set in TCBuffer object.
        total_length = len(stream)
        while total_length < message_size:
            __socket.setdefaulttimeout(self.__connection_time_out)
            stream = stream + __socket.recv(message_size - total_length)
            total_length = len(stream)

        return (tcbuffer, stream)

    def socket_close(self):
        try:
            self.__socket.shutdown(socket.SHUT_RDWR)
            self.__socket.close()
            self.log_obj.info("VRTM connection is closed!")
        except:
            # it only comes if connection is already close, we don't need to bother about it
            pass


if __name__ == '__main__':

    logging.config.fileConfig(fname='/root/test_vrtm/vrtm_invoke_logging.cfg')
