#-*- coding: utf-8 -*-
import os,time,glob
from multiprocessing import Process,Queue
import logging
import logging.config
import ConfigParser#读取配置文件的库
import os.path
import struct
import socket
import signal

import cmd as CMD

import sys 
reload(sys) # Python2.5 初始化后会删除 sys.setdefaultencoding 这个方法，我们需要重新载入 
sys.setdefaultencoding('gbk')#为了能够正确格式化存入文件

'''一定要加这个感叹号，感觉有点奇怪'''
#固定帧格式 起始字节：控制字节：地址4字节：结束字节
cmessage_fmt1='!BBIB'

#可变帧格式，这里注意只取需要的前13个字节
#起始字节：长度2字节：包计数4字节：启动字节：控制字节：地址4字节:用户数据（n):CS(校验字节)：结束字节
#长度2字节包括的内容是：控制字节+地址字节+用户数据的总长度
#校验范围是：控制字节+地址字节+用户数据
#可变帧中包计数为零的包表示不是文件数据，是文件名
cmessage_fmt2='!BHIBBI'


coutdata_fmt1='!BBIB'

class Client:
    def __init__(self,addr,host,port,**kwargs):
        self.sock=None
        self.addr=addr
        self.host='127.0.0.1'
        self.port=8837
        #self.path=data_path
        self.indata=None
        self.oudata=None
        self.parsedata=None
        self.oufmt1='!BBIB'
        self.oufmt2='!BHIBBI'
        self.queue_task,self.queue_error=kwargs.get('queue_task',None)
        self.log=kwargs.get('log',None)
        self.timeout=15
        self.xbfile=None
        self.tx_len=500#读取文件的长度，还有FileInfo里面
        self.root=kwargs.get('root',None)
        
    '''data_rootpath表示在配置文件中设置的客户端数据文件夹'''
    def create_uploadfilepath(self):
        uploadfilepath=self.xbfile.filepath[len(self.root):]
        self.log.info(u'[create_uploadfilepath]:得到的结果为:%s'%uploadfilepath)
        return uploadfilepath
    def file_upload(self,flag):#flag为真则读取下一数据组，为假则不读取下一组，接着发送上一组
        '''define upload file method!'''
        try:
            if flag:
                
                self.xbfile.curframe_count=self.xbfile.curframe_count+1
                self.xbfile.nextframe_count=self.xbfile.nextframe_count+1            
                temp_buff=self.xbfile.fd.read(self.tx_len)
                self.xbfile.set_databuff(temp_buff)
                #self.log.debug(u'[file_upload]读出的内容是：%s'%self.xbfile.get_databuff())
                if self.make_oudata(CMD.CMAKE_MAKEFILEDATA,userdata=self.xbfile):
                    self.sock.sendall(self.oudata)
            else:
                if self.make_oudata(CMD.CMAKE_MAKEFILEDATA,userdata=self.xbfile):
                    self.sock.sendall(self.oudata)                
        except Exception,e:
            self.log.error(u'[file_upload]{}'.format(e))
            if self.make_oudata(CMD.CMAKE_MAKEFILEERROR):#固定帧
                self.sock.sendall(self.oudata)
        
    def do_file(self):
        cmd=self.parsedata.get_cmd()
        if cmd==CMD.HCMD_FILE_CONFIRM_START:
            #self.xbfile.curframe_count=0
            #self.xbfile.nextframe_count=1
            self.file_upload(True)
        elif cmd==CMD.HCMD_FILE_COMPLETE:#文件传输完成
            self.log.debug(u'[do_file]文件传输完毕...')
            if self.deal_task():#执行下一个任务
                self.log.debug(u'[do_file]发送任务正在处理...')
            else:
                self.do_hartbeat()
        elif cmd==CMD.HCMD_FILE_NEXT_TRANSFERRING:#主站接收到的数据正确，接着传下一个
            self.file_upload(True)
        elif cmd==CMD.HCMD_FILE_RETRYTHIS:#主站接收到的数据错误，重传
            
            self.xbfile.try_times=self.xbfile.try_times-1
            if not self.xbfile.try_times:
                self.file_upload(False)
            else:
                self.log.error(u'[do_file]重传失败'.format(e))
                if self.make_oudata(CMD.CMAKE_MAKEFILEERROR):#固定帧
                    self.sock.sendall(self.oudata)
        else:
            self.log.error(u'[do_file]未定义的文件处理命令:%d！'%cmd)
    
    def deal_task(self):
        task_flag=False
        if not self.queue_task.empty(): 
            temp_task=self.queue_task.get()
            if isinstance(temp_task,dict) and temp_task.has_key('file'):
                if os.path.exists(temp_task.get('file',None)) and \
                   os.path.isfile(temp_task.get('file',None)):#是文件而且存在
                    
                    self.xbfile=None
                    self.xbfile=FileInfo(temp_task.get('file',None))
                    if not self.xbfile.file_len==0:#防止读到的文件为空文件2016-12-23
                        
                        #self.xbfile.set_relfilename(self.create_uploadfilepath())
                    
                        self.log.debug(u'[deal_task]文件路径为：%s'%temp_task.get('file',None))
                        #self.xbfile.set_filepath(temp_task.get('file',None))
                        if self.make_oudata(CMD.CMAKE_STARTFILE,userdata=self.xbfile):
                            self.sock.sendall(self.oudata)
                            task_flag=True
                    else:
                        task_flag=False
                else:
                    task_flag=False
                    self.log.error(u'[deal_task]文件不存在！')
            else:
                self.log.error(u"[deal_task]从任务队列得到的任务格式错误:{}".format(temp_task))
                task_flag=False
        else:
            self.log.info(u"[deal_task]无任务")
            task_flag=False
        return task_flag
    def do_system(self):
        cmd=self.parsedata.get_cmd()
        if cmd==CMD.HCMD_CONNECT_RES:#接收到连接命令后主站响应的命令号
