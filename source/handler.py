#-*-  coding:utf-8 -*-
import threading
import logging
import logging.config
import tempfile
import ConfigParser#读取配置文件的库
import struct
'''一定要加这个感叹号，感觉有点奇怪'''
message_fmt1='!BBIB'#固定帧格式 起始字节：控制字节：地址4字节：结束字节
message_fmt2='!BHIBBI'#可变帧格式，这里注意只取需要的前13个字节
                        #起始字节：长度2字节：包计数4字节：启动字节：控制字节：地址4字节
class Handler(object):
    def __init__(self,request,client_address,cur_thread,log):
        self.request=request
        self.c_address=client_address
        self.cur_thread=cur_thread
        self.cmd=0 #表示当前从报文解析出来的控制命令是多少
        self.indata=None #表示得到的数据缓冲
        self.oudata=None #表示要发送出去的数据缓冲
        self.log=log#日志记录
        self.xbfile=Xb_file(client_address[0])#初始化一个文件对象
        self.parse_data=None
    def handle_file(self,parse_data):
        self.log.debug(u"开始进入文件处理子程序！")
        self.oudata="file is ok！"
    
    def handle_cmd(self,parse_data):
        pass
    
    '''指示下位机进行重传'''
    def handle_retry(self):
        self.oudata="please try!"
    
    def parse_message(self):
        '''解析获得帧里面的数据'''
        parse_data=None
        self.log.debug(u"得到的字节长度为：%d"%len(self.indata))
        if len(self.indata)==7:#固定帧
            startc1,cmdc,addrc,endc=struct.unpack(message_fmt1,self.indata)
            parse_data=Parsedata_struct(startc1,cmdc,addrc,0,0)
            self.log.debug("--------startc1=%d cmdc=%d addrc=%d endc=%d---------"%(startc1,cmdc,addrc,endc))
        if len(self.indata)>15:#可变帧
            start_13bytes=None
            start_13bytes=self.indata[0:13]
            startc1,data_lenc,bao_countc,starc2,cmdc,addrc=struct.unpack(message_fmt2,start_13bytes)
            parse_data=Parsedata_struct(startc1,cmdc,addrc,data_lenc,bao_countc)
        '''得到数据之后开始进一步处理'''
        try:
            if parse_data:
                '''进入文件处理命令'''
                if parse_data.cmd<19 and parse_data.cmd>15:
                    self.handle_file(parse_data)
                else:
                    self.oudata="cmd invalid!"
            else:
                self.handle_retry()
                    
        except Exception,e:
            self.log.error("{}".format(e))
    def handle(self):
        while True:
            try:
                self.indata=None
                self.indata = self.request.recv(1024)
                if self.indata:
                    self.parse_message()
                    #response = "{}: {}".format(self.cur_thread.name, self.indata)
                    response=self.oudata
                    self.request.sendall(response) 
                    #self.log.debug("recived data is {} !".format(data))
            except Exception , e:
                self.log.error("The error is {}!".format(e))
                break
        

class Parsedata_struct(object):
    def __init__(self,startc1,cmdc,addrc,data_lenc,bao_countc):
        self.start=startc1
        self.cmd=cmdc
        self.addr=addrc
        self.data_len=data_lenc
        self.bao_count=bao_countc


class Xb_file(object):
    def __init__(self,ip_addr):
        self.filename=None #客户端传送过来的当前文件的文件名
        self.client_dictname=ip_addr#./data/ip_addr
        #self.tmpfd=tempfile.TemporaryFile()#使用时注意使用seek来灵活的移动文件指针位置
        self.cur_count=0 #当前包的包号
        self.next_count=0 #下一个包的包号
        #得到数据文件夹路径
        '''
        cf=ConfigParser.ConfigParser()
        cf.read('xb.ini')
        file_dictory=cf.get('')
        '''
"""
日志的输出级别
1 )、 Level:  CRITICAL Numeric value: 50 
2 )、 Level:  ERROR     Numeric value: 40
3 )、 Level:  WARNING Numeric value: 30 
4 )、 Level:  INFO          Numeric value: 20
5 )、 Level:  DEBUG      Numeric value: 10
6 )、 Level:  NOTSET    Numeric value: 0
"""