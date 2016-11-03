#-*- coding:utf-8 -*-
import time
import socket
import threading
import SocketServer
import logging
import logging.config
import ConfigParser#读取配置文件的库
import os.path
import struct

from handler import Handler

class ThreadedTCPRequestHandler(SocketServer.BaseRequestHandler):

    def handle(self):
        #得到log
        logging.config.fileConfig("log.conf")       
        log=logging.getLogger("simpleExample")
        
        #初始化处理
        h=Handler(self.request,self.client_address,threading.current_thread(),log)
        log.info("{} comming!".format(self.client_address)) 
        
        #主处理程序
        h.handle()

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass

def client(ip, port, message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, port))
    count=0
    starc1,cmdc,addrc,endc=16,20,1,22
    request=struct.pack('!BBIB',starc1,cmdc,addrc,endc)
    print u"得到的字节流长度为%d"%len(request)
    try:
        while (count<9):        
            sock.sendall(request)
            response = sock.recv(1024)
            print "Received: {}".format(response)
            count=count+1
    finally:
        sock.close()

if __name__ == "__main__":
    print __file__
    ini_ok=False
    log_ok=False
    if os.path.exists("xb.ini") and os.path.exists("log.conf"):
        #配置文件的读取
        try:
            cf=ConfigParser.ConfigParser()
            cf.read('xb.ini')
            HOST,PORT=cf.get("host","host"),int(cf.get("host","port"))
            ini_ok=True
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
            logging.config.fileConfig("log.conf")
            log_main=logging.getLogger("simpleExample") 
            log_ok=True
        except:
            log_ok=False
            print u"读取log.conf文件出错！，请检查文件格式是否正确！"         
               
        if ini_ok and log_ok:
            server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
            ip, port = server.server_address
            server.allow_reuse_address=True

            # Start a thread with the server -- that thread will then start one
            # more thread for each request
            server_thread = threading.Thread(target=server.serve_forever)
            # Exit the server thread when the main thread terminates
            server_thread.daemon = True
            server_thread.start()
            log_main.info("Server loop running in thread: %s"%server_thread.name)

            client(ip, port, "Hello World 1")
            client(ip, port, "Hello World 2")
            client(ip, port, "Hello World 3")

            server.shutdown()
            server.server_close()
        else:
            print u"退出。。。。。！"
    else:
        print u"无相关的配置文件，请检查xb.ini和log.conf文件是否存在！"