#如果子站有任务，则开始相应的任务，没有的话发送心跳到主站保持连接
            if self.deal_task():
                self.log.debug(u'[do_system]发送任务正在处理...')
            else:
                self.do_hartbeat()#发送心跳包
        elif cmd==CMD.HCMD_CMD_HARTEAT:
            if self.deal_task():
                self.log.debug(u'[do_system]发送任务正在处理...')
            else:
                self.do_hartbeat()#发送心跳包
        else:
            self.do_hartbeat()#发送心跳包
    
    def do_invalid(self):
        self.make_oudata(CMD.CMAKE_CMD_INVALID)
        self.sock.sendall(self.oudata)
        return True
    
    def do_hartbeat(self):
        time.sleep(8)
        self.log.info(u".")
        self.make_oudata(CMD.CMAKE_HARTBEAT)
        self.sock.sendall(self.oudata)
        return True
    
    def connect(self):
        '''starting connect a host'''
        try:
            socket.setdefaulttimeout(self.timeout)
            self.sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)            
            self.sock.connect((self.host,self.port))
            self.make_oudata(CMD.CMAKE_CONNECT)     #制造连接指令
            self.sock.sendall(self.oudata)
        except Exception,e:
            self.log.error(u"无法连接主站-错误:{}".format(e))
            if not self.queue_error.full():
                self.log.error(u"[connect]压入重启队列")
                self.queue_error.put('c1_restart')#告诉主进程开始重启该程序            
    def make_oudata(self,cmake,**kwargs):
        startc1=None
        data_len=None
        bao_count=None
        startc2=None
        cmd=None
        caddr=self.addr
        userdata=None
        dataobject=kwargs.get('userdata',None)
        cs=0
        endc=None
        
        self.oudata=None
        
        if dataobject:#可变帧
            startc1=CMD.VERIABLE_START_CHAR
            startc2=CMD.VERIABLE_START_CHAR
            endc=CMD.VERIABLE_END_CHAR
            if cmake==CMD.CMAKE_STARTFILE and isinstance(dataobject,FileInfo):
                cmd=CMD.CCMD_FILE_REQ_START#请求传输文件
                dataobject.set_databuff(dataobject.get_filename())
                data_len=CMD.CONTROL_LEN+CMD.ADDR_LEN+dataobject.get_datalen()
                self.log.debug(u'[make_oudata]data_len的长度为：%d'%data_len)
                bao_count=0
                dataobject.set_databuff(dataobject.get_filename())
                userdata=dataobject.get_databuff()
                #self.log.debug(u'[make_oudata]userdata is:%s'%userdata)
            elif cmake==CMD.CMAKE_MAKEFILEDATA and isinstance(dataobject,FileInfo):
                if  dataobject.file_bao_num==dataobject.curframe_count:
                    cmd=CMD.CCMD_FILE_COMPLETE#正在传输文件,这是最后一个包
                    dataobject.close()
                elif dataobject.curframe_count<dataobject.file_bao_num:
                    cmd=CMD.CCMD_FILE_TRANSFERRING#正在传输文件
                else:
                    self.log.debug(u'[make_oudata]大于传输的包数，不科学！')
                    return False
                data_len=CMD.CONTROL_LEN+CMD.ADDR_LEN+dataobject.get_datalen()
                self.log.debug(u'[make_oudata]data_len的长度为：%d'%data_len)
                bao_count=dataobject.curframe_count
                #dataobject.set_databuff(dataobject.get_filename())#不能在这里设置缓冲的数据！大意了！
                userdata=dataobject.get_databuff()
                #self.log.debug(u'[make_oudata]userdata is:%s'%userdata)
            else:
                self.log.error(u'[make_oudata]无效的可变帧制造命令:cmake:%d!'%cmake)
                return False
            
            s_len=len(userdata)
            frame_fmt1=self.oufmt2
            frame1,frame2=None,None
            frame_fmt2="!BB"
            #self.log.debug(u'[make_oudata]得到的格式化字符串是：%s'%frame_fmt)
            try:
                frame1=struct.pack(frame_fmt1,startc1,data_len,bao_count,startc2,cmd,caddr) 
                frame2=struct.pack(frame_fmt2,cs,endc) 
                self.oudata=frame1+userdata+frame2
            except Exception,e:
                self.log.error(u'[make_oudata]生成可变帧时错误：{}'.format(e))
                return False
            #self.log.debug(u'[make_oudata]生成可变帧！')
            return True
        else:       #固定帧
            #'''----------生成固定帧报文-----------'''
            startc1=CMD.FIXED_START_CHAR
            endc=CMD.FIXED_END_CHAR
            
            if cmake==CMD.CMAKE_CONNECT:#主动连接主站
                cmd=CMD.CCMD_CONNECT_REQ
                
        
            elif cmake==CMD.CMAKE_UNCONNECT:#请求断开连接
                cmd=CMD.CCMD_UNCONNECT_REQ
            
            elif cmake==CMD.CMAKE_CMD_INVALID:#主站下发的数据指令无效
                cmd=CMD.CCMD_CMD_INVALID            
               
            
            elif cmake==CMD.CMAKE_HARTBEAT:#发送心跳到主站
                cmd=CMD.CCMD_CMD_HARTBEAT
            elif cmake==CMD.CMAKE_MAKEFILEERROR:#文件操作错误
                cmd=CMD.CCMD_FILE_ERROR
            else:
                self.log.debug(u"不能生成该命令！")
                return False
            
            self.oudata=struct.pack(self.oufmt1,\
                                    startc1,\
                                    cmd,\
                                    caddr,\
                                    endc)
            
            return True
        return False    
    def parse_cmd(self):
        pass
    
    
    
    def handle(self):
        ##主要处理部分
        #try:
            
        cmd=self.parsedata.get_cmd()
        if cmd>CMD.HCMD_FILE_START and cmd<CMD.HCMD_FILE_END:#处理文件命令
            self.do_file()
        elif cmd>CMD.HCMD_SYSTEM_START and cmd<CMD.HCMD_SYSTEM_END:#处理系统命令
            self.do_system()
        else:#指令无效
            self.do_invalid()
        #except Exception,e:
            #self.log.error(u"[handle]:{}".format(e))            
            ##这里需要添加一个异常处理程序，或者重启，或者重新生成一个新程序
    def run(self):
        '''运行这个函数之前需要先运行connect函数来建立有效的套接字'''
        while True:
            try:
                
                self.indata=self.sock.recv(1024)
                self.log.debug(u"[C]原始字节长度为：%d"%len(self.indata))
                if self.indata:
                    self.parsedata=cparsedata_struct(self.indata)
                    #self.log.debug(u"CMD=%d"%self.parsedata.get_cmd())
                    if self.parsedata.is_valid:
                        self.handle()
                    else:
                        ##这里可以做一个日志记录和发送一个指令无效的命令
                        self.do_invalid()
                        self.log.error(u"[C]命令无效！")
                    
                else:
                    self.connect()
            except Exception,e:
                self.log.error(u"[handle]:{}".format(e))
                self.log.info(u'[handle]:客户端失主站连接...!')
                
                if not self.queue_error.full():
                    self.log.error(u"[run]压入重启队列")
                    self.queue_error.put('c1_restart')#告诉主进程开始重启该程序
                    
                time.sleep(5)
                    
   
   
