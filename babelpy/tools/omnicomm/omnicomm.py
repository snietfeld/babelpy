#!/usr/bin/env python
"""
Project Name: omnicomm
File Name: omnicomm.py

Description: 

Test configuration: 
    pyuic4 omnicomm_gui.ui -o omnicomm_gui.py
    python omnicomm.py

Author: Scott Nietfeld - Jan 28, 2012

Todo: 
    Implement string fields

References:       
"""

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from omnicomm_gui import Ui_MainWindow
import sys
import copy #for deepcopy

import serial
import socket
import hermes
import struct


units = ['unknown', 'm', 'kg', 'N', 'lbf', 'rad', 'rad/s']

class Connection():
    types = ['serial', 'udp packet', 'file']    
    protocol = ['none', 'hermes', 'babelbits']    
    
    def __init__(self, type=None, protocol='none', callback=sys.stdout.write):
        self.type = type
        self.callback = callback
        self.protocol = protocol
        self.callback = callback  #Callback for received message
        self.connected = False
        
    #Starts protocol session (if using a protocol) & tries to connect
    def start(self):
        try:
            if self.type == None: raise InputError('Connection type not defined')
            if self.protocol == None: raise InputError('Protocol type not defined')
            if self.callback == None: raise InputError('No callback defined')
        
            #Start protocol sessions if needed
            if self.protocol == 'hermes':
                self.session = hermes.HermesSession(msgHandler=self.callback) 
            elif self.protocol == 'babelbits':
                pass
        
            self.connect()  #Open serial port/socket/file/
        except Error:
            print "Failed to start connection"
            print sys.exc_info()[0]
            raise

    
    def connect(self):     #To be defined by subclass
        pass
    
    def omnom(self):       #To be defined by subclass
        pass
    
    def disconnect(self):  #To be defined by subclass
        pass
    
    def checkForMessages(self):
        #Run connection's method for getting available data
        data, nbytes = self.omnom()
        
        #Process data according to protocol specified
        if self.protocol == 'none':
            self.callback(data, nbytes)    #Just pass data straight to callback
            
        elif self.protocol == 'hermes':
            if len(data) > 0:
                for c in data:
                    self.session.processChar(ord(c[0])) #Callback run if needed
        
        elif self.protocol == 'babelbits':
            pass
        
        else:
            print "Error: Invalid protocol: %s" % self.protocol
    
class SerialConnection(Connection):
    def __init__(self, port=0, baud=9600, timeout=1, buff_size=1024, 
                 protocol='none', callback=sys.stdout.write):
        Connection.__init__(self, type='serial', protocol=protocol, callback=callback)
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.buff_size = buff_size
        
    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
            self.connected = True
        except serial.serialutil.SerialException:
            print "Whoopsie-doodle"
            raise
            
    #Checks to see if any new data is available
    def omnom(self):
        assert self.connected == True, "Not connected"
        data = None   
        
        #Get whatever data is available
        try:
            data = self.ser.read(self.buff_size)
        except:
            print 'Error reading from the port'
            raise
            
        return data, len(data)
        
    def flush(self):
        self.ser.flushInput()
        
    def disconnect(self):
        self.ser.close()
        self.connected = False
        
        
            
class UDPConnection(Connection):
    #Default bind_address '0.0.0.0' binds to any/all ip addresses
    def __init__(self, port=1350, bind_addr='0.0.0.0', timeout=1, buff_size=1024,
                 protocol='none', callback=sys.stdout.write):
        Connection.__init__(self, type='udp', protocol=protocol, callback=callback)
        self.port = port                  
        self.bind_addr = bind_addr 
        self.timeout = timeout
        self.buff_size = buff_size
        self.sock = None

    def connect(self):
        #Open socket
        try:
            self.sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
            self.sock.bind( (self.bind_addr, self.port) ) #Bind to address specified
            self.sock.settimeout(self.timeout)
            self.connected = True
        except:
            print 'Error opening socket'
            print sys.exc_info()[0]
            self.connected = False
            raise

    #Checks to see if any new data is available        
    def omnom(self):
        assert self.connected == True, "Not connected"
        data = None
        
        #Get whatever data is available
        try:
            data, addr = self.sock.recvfrom(self.buff_size)
        except socket.timeout:
            pass  #Nothing to see here
        except:
            print 'Error reading data from socket'
            print sys.exc_info()[0]
            raise
        
        return data, len(data)
        
    def disconnect(self):
        self.sock.close()
        self.connected = False

