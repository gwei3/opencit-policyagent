from struct import Struct
from array  import array

class PAStream(object):

    def __format(self, msg_length=None, msg_data_type=None):
        if msg_length is None or msg_data_type is None:
            return TCBuffer.FORMAT
        if msg_data_type == 's':
            return TCBuffer.FORMAT + str(msg_length) + msg_data_type
        return TCBuffer.FORMAT + msg_data_type
        
    def pack_pa_stream(self, tcbuffer, message, message_data_type):
        """ 
          Converts the TCBuffer object and message into Policy Agent stream.
          This function takes the parameters such as request size, request id, request status
          and packs them into a structure format as required by VRTM server.
        """
        # Make byte array of size equal to length of xml string + 12 Bytes header
        # for C to understand how much data is needed to be read.
        buffer_ = array('B', '\0' * (tcbuffer.get_m_reqSize() + TCBuffer.SIZE))
        # Make structure object in Python indicating template for size and data types
        # of xml string & parameters to be sent to VRTM server.
        struct_obj = Struct(self.__format(tcbuffer.get_m_reqSize(), message_data_type))
        arguments = [0] + tcbuffer.list() + [message]
        # Pack structure object with list of parameters(req_id, req_length, req_status) and xml string characters.
        struct_obj.pack_into(buffer_, *arguments)
        return buffer_
    
    
    def unpack_pa_stream(self, chunk, data_format):
        # Make bytearray of data equal to size of chunk (TCBuffer.Size).
        # This is header containing size for data to be received.
        _buffer = array('B', chunk)
        struct_obj = Struct(data_format)
        # Create structure of format TCBuffer.FORMAT and unpack received buffer into it.
        return struct_obj.unpack_from(_buffer)
        

class TCBuffer(object):

    """
        Equivalent to C tcBuffer structure of VRTM. 
    """
    # Default formate for PAStream is 'III', where I for unsigned int.
    FORMAT = 'III'  
    # sizeof(tcbuffer)
    SIZE=12
    
    def __init__(self, m_reqID = 0, 
                       m_reqSize = 0, 
                       m_ustatus = 0
                ):
        """
            m_reqID and m_reqSize are mandatory arguments for making vrtm request.
        """
        self.__m_reqID = m_reqID
        self.__m_reqSize = m_reqSize
        self.__m_ustatus = m_ustatus 
    
    # Don't change the position of attribute, this list is in sequence of C tcbuffer structure.
    # Position change may affect the communicatio with vrtm.
    def list(self):
        return [self.__m_reqID,
                self.__m_reqSize,
                self.__m_ustatus]
        
    def get_m_reqSize(self):
        return self.__m_reqSize

    def set_m_reqSize(self, m_reqSize):
        self.__m_reqSize = m_reqSize

    def set_m_reqID(self, m_reqID):
        self.__m_reqID = m_reqID

    def get_m_reqID(self):
        return self.__m_reqID

    def get_m_uStatus(self):
        return self.__m_ustatus

    def set_m_uStatus(self, m_uStatus):
        self.__m_ustatus = m_uStatus
    
        
if __name__ == '__main__':
    
    tcbuffer = TCBuffer(m_reqSize=len('I am coming!'),m_ustatus=120)
    pastream = PAStream()
    buffer_ = pastream.pack_pa_stream(tcbuffer, 'I am coming!')
    tcbuffer, message = pastream.unpack_pa_stream(buffer_)
    print tcbuffer.list()
    print message
