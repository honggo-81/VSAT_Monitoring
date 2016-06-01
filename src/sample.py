'''
Sample program to demonstrate communication to the Decimator

Copyright 2005 SED Systems, a division of Calian Ltd.

The following example performs a measurement of a signal at 1555.5MHz
using a center frequency of 1555.1MHz with a desired span of 50.0MHz.
The script demonstrates how to determine the actual settings from the
configuration response, and how to analyze the spectrum result to
analyze a signal power level (performed in the device_deciamtor module).
'''

from datetime import date
import time
import sys
import array
import device_decimator as decimator
import string

DECIMATOR_IP = '202.68.188.8'
span = 2.3e5
desired_frequency = 1596.713e6
rf_port = 3
signal_freq = desired_frequency
rbw = 100.0 # was 1 Hz
window_function = 'Blackman-Harris' # [Rectangular, Flattop, Blackman-Harris, Hamming, Hanning]
overlap = 0.5
num_average = 50
fft_length = 4096 # was 4096
num_points = 70

print 'Checking Decimator @' + DECIMATOR_IP + '...'
decim = decimator.connect(DECIMATOR_IP)
if decim == -1:
    print 'Cannot access Decimator'
    sys.exit(0)

serialNum = decimator.readSerialNumber()
msg = "Serial Number = " + str(serialNum)
print(msg)

currentPort = decimator.switchPort(rf_port)
msg = "Switch Port = " + str(currentPort)
print(msg)

#cmd = 'configSpectrum:%f,%f,1.0,Blackman-Harris,0.5,10,4096\r\n' % (desired_frequency, span)
#cmd = 'configSpectrum:%f,%f,1.0,Blackman-Harris,0.5,50,4096\r\n' % (desired_frequency, span)
cmd = 'configSpectrum:%f,%f,%f,%s,%f,%d,%d\r\n' % (desired_frequency, span, rbw, window_function, overlap, num_average, fft_length)
decim.send(cmd)
config_buf = decim.recv(100)
if not config_buf.startswith('configSpectrum'):
    print 'Error configuring decimator', config_buf
    sys.exit(1);

# Initiate the configuration and measurement
decim.send('startCapture\r\n')
buf = decim.recv(100)
if not buf.startswith('startCapture'):
    print 'Error starting capture', buf
    sys.exit(1);

# Request data in log amplitude format (dBm)
decim.send('getData:1,1\r\n')
floatData = decimator.getData()
#print floatData
print "length of all data: ", len(floatData)
# Analyse the returned spectrum using 7 bins for the signal bandwidth

sig_list = decimator.getSignalSampleData(config_buf, floatData, signal_freq, num_points)
print "length of focus data: ", len(sig_list)
print sig_list
psig = decimator.measureSignal(config_buf, floatData, signal_freq, num_points)

# Determine the actual center frequency and span settings
rec = string.split(config_buf,':')
rec = string.split(rec[1],',')
actual_centerFreq = float(rec[0])
actual_span = float(rec[1])

print 'Actual span: ', actual_span , ' Hz'
print 'Actual center frequency: ', actual_centerFreq , ' Hz'
print 'Signal level at', (signal_freq/1.0e6),'MHz: ', '%.2f' %(psig), 'dBm'

decimator.close()
print 'Finished at', time.localtime()