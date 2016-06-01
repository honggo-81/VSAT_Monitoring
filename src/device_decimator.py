'''
Sample program to demonstrate communication to the Decimator

Copyright 2005 SED Systems, a division of Calian Ltd.

The following are a collection of routines to manage communications
to a Decimator and perform analysis on measurement results.
'''
import socket
import time
import string
import sys
import struct
import array
from math import sqrt, log10, pow, fabs

BYTES_PER_FLOAT = 4 # All data is currently returned as array of floats
PORT = 9784         # The port as used by the Decimator
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

def connect( ip ):
    s.connect((ip, PORT))
    s.settimeout(10)
    str = s.recv(50)
    if str.find('connected') == -1:
        return -1
    return s

## Reads the response message for one block of data from the device.
## Caller must have already sent the getData command with formats desired
## Returns an array of floats or error message
def getData():
    buf = s.recv(100)
    if buf.startswith('getData'):
        #Get the size of data block to follow.
        #  Response looks like  getData:iii,qqq,bbb,\r\n
        #  bbb is the blockSize we need
        rec = string.split(buf,',',3)
        blockSize = int(rec[2]) / BYTES_PER_FLOAT
        BUF_SIZE = int(rec[2])
        #In case we already received part of the float array, save the data
        if len(rec[3]) > 2:
            tmp = rec[3]
            buf = tmp[2:] # discard \r\n from beginning of block
        else:
            buf = ''
        # retry until we have a complete block of data
        while len(buf) < BUF_SIZE:
            newdata = s.recv(BUF_SIZE - len(buf))
            buf = buf + newdata
        # unpack is setup to do endian conversion if necessary
        bindata = struct.unpack('!%df' % blockSize, buf)
    else:
        return 'getData error'
    return bindata
    
def readPowerDetector():
    # this is an unsupported command used for factory testing only.
    s.send('readPowerDetector\r\n')
    str = s.recv(100)
    i = str.find(':')
    return float(str[i+1:])

def readTemperature():
    s.send('status\r\n')
    str = s.recv(100)
    rec = string.split(str,',')
    return float(rec[4])

def readSerialNumber():
    s.send('status\r\n')
    str = s.recv(100)
    rec = string.split(str,',')
    return string.strip(rec[7])

def setRefClock( clk ):
    # clk = 0 for external 10MHz, 1 for internal 10MHz reference
    s.send('getConfig\r\n')
    str = s.recv(100)
    rec = string.split(str,':')
    rec = string.split(rec[1],',')
    rec[1] = clk
    cmd = 'config:' + rec[0] + ',' + `rec[1]` + ',' + rec[2] + ',' + rec[3]
    s.send(cmd)
    str = s.recv(100)
    if not str.startswith('config'):
        print 'Error configuring decimator' + str

# WSM - HY: Switch to a specific RF Port
def switchPort(rfPort):
    cmd = 'switchPort:%d\r\n' % rfPort
    s.send(cmd)
    str = s.recv(100)
    i = str.find(':')
    return str[i + 1:]

def close():
    NOLINGER = struct.pack('HH', 1, 0)
    s.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER, NOLINGER)
    s.shutdown(2)
    s.close()
#
# Utilities for manipulating data arrays from Decimator
#

# Get index of element with maximum value
def getMaxIdx( arr ):
    maxidx = 0
    maxlvl = arr[0]
    i = 1
    while i < len(arr):
        if maxlvl < arr[i]:
            maxlvl = arr[i]
            maxidx = i
        i += 1
    return maxidx

# Perform a power integration of supplied array of values
def lin_add( arr ):
    try:
        total = 0.0
        for element in arr:
            total += pow(10, element / 10) # WSM - HY: Converting dbM to mW
        total = 10 * log10(total)
    except:
        total = -999
    return total

# Process an array of IQ data and calculate mean, rms values
def getAdcLevel(numBlks):
    samples = array.array('f')
    numSamples = 0
    ADC_TO_VOLTS = 2.0 / pow(2,16)
    ## The raw IQ data can be saved to a file by uncommenting the
    ##   appropriate lines below.
    #tm = time.strftime("%Y%m%d%H%M%S", time.localtime())
    #filename = "decim_iq_%s.txt" % tm
    #fileiq = open(filename,"w")             
            
    block = 1
    while block <= numBlks:
        s.send('getData:2,1\r\n') #request raw IQ data
        floatData = getData()
        n = 0
        for element in floatData:
            samples.append(element * ADC_TO_VOLTS)
            #valstr = "%.0f " % element
            #fileiq.write(valstr)
            n += 1
        numSamples = numSamples + n    
        block += 1
    #fileiq.flush()
    #fileiq.close()
    Isum = 0.0
    Qsum = 0.0                
    i = 1
    while i < numSamples / 2:
        Isum = Isum + samples[i*2]
        Qsum = Qsum + samples[i*2+1]
        i += 1
    Imean = Isum / (numSamples/2)
    Qmean = Qsum / (numSamples/2)
   
    Isumsq = 0.0
    Qsumsq = 0.0
    i = 1
    while i < numSamples / 2:
        Isumsq = Isumsq + pow(samples[i*2] - Imean, 2)
        Qsumsq = Qsumsq + pow(samples[i*2+1]- Qmean, 2)
        i += 1
                                    
    Irms = sqrt(Isumsq/(numSamples/2))
    Qrms = sqrt(Qsumsq/(numSamples/2))
    #print 'Isum', Isum, numSamples, Imean, Isumsq, Irms
    #print 'Qsum', Qsum, numSamples, Qmean, Qsumsq, Qrms
    
    adc = sqrt((Irms * Irms)+ (Qrms * Qrms))
    data = {}
    data['Imean'] = Imean
    data['Qmean'] = Qmean
    data['Irms'] = Irms
    data['Qrms'] = Qrms
    data['adc_rms'] = adc
    return data

# Measure a signal level in a trace result / band power
def measureSignal(config, data, freq, numPoints):
    rec = string.split(config,':')
    rec = string.split(rec[1],',')
    centerFreq = float(rec[0])
    span = float(rec[1])
    binSize = span / len(data)
    print " binSize: ", binSize
    startFreq = centerFreq - (span / 2.0)
    endFreq = centerFreq + (span / 2.0)
    if freq < startFreq or freq > endFreq:
        return -100
    else:
        signalIdx = int((freq - startFreq) / binSize)
        print "signalIdx: ", signalIdx
        sigLevel = lin_add(data[signalIdx-numPoints/2:signalIdx+numPoints/2+1])
        signalIdxMin = signalIdx-numPoints/2
        signalIdxMax = signalIdx+numPoints/2+1
        print "signalIdxMin: ", signalIdxMin , "signalIdxMax: ", signalIdxMax
    return sigLevel

def getSignalSampleData(config, data, freq, numPoints):
    rec = string.split(config,':')
    rec = string.split(rec[1],',')
    centerFreq = float(rec[0])
    span = float(rec[1])
    binSize = span / len(data)
    startFreq = centerFreq - (span / 2.0)
    endFreq = centerFreq + (span / 2.0)
    if freq < startFreq or freq > endFreq:
        return [-100]
    else:
        signalIdx = int((freq - startFreq) / binSize)
        return data[signalIdx-numPoints/2:signalIdx+numPoints/2+1]


# Find the median value of a set of points
def median( points ):
    data = list(points)
    data.sort()
    if len(data) % 2:   # number of elements is odd
        median = data[len(data)/2]
    else:
        mid = len(data)/2
        median = (data[mid-1] + data[mid]) / 2.0
    return median