# 2026/04/21 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
import threading
import time
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
import Assistant
import CommonAPI
from SlackAPI import save_json, load_json

# env:
#  SLACK_BOT_TOKEN or SLACK_API_TOKEN
#  SLACK_APP_TOKEN

# Slack APP
#  Socket Mode
# 
#      Enable Socket Mode => ON
#
#        Generate an app-level token to enable Socket Mode
#          1. Token Name: ～
#          2. [Generate]
#        Token                   => SLACK_APP_TOKEN
#
#  OAuth & Permissions
#
#      BotTokenScope
#
#          app_mention:read
#          channels:history
#          channels:read
#          chat:write
#          chat:write.customize
#          groups:history
#          groups:read
#          groups:write
#          reactions:read
#          reactions:write
#          users:read
#
#  Event Subscriptions
#
#      Enable Events => ON
#
#      Subscribe to bot events
#
#          app_mention
#          message.channels
#          message.groups
#
#  Install App
#      [Install to Workspace]
#      Bot User OAuth Token      => SLACK_BOT_TOKEN (or SLACK_API_TOKEN)

#------------------------------------------------------------------------------

class ThreadCache:
    THREAD_CACHE_DIR= 'threads'

    def __init__( self ):
        self.lock= threading.Lock()
        self.thread_map= {}
        if not os.path.exists( self.THREAD_CACHE_DIR ):
            os.mkdir( self.THREAD_CACHE_DIR )

    def get_thread_file_name( self, thread_id ):
        params= thread_id.split( '_' )
        return  os.path.join( self.THREAD_CACHE_DIR, params[0]+'_'+params[1], thread_id + '.json' )

    def save_thread_0( self, thread_id ):
        if thread_id in self.thread_map:
            save_file_name= self.get_thread_file_name( thread_id )
            p,_= os.path.split( save_file_name )
            if not os.path.exists( p ):
                os.makedirs( p )
            session= self.thread_map[thread_id]
            session.save_session( save_file_name )

    def has_thread_0( self, thread_id ):
        if thread_id in self.thread_map:
            return  True
        thread_file= self.get_thread_file_name( thread_id )
        if os.path.exists( thread_file ):
            session= CommonAPI.Session( thread_id )
            session.load_session( thread_file )
            session.lock= threading.Lock()
            self.thread_map[thread_id]= session
            return  True
        return  False

    def has_thread( self, thread_id ):
        with self.lock:
            return  self.has_thread_0( thread_id )

    def has_message( self, thread_id, msg_id ):
        with self.lock:
            if self.has_thread_0( thread_id ):
                session= self.thread_map[thread_id]
                if session.get_info().get('msg_id','') == msg_id:
                    return  True
            return  False

    def get_session( self, thread_id ):
        with self.lock:
            if not self.has_thread_0( thread_id ):
                session= CommonAPI.Session( thread_id )
                session.get_info()['date']= CommonAPI.ExecTime().get_date()
                session.lock= threading.Lock()
                self.thread_map[thread_id]= session
                #{ 'thread_id': thread_id, 'message_list': [], 'date': ExecTime().get_date(), 'mtime': '', 'msg_id': '' }
            return  self.thread_map[thread_id]


#------------------------------------------------------------------------------

class SlackBotOptions(Assistant.AssistantOptions):
    def __init__( self, **args ):
        super().__init__()
        self.preset= 'chatbot'
        self.response_all= True
        self.apply_params( args )


#------------------------------------------------------------------------------

# thread_info
# {
#     "thread_id": "slack_thread_ts",
#     "date": "DATE",
#     "mtime": "MTIME",
#     "msg_id": "GUID",
#     "message_list": [],
#     "queue": []
# }