class TMField():
    def __init__(self):
        self.id = -1
        self.big_endian = True
        self.packed = False
        self.format_str = ""
        self.name = ""
        self.units = 'unknown'
        self.value = 0

class PacketFormat():
    def __init__(self):
        self.fields = []
        self.field_dict = {}
        self.format_str = ""
        
    def add_field(self, field):
        field.id = len(self.fields)
        self.fields.append(field)
        self.field_dict[field.name] = field

            
    def get_format_string(self):
        format_str = ""

        if self.big_endian == True:
            format_str += '>'
        else:
            format_str += '<'
        
        for field in self.fields:
            format_str += field.format_str
            
        return format_str

class omnicomm_QT4(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        self.packet_format = PacketFormat()
        self.tm_cells = {}   #Maps tm field names to cell coords

        # Connect function calls to GUI actions
        QtCore.QObject.connect(self.ui.update_format_btn,
                               QtCore.SIGNAL("clicked()"), 
                               self.update_format)
                               
        QtCore.QObject.connect(self.ui.udp_connect_btn,
                               QtCore.SIGNAL("clicked()"), 
                               self.udp_connect_btn_clicked)
                               
        QtCore.QObject.connect(self.ui.serial_connect_btn,
                               QtCore.SIGNAL("clicked()"), 
                               self.serial_connect_btn_clicked)
                               
        QtCore.QObject.connect(self.ui.udp_disconnect_btn,
                               QtCore.SIGNAL("clicked()"), 
                               self.close_connection)
                               
        QtCore.QObject.connect(self.ui.serial_disconnect_btn,
                               QtCore.SIGNAL("clicked()"), 
                               self.close_connection)
                              

        # Initialize global application variables
        


        #Initialize hermes session
        #self.conn = UDPConnection(port=1350, protocol='none', callback=self.msghandler)
        #self.conn = SerialConnection(port=8, baud=9600, protocol='none', callback=self.msghandler)
        
        #self.ser = None
        #self.session = None
        
        
    
    # Application functions
    #-------------------------------------------------------------
    def udp_connect_btn_clicked(self):
        try:
            port      = int(str(self.ui.udp_port_edit.text()))
            bind_addr = str(self.ui.udp_bindaddr_edit.text())
            timeout   = int(str(self.ui.udp_timeout_edit.text()))
            buff_size  = int(str(self.ui.udp_buffsize_edit.text()))
            
            self.conn = UDPConnection(port=port, bind_addr=bind_addr, 
                                      timeout=timeout, buff_size=buff_size, 
                                      protocol='none', callback=self.msghandler)
        except:
            print 'Error creating socket'
            print sys.exc_info()[0]
            raise
                                      
        self.open_connection() 
        
    def serial_connect_btn_clicked(self):
        try:
            port      = int(str(self.ui.serial_port_edit.text()))
            baud      = str(self.ui.serial_baud_edit.text())
            timeout   = int(str(self.ui.udp_timeout_edit.text()))
            buff_size = int(str(self.ui.udp_buffsize_edit.text())) - 1 #Port numbers are 1-indexed
            
            self.conn = SerialConnection(port=port, baud=baud, 
                                         timeout=timeout, buff_size=buff_size, 
                                         protocol='none', callback=self.msghandler)
        except:
            print 'Error opening serial port'
            print sys.exc_info()[0]
            raise
                                      
        self.open_connection()
                              
                              
    def close_connection(self):
        self.conn_timer.stop()
        self.conn.disconnect()
        
    def open_connection(self):
        self.conn.connect()
        print 'Connected...'
        self.conn_timer = QtCore.QTimer()
        QObject.connect(self.conn_timer, SIGNAL("timeout()"), self.conn.checkForMessages)
        self.conn_timer.start(100)
    
    def start_serial(self):
        #Initialize hermes session
        self.ser = serial.Serial(12, 9600, timeout=1)
        self.session = hermes.HermesSession(msgHandler=self.msghandler)        
        
        #Start timer for serial connection
        self.serial_timer = QtCore.QTimer()
        QObject.connect(self.serial_timer, SIGNAL("timeout()"), self.check_serial)
        self.serial_timer.start(100)
    
    def check_serial(self):
        msg = self.ser.read()
        
        if len(msg) > 0:
            for c in msg:
                self.session.processChar(ord(c[0]))
    
    def msghandler(self, s, nbytes):
        s = s[0:nbytes]
    
        #Post raw data to textbox
        self.ui.raw_data_textEdit.clear()
        if self.ui.data_view_encoding_combo.currentText() == 'ASCII':
            self.ui.raw_data_textEdit.appendPlainText(s)
        elif self.ui.data_view_encoding_combo.currentText() == 'Hex':    
            self.ui.raw_data_textEdit.appendPlainText(s.encode('hex'))
    
        #if nbytes == 4:
        if self.packet_format.format_str is not '':
            field_tuple = struct.unpack(self.packet_format.format_str, s)
            print field_tuple

            for i in range(0, len(field_tuple)):
                self.packet_format.fields[i].value = field_tuple[i]

        else:
            print s
                
        self.update_field_display()
    
    def update_format(self):
        format_str = str(self.ui.format_lineEdit.text())
        
        field_names = self.ui.labels_lineEdit.text().split(',')
        field_units = self.ui.units_lineEdit.text().split(',')
        field_format_strings = self.parse_format_string(format_str)
        
        print field_format_strings
        
        if len(field_names) == len(field_units) == len(field_format_strings):
            for i in range(0, len(field_names)):    
                field = TMField()
                field.format_str = field_format_strings[i]
                field.name = field_names[i]
                field.units = field_units[i]
                
                self.packet_format.add_field(field)

            self.packet_format.format_str = format_str   
            x = []             
            self.tm_cells = self.tm_cells.fromkeys(field_names, None)
            for key in self.tm_cells.keys(): self.tm_cells[key] = []
            self.update_tm_table()
            print self.tm_cells
        else:   
            print 'Err: number of field descriptors unmatched'
        
    def update_tm_table(self):
        self.ui.tm_table.clear()
        for i, field in enumerate(self.packet_format.fields):
            print field
            self.insert_field_row(self.ui.tm_table, field, i, 0)
            #self.tm_cells[(i,0+2)] = field
            self.tm_cells[field.name].append((i,0+2))
            print field.name, i
            
        self.update_field_display()
        
    def update_field_display(self):
        
        for name in self.tm_cells.keys():
            field = self.packet_format.field_dict[name]
            
            for (row, column) in self.tm_cells[name]:
                self.ui.tm_table.setItem(row, column, QTableWidgetItem(str(field.value)))
            
    @staticmethod
    def insert_field_row(table, field, row, column):
        
        while table.columnCount() < 5: 
            table.insertColumn(table.columnCount())
            
        while table.rowCount() < row + 1:
            table.insertRow(table.rowCount())
            
        table.setItem(row, column+0, QTableWidgetItem(str(field.id)))
        table.setItem(row, column+1, QTableWidgetItem(field.name))
        table.setItem(row, column+3, QTableWidgetItem(field.units))
        table.setItem(row, column+4, QTableWidgetItem(field.format_str))
    
    @staticmethod
    def parse_format_string(s):
        field_format_list = []
        for c in s:
            if c != '>' and c != '<':
                field_format_list.append(c)
                
        return field_format_list


if __name__ == "__main__":
 
    app = QtGui.QApplication(sys.argv)
    myapp = omnicomm_QT4()    
    myapp.show()
    sys.exit(app.exec_())