class FileInfo(object):
    '''
    在传输文件的时候记录其传输动态
    '''
    def __init__(self,filepath):
        self.filepath=filepath#"c:\pyhth\test.txt"
        self.relfilename=None
        self.curframe_count=0 #开始传输时从1开始
        self.nextframe_count=1
        self.databuf=None
        self.fd=open(self.filepath,'rb')
        self.try_times=5#文件传输错误时重传次数
        self.fd.seek(0,os.SEEK_END)
        self.file_len=self.fd.tell()
        self.fd.seek(0,os.SEEK_SET)#移动回0处
        self.bao_len=500#设每个文件一次读取10个字节
        #print u'[FileInfo]文件长度为：%d'%self.file_len
        temp=0
        if self.file_len%self.bao_len:#如果有余数则加1，无余数则不用加1
            self.file_bao_num=self.file_len/self.bao_len+1 
        else:
            self.file_bao_num=self.file_len/self.bao_len
        
        
    def get_curframe_count(self):
        return self.curframe_count
    
    def get_nextframe_count(self):
        return self.nextframe_count
    
    def add_baocount(self):
        self.curframe_bao=self.curframe_bao+1
        self.nextframe_bao=self.nextframe_bao+1
        return True
    
    def get_filename(self):
        return os.path.split(self.filepath)[1]
    
    def get_relfilename(self):
        return self.relfilename
    
    def set_relfilename(self,filepath):
        self.relfilename=filepath
        return True
    def get_databuff(self):
        return self.databuf
    
    def set_databuff(self,data):
        #self.databuf=None
        self.databuf=data
        return True
    
    def get_datalen(self):
        return len(self.databuf)
    
    def get_filepath(self):
        return self.filepath
        
    def set_filepath(self,filepath):
        self.filepath=filepath
        return True
    
    def close(self):
        if self.fd:            
            self.fd.close()
        return True
