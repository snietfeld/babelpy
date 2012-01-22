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

in_buf = []

#Constants
SYNC_1 = ord('T')
SYNC_2 = ord('M')
HEADERLEN = 5
MAX_MSGLEN = 0xffff - HEADERLEN - 4


NOCHECK = 0
CHECKSUM8 = 1
CHECKSUM16 = 2
CRC16 = 3
CRC32 = 4
#\Constants

#Globals
msg = [0] * MAX_MSGLEN  #Creates list of MAX_MSGLEN zeros
inBufLen = MAX_MSGLEN
outBufLen = MAX_MSGLEN
synced    = False
headerReceived = False
packetLen = 0
formatID = 0
checkType = 0
count = 0
rxdChecksum = 0
calcdChecksum = 0


def msgHandler(s, nbytes):
    format = '<f'

    s = s[0:nbytes]

    if nbytes == 4:
        print len(s)
        fields = struct.unpack(format, s)
        gyro_az = fields[0]
        print "%f" % gyro_az
    else:
        print s

def checksum8(s, nbytes):
    accum = 0
    for i in range(0, nbytes):
        accum += s[i]
    return accum & 0xff

def checksum16(s, nbytes):
    accum = 0
    for i in range(0, nbytes):
        accum += s[i]
    return accum & 0xffff

def processChar(c):
    global msg, synced, headerReceived, packetLen, formatID, checkType, checkLen, count, rxdChecksum, calcdChecksum, msgHandler

    #print "Processing %d" % c

    if synced == 2:
        msg[count] = c
        count += 1

        if headerReceived == True:
            if count >= packetLen:
                #print "Done reading message."
                #Done reading messafe, now process
                if checkType == NOCHECK:
                    msgHandler(msg[HEADERLEN:], packetLen-HEADERLEN-checkLen)

                else:  #Need to do error checking
                    if checkType == CHECKSUM8:
                        #print "CHECKSUM8 detected"
                        rxdChecksum = msg[packetLen-1]
                        calcdChecksum = checksum8(msg[2:], packetLen-2-1)
                    elif checkType == CHECKSUM16:
                        #print "CHECKSUM16 detected"
                        rxdChecksum = (msg[packetLen-2] << 8) + msg[packetLen-1]
                        calcdChecksum = checksum16(msg[2:], packetLen-3-1)
                    else:
                        #Incaled check type, scrap packet & start over
                        synced = 0
                        headerReceived = 0
                        count = 0
                        formatID = 0
                        packetLen = 0

                if calcdChecksum == rxdChecksum:
                    #print "CHECKSUM MATCH - processing message"
                    s = ""
                    msgLen = packetLen-HEADERLEN-checkLen

                    print packetLen, checkLen
                    for i in range(HEADERLEN, packetLen-checkLen):
                        s += chr(msg[i])

                    msgHandler(s, len(s))

                    #msgHandler(msg[HEADERLEN:], packetLen-HEADERLEN-checkLen)
                
                #Done with this message, reset variables for next one
                synced = 0
                headerReceived = 0
                count = 0
                formatID = 0
                packetLen = 0

        elif count == HEADERLEN: #Time to read the header
            #print "Processing header..."
            formatID = msg[2]
            packetLen = (msg[3] << 8) + msg[4]
            
            if packetLen >= inBufLen or packetLen > MAX_MSGLEN:
                #Message is too long, just scrap it and start over
                synced = 0
                headerReceived = 0
                count = 0
                formatID = 0
                packetLen = 0
                return

            checkType = (formatID >> 4) & 0x00ff

            if checkType == CHECKSUM16 or checkType == CRC16:
                checkLen = 2
            elif checkType == CHECKSUM8:
                checkLen = 1
            elif checkType == NOCHECK:
                checkLen = 0
            else:
                #Invalid check type--scrap packet and start over
                synced = 0
                headerReceived = 0
                count = 0
                formatID = 0
                packetLen = 0

            headerReceived = 1

            #print "   formatID: %x\n   packetLen: %d\n   checkType: %d\n   checkLen: %d" % (formatID, packetLen, checkType, checkLen)

    elif c == SYNC_1:
        #print "SYNC_1 received"
        synced = 1
        msg[count] = c
        count += 1

    elif synced == 1 and c == SYNC_2:
        #print "SYNC_2 received"
        synced = 2
        msg[count] = c
        count += 1


def processMsg(msg, msgLength):
    pass
            

def makeMsg(s, msgType):
    pass


def makePacket(msg, msgType):
    pass



if __name__ == "__main__":
    import serial
    #import doctest
    #doctest.testmod()

    test_msg = [SYNC_1, SYNC_2, CHECKSUM16 << 4, 0x00, 0x09, ord('o'), ord('k'), 0x01, 0x03]

    for c in test_msg:
        processChar(c)

    ser = serial.Serial(12, 9600, timeout=1)
    
    while(True):
        c = ser.read()
        if len(c) > 0:
           processChar(ord(c[0]))