class SlackBot:
    def __init__( self, options ):
        self.options= options
        self.thread_cache= ThreadCache()
        self.assistant= Assistant.Assistant( options )

    #--------------------------------------------------------------------------
    # Assistant API

        # thread_id = スレッド(セッション)を識別できる固有文字列 (必須)
        # prompt = ユーザー入力 (必須)
        # msg_id = 同一メッセージかどうか判定する場合のみ必要。不要なら ''
        # msg_info = スレッド(セッション)ログに記録したい情報。不要なら {}
    def bot( self, thread_id, prompt, msg_id, msg_info ):
        with CommonAPI.ExecTime( 'Generate' ):
            session= self.thread_cache.get_session( thread_id )
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
                    self.thread_cache.save_thread_0( thread_id )
        return  response

    #--------------------------------------------------------------------------
    # Slack API

    def ts_to_local_time( self, ts ):
        try:
            t= float( ts )
        except (TypeError, ValueError):
            return  time.localtime()
        return  time.localtime( t )

    def get_thread_ts( self, message ):
        return  message.get( 'thread_ts' ) or message.get( 'ts' )

    def get_thread_id_0( self, ts ):
        params= ts.split( '.' )
        thread_id= time.strftime( 'slack_%Y%m%d_%H%M%S', self.ts_to_local_time( params[0] ) )
        thread_id+= '_' + params[1]
        print( '*************', thread_id )
        return  thread_id

    def get_thread_id( self, message ):
        return  self.get_thread_id_0( self.get_thread_ts( message ) )

    def send_message( self, say, thread_id, message, client ):
        msg_id= message.get( 'client_msg_id', '' )

        # すでに返答済み
        if self.thread_cache.has_message( thread_id, msg_id ):
            return

        thread_ts= self.get_thread_ts( message )

        # Reaction Mark
        channel= message.get( 'channel', '' )
        ts= message.get( 'ts', '' )
        try:
            reaction_mark= 'robot_face'
            client.reactions_add( channel=channel, timestamp=ts, name=reaction_mark )
        except Exception as e:
            print( f'Error reaction:{e}\n' )

        text= message.get( 'text', '' )
        user= message.get( 'user', '' )
        tsstr= time.strftime( '%Y-%m-%d %H:%M:%S', self.ts_to_local_time( ts ) )
        prompt= f'{tsstr} {user}: {text}'

        msg_info= {
            'channel': channel,
            'thread_ts': thread_ts,
        }

        reply_text= self.bot( thread_id, prompt, msg_id, msg_info )
        say( text=reply_text, thread_ts=thread_ts, blocks= [
                {
                    'type': 'markdown',
                    'text': reply_text
                }
            ])

    def event_app_mention( self, body, logger, say, client ):
        if self.options.debug_echo:
            print( '######(mention)' )
            print( body )
            print( '######(mention)' )

        message= body['event']
        thread_id= self.get_thread_id( message )

        # すでに参加済みなら無視
        if self.thread_cache.has_thread( thread_id ):
            return

        # 途中から参加
        self.send_message( say, thread_id, message, client )
        logger.info(f'mention replied to {message["ts"]} in channel {message["channel"]}')

    def event_message( self, message, say, logger, client ):
        if self.options.debug_echo:
            print( '$$$$$$<message>' )
            print( message )
            print( '$$$$$$<message>' )

        # DM は無視, Channel のみ
        if message.get('channel_type') == 'im':
            return

        # bot のメッセージは無視
        if message.get('bot_id'):
            return

        # 会話に参加していないスレッドは無視
        thread_id= self.get_thread_id( message )
        if not self.thread_cache.has_thread( thread_id ):
            return

        self.send_message( say, thread_id, message, client )
        logger.info(f'replied to {message["ts"]} in channel {message["channel"]}')


#------------------------------------------------------------------------------

slack_bot= None

def respound_within_3_seconds( ack ):
    ack()

def handle_app_mention_events( body, logger, say, client ):
    global slack_bot
    slack_bot.event_app_mention( body, logger, say, client )

def handle_message( message, say, logger, client ):
    global slack_bot
    slack_bot.event_message( message, say, logger, client )

def handle_message_events( body, logger ):
    message_type= body.get( 'type', '' )    # event_callback
    event= body.get( 'event', {} )
    event_type= event.get( 'type', '' )     # message
    subtype= event.get( 'subtype', '' )     # message_deleted/message_changed/bot_message
    channel= event.get( 'channel', '' )     # C0
    ts= event.get( 'ts', '' )
    text= f'receved {message_type} {event_type} {subtype} {channel} {ts}'
    print( text )
    logger.info( text )


#------------------------------------------------------------------------------

def usage():
    print( 'SlackBot v1.00 Hiroyuki Ogasawara' )
    print( 'usage: SlackBot [<options>' )
    print( 'options:' )
    print( '  --preset <preset>             default: chatbot' )
    print( '  --config <config_file>        default: config.txt' )
    print( '  --prompt_dir <dir>' )
    print( '  --provider <provider>' )
    print( '  --host <base_url>' )
    print( '  --model <model>' )
    print( '  --print' )
    print( '  --debug' )
    sys.exit( 1 )


def main( argv ):
    acount= len(argv)
    options= SlackBotOptions()
    ai= 1
    while ai < acount:
        arg= argv[ai]
        if arg[0] == '-':
            if arg == '--preset':
                ai= options.set_str( ai, argv, 'preset' )
            elif arg == '--config':
                ai= options.set_str( ai, argv, 'config_file' )
            elif arg == '--prompt_dir':
                ai= options.set_str( ai, argv, 'prompt_dir' )
            elif arg == '--provider':
                ai= options.set_str( ai, argv, 'provider' )
            elif arg == '--host':
                ai= options.set_str( ai, argv, 'base_url' )
            elif arg == '--model':
                ai= options.set_str( ai, argv, 'model' )
            elif arg == '--noverify':
                options.verify= False
            elif arg == '--print':
                options.print= True
            elif arg == '--debug':
                options.debug_echo= True
            else:
                print( 'Error: unknown option %s' % arg )
                usage()
            ai+= 1
        else:
            usage()

    global slack_bot
    slack_bot= SlackBot( options )

    app= App( token= os.environ.get('SLACK_BOT_TOKEN', os.environ.get('SLACK_API_TOKEN')) )
    app.event('app_mention')( ack=respound_within_3_seconds, lazy=[handle_app_mention_events] )
    app.message()(ack=respound_within_3_seconds, lazy=[handle_message])
    app.event('message')(ack=respound_within_3_seconds, lazy=[handle_message_events])
    handler= SocketModeHandler( app, os.environ['SLACK_APP_TOKEN'] )
    handler.start()

    return  0

if __name__ == '__main__':
    sys.exit( main( sys.argv ) )