class cparsedata_struct(object):
    '''This is parse data object!
    date:2016-12-21
    Author:Zhang Qifang
    '''
    def __init__(self,indata):
        self.indata=indata
        self.infmt1='!BBIB'#接收到主站数据的两种格式的报文
        self.infmt2='!BHIBBI'
        self.headfmt='B' #获得起始帧
        try:
            if not self.is_fixed_frame():
                self.startc1,self.datalen,self.baocount,self.startc2,\
                    self.cmd,self.addr=struct.unpack(self.infmt2,self.indata[:13])
                self.userdata=self.indata[13:-2]
                self.checksum=self.indata[-2]
            else:
                self.startc1,self.cmd,self.addr,self.endc=struct.unpack(self.infmt1,self.indata)
                self.userdata=0
                self.checksum=None
            self.is_valid=True
        except Exception,e:
            print u'[cparsedata_struct]:{}'.format(e)
            self.is_valid=False
    def get_cmd(self):
        return self.cmd
    
    
    def get_startc1(self):
        '''##获得原始数据的帧头，用来判别帧的类型##'''
        startc1=self.indata[0]
        return struct.unpack(self.headfmt,startc1)
        #return startc1
    
    def get_hostaddr(self):
        return self.addr
    
    def get_userdata(self):
        return self.userdata
    
    def get_checksum(self):
        return self.checksum
    
    def is_fixed_frame(self):
        if self.get_startc1()==CMD.VERIABLE_START_CHAR:#是可变帧
            #print u'可变帧'
            return False
        else:#是固定帧
            #print u'固定帧'
            return True
            
                
