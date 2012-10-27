#---------------------------------------------------------------------#
# Project Name: pybabelbits
#
# Version: 
# Description:
#
# Test configuration:
#
# Author: Scott Nietfeld
# Date: Jan 21, 2012
#--------------------------------------------------------------------#/

import struct


#Module constants
HEADERLEN = 5
MAX_MSGLEN = 0xffff - HEADERLEN - 4

NOCHECK = 0
CHECKSUM8 = 1
CHECKSUM16 = 2
CRC16 = 3
CRC32 = 4

class HermesSession:
    def __init__(self, msgHandler):
        #session constants
        self.SYNC_1 = ord('T')
        self.SYNC_2 = ord('M')

        #Session variables
        self.msgHandler = msgHandler
        self.in_buf    = [0] * MAX_MSGLEN  #Creates list of MAX_MSGLEN zeros
        self.inBufLen  = MAX_MSGLEN
        self.outBufLen = MAX_MSGLEN
        self.synced    = False
        self.headerReceived = False
        self.packetLen = 0
        self.formatID  = 0
        self.checkType = 0
        self.count     = 0
        self.rxdChecksum = 0
        self.calcdChecksum = 0

    def runHandler(self):
        s = ""
        msgLen = self.packetLen-HEADERLEN-self.checkLen

        for i in range(HEADERLEN, self.packetLen-self.checkLen):
            s += chr(self.in_buf[i])

        self.msgHandler(s, len(s))

    def reset(self):
        self.synced = 0
        self.headerReceived = 0
        self.count = 0
        self.formatID = 0
        self.packetLen = 0


    def processChar(self, c):
        """Processes individual characters, assembles packets & calls message handler.
        >>> import hermes
        >>> def handler(s, nbytes):
        ...     print(s[0:nbytes])
        ... 
        >>> session = hermes.HermesSession(msgHandler=handler)
        >>> test_msg = [session.SYNC_1, session.SYNC_2, hermes.CHECKSUM16 << 4, 0x00, 0x09, ord('o'), ord('k'), 0x01, 0x03]
        >>> for c in test_msg:
        ...     session.processChar(c)
        ... 
        ok
        """

        if isinstance(c, basestring):
            c = ord(c[0])

        #print "Processing %d" % c

        if self.synced == 2:
            self.in_buf[self.count] = c
            self.count += 1

        if self.headerReceived == True:
            if self.count >= self.packetLen:
                #print "Done reading message."
                #Done reading messafe, now process
                if self.checkType == NOCHECK:
                    self.runHandler()

                else:  #Need to do error checking
                    if self.checkType == CHECKSUM8:
                        #print "CHECKSUM8 detected"
                        self.rxdChecksum = self.in_buf[self.packetLen-1]
                        self.calcdChecksum = checksum8(self.in_buf[2:], self.packetLen-2-1)
                    elif self.checkType == CHECKSUM16:
                        #print "CHECKSUM16 detected"
                        self.rxdChecksum = (self.in_buf[self.packetLen-2] << 8) + self.in_buf[self.packetLen-1]
                        self.calcdChecksum = checksum16(self.in_buf[2:], self.packetLen-3-1)
                    else:
                        #Incaled check type, scrap packet & start over
                        self.reset()

                    if self.calcdChecksum == self.rxdChecksum:
                        #print "CHECKSUM MATCH - processing message"
                        self.runHandler()
                
                #Done with this message, reset variables for next one
                self.reset()

        elif self.count == HEADERLEN: #Time to read the header
            #print "Processing header..."
            self.formatID = self.in_buf[2]
            self.packetLen = (self.in_buf[3] << 8) + self.in_buf[4]
            
            if self.packetLen >= self.inBufLen or self.packetLen > MAX_MSGLEN:
                #Message is too long, just scrap it and start over
                self.reset()
                return

            self.checkType = (self.formatID >> 4) & 0x00ff

            if self.checkType == CHECKSUM16 or self.checkType == CRC16:
                self.checkLen = 2
            elif self.checkType == CHECKSUM8:
                self.checkLen = 1
            elif self.checkType == NOCHECK:
                self.checkLen = 0
            else:
                #Invalid check type--scrap packet and start over
                self.reset()
                    
            self.headerReceived = 1

            #print "   formatID: %x\n   packetLen: %d\n   checkType: %d\n   checkLen: %d" % (formatID, packetLen, checkType, checkLen)

        elif c == self.SYNC_1:
            #print "SYNC_1 received"
            self.synced = 1
            self.in_buf[self.count] = c
            self.count += 1

        elif self.synced == 1:     #Check for SYNC_2 byte
            if c == self.SYNC_2:   #SYNC_2 found
                #print "SYNC_2 received"
                self.synced = 2
                self.in_buf[self.count] = c
                self.count += 1
            else:                  #Bad SYNC_2, reset
                self.reset()
            

    def makePacket(self, checkType, msg, msgLen):
        formatID = checkType << 4

        #Calculate total packet length
        if checkType == CHECKSUM16 or checkType == CRC16:
            packetLen = msgLen + HEADERLEN + 2
        elif checkType == CHECKSUM8:
            packetLen = msgLen + HEADERLEN + 1
        elif checkType == NOCHECK:
            packetLen = msgLen + HEADERLEN
        else:
            return 0  #Unrecognized check type, abort
            
        if packetLen > MAX_MSGLEN: 
            return 0

        format = "<BBBBB" + str(msgLen) + "s"

        #Pack header and mesage (leave check off for now)
        s = struct.pack(format, 
                        self.SYNC_1, 
                        self.SYNC_2,
                        formatID,
                        (packetLen >> 8) & 0x00ff,
                        packetLen & 0x00ff,
                        msg[0:msgLen])

        #Calculate checksum (if any) and create check string
        if checkType == CHECKSUM16:
            calcdChecksum = checksum16(s[2:], packetLen - 3 - 1)
            check = struct.pack("BB", 
                                (calcdChecksum >> 8) & 0x00ff, 
                                calcdChecksum & 0x00ff)
        elif checkType == CHECKSUM8:
            calcdChecksum = checksum8(s[2:], packetLen - 2 - 1)
            check = struct.pack("B", calcdChecksum)
        elif checkType == NOCHECK:
            check = ""

        s += check

        return s
                        


