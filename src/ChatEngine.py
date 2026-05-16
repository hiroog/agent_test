# 2026/04/21 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
import time
import threading
from collections import deque

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
import Assistant
import CommonAPI

#------------------------------------------------------------------------------

class SessionCache:
    SESSION_CACHE_DIR= 'threads'
    SESSION_QUEUE_SIZE= 20

    def __init__( self ):
        self.lock= threading.Lock()
        self.session_map= {}
        self.session_queue= []
        if not os.path.exists( self.SESSION_CACHE_DIR ):
            os.mkdir( self.SESSION_CACHE_DIR )

    def get_session_filename( self, session_id ):
        params= session_id.split( '_' )
        return  os.path.join( self.SESSION_CACHE_DIR, params[0]+'_'+params[1], session_id + '.json' )

    #--------------------------------------------------------------------------
    # Lock の中から呼ぶ想定の命令

    # メモリ解放
    def pop_queue_0( self, session_id ):
        if session_id in self.session_queue:
            self.session_queue.remove( session_id )
        self.session_queue.append( session_id )
        while len(self.session_queue) > self.SESSION_QUEUE_SIZE:
            pop_name= self.session_queue.pop(0)
            if pop_name in self.session_map:
                self.session_map[pop_name]= None
                del self.session_map[pop_name]
                print( 'Cache <<< %d >>> Removed %s' % (len(self.session_queue),pop_name) )

    def save_session_0( self, session ):
        session_id= session.get_id()
        save_file_name= self.get_session_filename( session_id )
        p,_= os.path.split( save_file_name )
        if not os.path.exists( p ):
            os.makedirs( p )
        session.save_session( save_file_name )

    def has_session_0( self, session_id ):
        if session_id in self.session_map:
            if self.session_map[session_id]:
                return  True
        session_filename= self.get_session_filename( session_id )
        if os.path.exists( session_filename ):
            session= CommonAPI.Session( session_id )
            session.load_session( session_filename )
            session.lock= threading.Lock()
            self.session_map[session_id]= session
            return  True
        return  False

    #--------------------------------------------------------------------------
    # Lock する命令

    def has_session( self, session_id ):
        with self.lock:
            return  self.has_session_0( session_id )

    def has_message( self, session_id, msg_id ):
        with self.lock:
            if self.has_session_0( session_id ):
                session= self.session_map[session_id]
                if session.get_info().get('msg_id','') == msg_id:
                    return  True
            return  False

    def get_session( self, session_id ):
        with self.lock:
            if not self.has_session_0( session_id ):
                session= CommonAPI.Session( session_id )
                session.get_info()['date']= CommonAPI.ExecTime().get_date()
                session.lock= threading.Lock()
                self.session_map[session_id]= session
            self.pop_queue_0( session_id )
            return  self.session_map[session_id]


#------------------------------------------------------------------------------

class EventQueue:
    def __init__( self ):
        self.lock= threading.Condition()
        self.queue= deque()
        self.break_flag= False

    def pop_event( self ):
        with self.lock:
            while len(self.queue) == 0 and not self.break_flag:
                self.lock.wait()
            if self.break_flag:
                return  None
            return  self.queue.popleft()

    def send_event( self, event ):
        with self.lock:
            self.queue.append( event )
            self.lock.notify()

    def stop_all( self ):
        with self.lock:
            self.break_flag= True
            self.lock.notify_all()

    def wait_break( self, timeout ):
        with self.lock:
            self.lock.wait( timeout=timeout )
            return  self.break_flag

class TaskWorker(threading.Thread):
    def __init__( self, event_queue ):
        super().__init__()
        self.event_queue= event_queue

    def run( self ):
        while True:
            event= self.event_queue.pop_event()
            if event is None:
                break
            event.exec()

class SchedulerWorker(threading.Thread):
    def __init__( self, queue, interval ):
        super().__init__()
        self.lock= threading.Lock()
        self.event_queue= queue
        self.interval= interval
        self.delayed_task_list= []

    def ts_to_localfmt( self, ts ):
        return  time.strftime( '%Y-%m-%d %H:%M:%S', time.localtime(ts) )

    def scheduler( self ):
        ts= time.time()
        run_list= []
        with self.lock:
            for index,task in enumerate(self.delayed_task_list):
                if task.ts <= ts:
                    run_list.append( task )
                    self.delayed_task_list[index]= None
            if run_list != []:
                task_list= []
                for task in self.delayed_task_list:
                    if task:
                        task_list.append( task )
                self.delayed_task_list= task_list
        for task in run_list:
            print( 'Run "%s" %s' % (task.name, self.ts_to_localfmt( task.ts )) )
            self.event_queue.send_event( task )

    def run( self ):
        while not self.event_queue.wait_break( timeout=self.interval ):
            self.scheduler()

    def push_task( self, task ):
        print( 'Add delayed task "%s" at %s' % (task.name, self.ts_to_localfmt(task.ts)) )
        with self.lock:
            self.delayed_task_list.append( task )


