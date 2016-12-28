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
'''
import urllib

def getHtml(url):
    page=urllib.urlopen(url)
    html=page.read()
    return html

html=getHtml("http://tieba.baidu.com/p/2738151262")

print html
'''

##例程1 linux多进程测试
'''
import os

def children():
    print 'A new child:',os.getpid()
    print 'Parent id is:',os.getppid()
    os._exit(0)
    
def parent():
    while True:
        
        newpid = os.fork()#fork只能用在linux系统，纠结
        print newpid
        if newpid==0:
            
            children()
        else:
            pids=(os.getpid(),newpid)
            print "parent:%d,child:%d"%pids
            print "parent parent:",os.getppid()
        if raw_input()=='q':
            break
        
if __name__=="__main__":
    parent()
'''

##例程2 windows多进程测试
'''
from multiprocessing import Process
import os

#子进程要执行的代码
def run_proc(name):
    print 'Run child process %s (%s)...'%(name,os.getpid())
    
if __name__=="__main__":
    print "Parent process %s."%os.getpid()
    p=Process(target=run_proc,args=('test',))
    print 'Process will start.'
    p.start()
    p.join()
    print 'Process end'
'''

##例程3 Pool线程池

'''
对Pool对象调用join()方法会等待所有子进程执行完毕，调用join()之前必须先调用close()，
调用close()之后就不能继续添加新的Process了。

请注意输出的结果，task 0，1，2，3是立刻执行的，
而task4要等待前面某个task完成后才执行，这是因为Pool的默认大小在我的电脑上是4，
因此，最多同时执行4个进程。这是Pool有意设计的限制，并不是操作系统的限制。如果改成：
p = Pool(5)
'''


'''
from multiprocessing import Pool
import os, time, random

def long_time_task(name):
    print 'Run task %s (%s)...' % (name, os.getpid())
    start = time.time()
    time.sleep(random.random() * 3)
    end = time.time()
    print 'Task %s runs %0.2f seconds.' % (name, (end - start))

if __name__=='__main__':
    print 'Parent process %s.' % os.getpid()
    p = Pool()
    for i in range(5):
        p.apply_async(long_time_task, args=(i,))
    print 'Waiting for all subprocesses done...'
    p.close()
    p.join()
    print 'All subprocesses done.'
'''

##例程4 进程间的通讯
'''
Process之间肯定是需要通信的，操作系统提供了很多机制来实现进程间的通信。
Python的multiprocessing模块包装了底层的机制，提供了Queue、Pipes等多种方式来交换数据。
'''
from multiprocessing import Process, Queue
import os,time,random


#写数据进程执行的代码：
def write(q):
    for value in ['A','B','C']:
        print 'Put %s to queue...'%value
        q.put(value)
        time.sleep(random.random())
        
        
#读取数据进程执行的代码：
def read(q):
    while True:
        value=q.get(True)
        print 'Get %s from queue.'%value
        
        
if __name__=="__main__":
    #父进程创建Queue，并传给各个子进程：
    q=Queue()
    pw=Process(target=write,args=(q,))
    pr=Process(target=read,args=(q,))
    #启动子进程pw，写入：
    pw.start()
    #启动子进程pr,读出：
    pr.start()
    #等待pw结束
    pw.join()
    #pr进程里死循环，无法等待其结束，只能强制终止
    pr.terminate()