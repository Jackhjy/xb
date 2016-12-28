#-*-  coding:utf-8 -*-
import threading
import logging
import logging.config
import tempfile
import ConfigParser#读取配置文件的库
import struct
import os


import cmd as CMD
import tools
'''一定要加这个感叹号，感觉有点奇怪'''
#固定帧格式 起始字节：控制字节：地址4字节：结束字节
message_fmt1='!BBIB'

#可变帧格式，这里注意只取需要的前13个字节
#起始字节：长度2字节：包计数4字节：启动字节：控制字节：地址4字节:用户数据（n):CS(校验字节)：结束字节
#长度2字节包括的内容是：控制字节+地址字节+用户数据的总长度
#校验范围是：控制字节+地址字节+用户数据
#可变帧中包计数为零的包表示不是文件数据，是文件名
message_fmt2='!BHIBBI'


outdata_fmt1='!BBIB'            
class Handler(object):
    def __init__(self,request,client_address,cur_thread,log,root_data,addr):
        self.request=request
        self.c_address=client_address
        self.cur_thread=cur_thread
        self.cmd=0 #表示当前从报文解析出来的控制命令是多少
        self.indata=None #表示得到的数据缓冲
        self.oudata=None #表示要发送出去的数据缓冲
        self.log=log#日志记录
        self.xbfile=Xb_file(client_address[0],root_data)#初始化一个文件对象
        self.parse_data=None
        self.filename=None
        self.tempfile=None
        self.haddr=addr
    
    
    def check_datapath(self):
        root_path=self.xbfile.client_dictname
        file_pathfile=os.path.split(self.filename)
    def clear_temp(self):
        self.filename=None
        if self.tempfile:
            self.tempfile.close()
        
    def ready_temp(self):
        self.tempfile=tempfile.TemporaryFile(mode='w+b',dir='.\\tmp\\')
        self.tempfile.seek(0)
        #self.tempfile=open(".\\tmp\\tmp.txt",'w+b')
        
    def save_file(self):
        filepath=os.path.join(self.xbfile.client_dictname,self.filename)
        temp=None
        return_flag=False
        try:
            
            if self.tempfile:
                self.tempfile.seek(0)
                temp=self.tempfile.read()
                
            fd=open(filepath,'wb')
            fd.seek(0)
            fd.write(temp)
            fd.close()
            return_flag=True
        except Exception,e:
            if fd:
                fd.close()
            self.log.debug(u'[save_file]文件存储异常：{}'.format(e))
            return_flag=False
        return return_flag
            
    def handle_file(self,parse_data):
        self.log.debug(u"开始进入文件处理子程序！")
        cmd=parse_data.cmd
        
        if cmd==CMD.CCMD_FILE_REQ_START:#收到客户机请求传输文件的命令
            self.filename=None
            self.filename=self.indata[13:-2]
            if tools.checksum(self.indata[8:-2]):
                self.log.debug(u"C----->H 行波设备请求开始传输文件:%s"%self.filename)
                if os.path.exists(os.path.join(self.xbfile.client_dictname,self.filename)):#数据文件已存在和不存在的处理方式
                    self.log.debug(u"文件已经存在！")
                    self.oudata=get_outdata(CMD.HCMD_FILE_COMPLETE,haddr=self.haddr)
                    self.request.sendall(self.oudata)
                    self.clear_temp()
                else:  
                    self.oudata=get_outdata(CMD.HCMD_FILE_CONFIRM_START,haddr=self.haddr)
                    self.request.sendall(self.oudata)
                    self.xbfile.cur_count=0
                    self.xbfile.next_count=1
                    self.ready_temp()
                    
            else:
                self.log.error(u'校验错误！')
                self.oudata=get_outdata(CMD.HCMD_FILE_RETRYTHIS,haddr=self.haddr)#重传该数据
                self.request.sendall(self.oudata)
        elif cmd==CMD.CCMD_FILE_TRANSFERRING:#收到客户机正在传输数据的命令
            self.xbfile.cur_count=self.xbfile.cur_count+1
            self.xbfile.next_count=self.xbfile.next_count+1            
            if parse_data.bao_count==self.xbfile.cur_count:
                self.log.debug(u'[handle_file]包序号核对正确！')
                self.tempfile.write(self.indata[13:-2])
                self.log.debug(u'[handle_file]写入文件的文件包长度：%d'%len(self.indata[13:-2]))
                self.log.debug(u'[handle_file]下一步1！')
                self.oudata=get_outdata(CMD.HCMD_FILE_NEXT_TRANSFERRING,haddr=self.haddr)#返回完成命令
                self.log.debug(u'[handle_file]下一步2！')
                self.request.sendall(self.oudata)   
            else :
                self.log.error(u'包序号不匹配')
                self.oudata=get_outdata(CMD.HCMD_FILE_RETRYTHIS,haddr=self.haddr)#重传该数据
                self.request.sendall(self.oudata)
        elif cmd==CMD.CCMD_FILE_COMPLETE:#文件传输完成，接收最后一个包
            self.xbfile.cur_count=self.xbfile.cur_count+1
            self.xbfile.next_count=self.xbfile.next_count+1
            self.log.debug(u'[handle_file]接收到最后一个包，包号为：%d'%self.xbfile.cur_count)
            if parse_data.bao_count==self.xbfile.cur_count:
                self.log.debug(u'[handle_file]包序号核对正确！')
                self.tempfile.write(self.indata[13:-2])
                self.log.debug(u'[handle_file]写入文件的文件包长度：%d'%len(self.indata[13:-2]))
                if self.save_file():#存储正常
                    self.log.debug(u"[handle_file]文件保存完毕!") 
                else:#存储不正常
                    if os.path.exists(os.path.join(self.xbfile.client_dictname,self.filename)):
                        os.remove(os.path.join(self.xbfile.client_dictname,self.filename))
                self.oudata=get_outdata(CMD.HCMD_FILE_COMPLETE,haddr=self.haddr)#返回完成命令
                self.request.sendall(self.oudata)                     
                self.clear_temp()    
            else :
                self.log.error(u'包序号不匹配')
                self.oudata=get_outdata(CMD.HCMD_FILE_RETRYTHIS,haddr=self.haddr)#重传该数据
                self.request.sendall(self.oudata)
        elif cmd==CMD.CCMD_FILE_ERROR:
            self.log.debug(u'客户端文件读取错误！')
            self.oudata=get_outdata(CMD.HCMD_FILE_COMPLETE,haddr=self.haddr)#返回完成命令
            self.request.sendall(self.oudata)            
            self.clear_temp()
        else:
            self.oudata="file cmd is not used！"
            self.request.sendall(self.oudata)
    def handle_system(self,parse_data):
        cmd=parse_data.cmd
        if cmd==CMD.CCMD_CONNECT_REQ:
            self.oudata=get_outdata(CMD.HCMD_CONNECT_RES,haddr=self.haddr)
            self.log.debug(u'有客户端请求连接！')
            self.request.sendall(self.oudata)
        elif cmd==CMD.CCMD_CMD_HARTBEAT:
            self.oudata=get_outdata(CMD.HCMD_CMD_HARTEAT,haddr=self.haddr)
            self.log.debug(u'{}收到心跳！'.format(self.cur_thread.getName()))
            self.log.info(u'.')
            self.request.sendall(self.oudata)            
    def handle_cmd(self,parse_data):
        pass
    
    '''指示下位机进行重传'''
    def handle_retry(self):
        self.oudata="please try!"
    def do_invalid(self):
        pass
    def do_message(self):
        '''解析获得帧里面的数据'''
        parse_data=None
        self.log.debug(u"得到的字节长度为：%d"%len(self.indata))
        if len(self.indata)==7:#固定帧
            startc1,cmdc,addrc,endc=struct.unpack(message_fmt1,self.indata)
            parse_data=Parsedata_struct(startc1,cmdc,addrc,0,0)
            self.log.debug("----1----startc1=%d cmdc=%d addrc=%d endc=%d---------"%(startc1,cmdc,addrc,endc))
        if len(self.indata)>15:#可变帧
            start_13bytes=None
            start_13bytes=self.indata[0:13]
            startc1,data_lenc,bao_countc,starc2,cmdc,addrc=struct.unpack(message_fmt2,start_13bytes)
            parse_data=Parsedata_struct(startc1,cmdc,addrc,data_lenc,bao_countc)
            self.log.debug("----2----bao_countc=%d cmdc=%d addrc=%d data_lenc=%d---------"%(bao_countc,cmdc,addrc,data_lenc))
        '''得到数据之后开始进一步处理'''
        try:
            if parse_data:
                '''进入文件处理命令'''
                if parse_data.cmd<CMD.CCMD_FILE_END and parse_data.cmd>CMD.CCMD_FILE_START:
                    self.handle_file(parse_data)
                elif parse_data.cmd<CMD.CCMD_SYSTEM_END and parse_data.cmd>CMD.CCMD_SYSTEM_START:
                    self.handle_system(parse_data)
                    
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
                self.oudata=None
                self.indata = self.request.recv(1024)
                if self.indata:
                    self.do_message()#主处理部分
                    #response = "{}: {}".format(self.cur_thread.name, self.indata)
                    #response=self.oudata
                    #self.request.sendall(response) 
                    #self.oudata=None
                    #self.log.debug("recived data is {} !".format(data))
            except Exception , e:
                self.log.error("The error is {}!".format(e))
                self.log.info(u"[handle]:客户端:%s已退出！"%self.c_address[0])
                break