#这个进程是处理客户端任务的
def process_client(host,port,addr,q,root_path):
    
    #得到log
    
    logging.config.fileConfig("clog.conf")       
    log=logging.getLogger("simpleExample")  
    log.info(u'[process_client]开始连接主站！')
    c=Client(addr,host,addr,queue_task=q,log=log,root=root_path)
    c.connect()
    log.info(u'[process_client]已连接到主站！')
    c.run()

#这个进程是扫描文件夹获得数据文件任务的
#扫描文件策略
#顺序扫描，可以预定时间，比如15分钟扫一次之类的
#这里管道可以设置为100之类的，存完之后判断管道是否为空，空则立马塞数据进去

def process_scan_directory(root_path,q_task,q_error):
    
    
    try:
        
        if os.path.exists(root_path) and os.path.isdir(root_path):
            print u'[扫描]正在进入数据文件夹......'
            scan_files=Scan_Dir(root_path)
            f_task={}
            
            while True:
                #time.sleep(1000)
                #log.info(u'[process_scan_directory]正在扫描！')
                scan_files.fresh_filelist()
                files=scan_files.get_allfiles()
                #log.info(u'[process_scan_directory]扫描完毕！')
                time.sleep(10)#这个一定要加，万一行波设备正在写入文件，这里就等待10秒中，等数据完成写入
                while True:
                    try:
                        
                        if q_task.empty():
                            i=99
                            while i:
                                i=i-1
                                f_task['file']=files.pop()
                                q_task.put(f_task)
                    except Exception,e:
                        #log.info(u'[process_scan_directory]文件任务已经分配完毕：{}！'.format(e))
                        break
            
        else:
            print u'该文件夹不存在，请重新配置！'
    except Exception,e:
        #log.error(u'[process_scan_directory]扫描文件夹出错！')
        print "[process_scan_directory]{}".format(e)
        if not q_error.full():
            q_error.put('c2_restart')#告诉主进程开始重启该程序
    

def list_alldir(path):
    temp_list=os.listdir(path)
    dir_list=[]
    for temp in temp_list:
        t=os.path.join(path,temp)
        if os.path.isdir(t):
            dir_list.append(t)
            d=list_alldir(t)
            for temp in d:
                dir_list.append(temp)
    return dir_list
