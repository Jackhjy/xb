#-*- coding:utf-8 -*-
#测试struct
'''
import struct
import binascii
values = (1, 'abc', 2.7)
s = struct.Struct('I3sf')
packed_data = s.pack(*values)#一定要注意这个星号表示它是一个元组
unpacked_data = s.unpack(packed_data)
 
print 'Original values:', values
print 'Format string :', s.format
print 'Uses :', s.size, 'bytes'
print 'Packed Value :', binascii.hexlify(packed_data)
print 'Unpacked Type :', type(unpacked_data), ' Value:', unpacked_data
'''


#--------------------------------------
#!/usr/bin/python

#import sqlite3

#conn = sqlite3.connect('test.db')
#print "Opened database successfully";

#conn.execute('''CREATE TABLE COMPANY
#       (ID INT PRIMARY KEY     NOT NULL,
#       NAME           TEXT    NOT NULL,
#       AGE            INT     NOT NULL,
#       ADDRESS        CHAR(50),
#       SALARY         REAL);''')
#print "Table created successfully";

#conn.close()


#--------------------------------------

import urllib

def getHtml(url):
    page=urllib.urlopen(url)
    html=page.read()
    return html

html=getHtml("http://tieba.baidu.com/p/2738151262")

print html