def checksum8(s, nbytes):
    """Calculates 8-bit checksum
    >>> from hermes import checksum8
    >>> checksum8([1,2,3,4,5], 5)
    15
    >>> checksum8([1,2,3,4,5,2**8], 6)
    15
    """
    accum = 0

    if isinstance(s, basestring):
        for i in range(0, nbytes):
            accum += ord(s[i])

    elif isinstance(s, list):
        for i in range(0, nbytes):
            accum += s[i]

    else:
        print "checksum8: Error - unknown input type"

    return accum & 0xff

def checksum16(s, nbytes):
    """Calculates 8-bit checksum
    >>> from hermes import checksum8
    >>> checksum16([1,2,3,4,5], 5)
    15
    >>> checksum16([1,2,3,4,5,2**8], 6)
    271
    >>> checksum16([1,2,3,4,5,2**8,2**16], 7)
    271
    """

    accum = 0

    if isinstance(s, basestring):
        for i in range(0, nbytes):
            accum += ord(s[i])

    elif isinstance(s, list):
        for i in range(0, nbytes):
            accum += s[i]

    else:
        print "checksum16: Error - unknown input type"

    return accum & 0xffff




if __name__ == "__main__":
    import serial
    import doctest
    import random
    doctest.testmod()

    test_msg = ""
    match_count = 0

    #Define message handler function
    def handler(s, nbytes):
        global test_msg, match_count
        format = '<f'

        s = s[0:nbytes]

        if s == test_msg: 
            match_count += 1
        else:
            print "err"
            print list(test_msg), list(s)

    #Start session
    session = HermesSession(msgHandler=handler)

    #Parse test message
    test_msg = "ok"
    test_packet = [session.SYNC_1, 
                   session.SYNC_2, 
                   CHECKSUM16 << 4, 
                   0x00, 0x09, 
                   ord('o'), ord('k'), 
                   0x01, 0x03]

    for c in test_packet:
        session.processChar(c)

    # test_msg = "\x8f\x8f"
    # s = session.makePacket(1, test_msg, 2)
    # print list(s)
    # for c in s:
    #     session.processChar(c)

    #Generate random packets, parse, and compare
    for i in range(0, 100):
        msgLen = random.randrange(1, MAX_MSGLEN)
        test_msg = ""
        for j in range(0, msgLen):
            test_msg += chr(random.randrange(0, 255))
                           
        checkType = random.randrange(0, 3)
        s = session.makePacket(checkType, test_msg, msgLen)

        for c in s:
            session.processChar(c)

    print match_count
    # #Make message
    # s = session.makePacket(CHECKSUM16, "ok", 2)

    # for c in s:
    #     print ord(c)
    #     session.processChar(c)