class Scan_Dir(object):
    def __init__(self,dirpath):
        self.rootpath=dirpath
        self.file_list=[]
        self.dir_list=[]
    
    def fresh_filelist(self):
        #先搜索出所有的文件夹
        self.dir_list=list_alldir(self.rootpath)
        #print u'{}'.format(self.dir_list)
        fd=open(".\\tmp\\dir.txt",'w')
        for temp in self.dir_list:
            
            fd.write(u'%s\n'%temp)
        fd.close()
        file_list=[]
        
        for temp in self.dir_list:
            s=temp+"\\*.py"
            l=glob.glob(s)
            for temp in l:
                self.file_list.append(temp)
        fd=open(".\\tmp\\file.txt",'w')
        for p in self.file_list:
            fd.write(u'%s\n'%p)
        fd.close()
      
    def get_allfiles(self,**kwargs):
        return self.file_list
        

if __name__=='__main__':
    #print __file__
    #result=glob.glob(r'e:/Python/xb_project/git_project/xb/source/*.py')
    #for temp in result:
        #print temp
    #print type(result) #List类型  
    queue_task=Queue(100)
    queue_error=Queue(2)
    ini_ok=False
    log_ok=False
    if os.path.exists("xb.ini") and os.path.exists("log.conf"):
        #配置文件的读取
        try:
            cf=ConfigParser.ConfigParser()
            cf.read('xb.ini')
            HOST,PORT=cf.get("host","host"),int(cf.get("host","port"))
            DATA_PATH=cf.get("path","data_path")
            ADDR=int(cf.get("client","client_addr"))
            ROOT_PATH=cf.get("client","path")
            ini_ok=True
            print u'连接主机:%s的端口:%d'%(HOST,PORT)
            print u'本机逻辑地址为:%d'%ADDR
            print u'客户端数据文件夹在：%s'%os.path.abspath(ROOT_PATH)
            """
            s=cf.sections()
            o=cf.options("host")
            v=cf.items("host")
        
            print 'section',s
            print 'options',o
            print 'db',v
            """
        except:
            ini_ok=False
            print u"读取xb.ini文件错误，请检查文件格式是否正确！"
        #log配置文件读取
        try:
            logging.config.fileConfig("clog.conf")
            log_main=logging.getLogger("simpleExample") 
            logging.config.fileConfig("mlog.conf")
            log_main=logging.getLogger("simpleExample") 
            log_ok=True
        except:
            log_ok=False
            print u"读取log.conf文件出错！，请检查文件格式是否正确！"          
        if not log_ok and not ini_ok:
            os._exit(0)
        else:#开始进入启动流程
            process1=Process(target=process_client,args=(HOST,PORT,ADDR,[queue_task,queue_error],ROOT_PATH))
            process2=Process(target=process_scan_directory,args=(ROOT_PATH,queue_task,queue_error))

            process2.start()
            
            #dir_scan=Scan_Dir('e:\\Python')
            #dir_scan.fresh_filelist()
            process1.start()
            log_main.info(u'[main]开始进程任务....')
            #process1.join()
            p1_restart,p2_restart=None,None
            while True:
                while  not queue_error.empty():
                    e=queue_error.get()
                    if e=='c1_restart':
                        p1_restart=True
                    elif e=='c2_restart':
                        p2_restart=True
                    else:
                        p1_restart=False
                        p2_restart=False
                if  p1_restart:
                    process1.terminate()
                    process1=None #这个一定要清除！
                    process1=Process(target=process_client,args=(HOST,PORT,ADDR,[queue_task,queue_error],ROOT_PATH))
                    process1.start()
                    p1_restart=False
                    log_main.info(u'重启客户端进程！')
                    #print u'重启客户端程序......!'
                    time.sleep(5)
                if  p2_restart:
                    process2.terminate()
                    process2=None #这个一定要清除！
                    process2=Process(target=process_scan_directory,args=(ROOT_PATH,log_main,queue_task,queue_error))
                    process2.start()
                    log_main.info(u'重启文件收集进程')
                    #print u'重启文件收集程序......!'
                    p2_restart=False
                time.sleep(10)
                
                #queue_task.put({'file':'.\\tmp\\xb.log'})#压入任务的必须是绝对路径的
    else:
        print u"请检查配置文件是否存在........"