#组装输出的字节序列        
def get_outdata(cmd,**kwargs):
    startc1=None
    data_len=kwargs.get('len',0)
    bao_count=kwargs.get('count',0)
    starc2=None
    hcmd=cmd
    haddr=kwargs.get('haddr',0)
    userdata=kwargs.get('userdata',None)
    cs=0
    endc=None    
    if kwargs.get('userdata',None):#可变帧
        pass
    else:#固定帧
        startc1,endc=CMD.FIXED_START_CHAR,CMD.FIXED_END_CHAR
        return struct.pack(outdata_fmt1,startc1,hcmd,haddr,endc)        

class Parsedata_struct(object):
    def __init__(self,startc1,cmdc,addrc,data_lenc,bao_countc):
        self.start=startc1
        self.cmd=cmdc
        self.addr=addrc
        self.data_len=data_lenc-5 #除去控制域和地址域
        self.bao_count=bao_countc #当前包是第几个包


class Xb_file(object):
    def __init__(self,ip_addr,root_data):
        self.filename=None #客户端传送过来的当前文件的文件名路径
        self.client_dictname=os.path.join(root_data,ip_addr)+'\\'#./data/ip_addr
        print self.client_dictname
        try:
            if not os.path.exists(root_data):
                os.mkdir(root_data)
            if not os.path.exists(self.client_dictname):
                os.mkdir(self.client_dictname)
        except:
            print "xb_file directory is error!"
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