class TaskManager:
    TASK_WORKER_COUNT= 4
    SCHEDULAR_INTERVAL= 60

    def __init__( self ):
        self.worker_list= []
        self.schedular_worker= None
        self.event_queue= EventQueue()
        self.initialize()

    def finalize( self ):
        self.event_queue.stop_all()
        for wk in self.worker_list:
            wk.join()
        self.worker_list.clear()
        self.schedular_worker.join()
        print( 'TaskManager-Finalized', flush=True )

    def initialize( self ):
        for _ in range( self.TASK_WORKER_COUNT ):
            self.worker_list.append( TaskWorker( self.event_queue ) )
        self.schedular_worker= SchedulerWorker( self.event_queue, self.SCHEDULAR_INTERVAL )

    def start( self ):
        for wk in self.worker_list:
            wk.start()
        self.schedular_worker.start()

    def add_task( self, task ):
        self.event_queue.send_event( task )

    def add_delayed_task( self, task ):
        self.schedular_worker.push_task( task )


#------------------------------------------------------------------------------

class ChatEngineOptions(Assistant.AssistantOptions):
    def __init__( self, **args ):
        super().__init__()
        self.preset= 'chatbot'
        self.response_all= True
        self.dm_enabled= False
        self.assistant_mode= False
        self.task_schedular= False
        self.channel_allow_list= []         # channel-id or user-id
        self.channel_post_allow_list= []
        self.apply_params( args )


#------------------------------------------------------------------------------

class ChatEngine:
    def __init__( self, options ):
        self.options= options
        self.task_manager= None
        if self.options.task_schedular:
            self.task_manager= TaskManager()
            self.task_manager.start()
        self.session_cache= SessionCache()
        self.assistant= Assistant.Assistant( options )

    def close( self ):
        if self.task_manager:
            self.task_manager.finalize()
            self.task_manager= None

    #--------------------------------------------------------------------------
    # Assistant API

    # Chat 送信
        # session_id = セッション(スレッド)を識別できる固有文字列 (必須)
        # prompt = ユーザー入力 (必須)
        # msg_id = 同一メッセージかどうか判定する場合のみ必要。不要なら ''
        # msg_info = スレッド(セッション)ログに記録したい情報。不要なら {}
    def bot( self, session_id, prompt, msg_id, msg_info ):
        with CommonAPI.ExecTime( 'Generate' ):
            session= self.session_cache.get_session( session_id )
            with session.get_lock():
                session.get_info()['mtime']= CommonAPI.ExecTime().get_date()
                session.get_info()['msg_id']= msg_id
                session.get_info().update( msg_info )
                try:
                    if True:
                        input_obj= {
                            'prompt': prompt
                        }
                        response,status_code,session= self.assistant.generate_text2( input_obj, session )
                        if status_code != 200:
                            response= '\nserver error: %d\n' % status_code
                    else:
                        response= '返答だよ'
                finally:
                    self.session_cache.save_session_0( session )
        return  response

    def has_message( self, session_id, msg_id ):
        return  self.session_cache.has_message( session_id, msg_id )

    def has_session( self, session_id ):
        return  self.session_cache.has_session( session_id )


#------------------------------------------------------------------------------

class task_msg:
    def __init__( self, msg, ts= 0 ):
        self.name= msg
        self.ts= ts
    def exec( self ):
        print( 'TASK ', self.name )


def main( argv ):
    acount= len(argv)
    try:
        taskman= TaskManager()
        taskman.start()
        ts= time.time() + 5
        print( ts )
        taskman.add_delayed_task( task_msg( 'Delayed task', ts ) )
        for _ in range(10):
            taskman.add_task( task_msg( 'AAAA' ) ) 
        time.sleep( 20 )
    finally:
        taskman.finalize()
    return  0

if __name__ == '__main__':
    sys.exit( main( sys.argv ) )


