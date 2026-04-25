# 2026/04/21 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
import threading
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
import Assistant
from OllamaAPI4 import ExecTime
from SlackAPI import save_json, load_json

# env:
#  SLACK_BOT_TOKEN
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
#          chat:write
#          chat:write.customize
#          groups:history
#          reactions:read
#          reactions:write
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
#      Bot User OAuth Token      => SLACK_BOT_TOKEN

#------------------------------------------------------------------------------

class ThreadCache:
    THREAD_CACHE_DIR= 'threads'

    def __init__( self ):
        self.lock= threading.Lock()
        self.thread_map= {}
        self.thread_lock_map= {}
        if not os.path.exists( self.THREAD_CACHE_DIR ):
            os.mkdir( self.THREAD_CACHE_DIR )

    def get_thread_file_name( self, thread_id ):
        return  os.path.join( self.THREAD_CACHE_DIR, thread_id + '.json' )

    def save_thread_0( self, thread_id ):
        if thread_id in self.thread_map:
            save_json( self.get_thread_file_name( thread_id ), self.thread_map[thread_id] )

    def has_thread_0( self, thread_id ):
        if thread_id in self.thread_map:
            return  True
        thread_file= self.get_thread_file_name( thread_id )
        if os.path.exists( thread_file ):
            self.thread_map[thread_id]= load_json( thread_file )
            return  True
        return  False

    def has_thread( self, thread_id ):
        with self.lock:
            return  self.has_thread_0( thread_id )

    def has_message( self, thread_id, msg_id ):
        with self.lock:
            if self.has_thread_0( thread_id ):
                thread_info= self.thread_map[thread_id]
                if thread_info.get('msg_id','') == msg_id:
                    return  True
            return  False

    def get_thread_info( self, thread_id ):
        with self.lock:
            if not self.has_thread_0( thread_id ):
                self.thread_map[thread_id]= { 'thread_id': thread_id, 'message_list': [], 'date': ExecTime().get_date(), 'mtime': '', 'msg_id': '' }
            if thread_id not in self.thread_lock_map:
                self.thread_lock_map[thread_id]= threading.Lock()
            return  self.thread_map[thread_id],self.thread_lock_map[thread_id]


#------------------------------------------------------------------------------

class SlackBotOptions(Assistant.AssistantOptions):
    def __init__( self, **args ):
        super().__init__()
        self.preset= 'chatbot'
        self.debug_echo= True
        #---------------------------
        self.apply_params( args )


#------------------------------------------------------------------------------

# thread_info
# {
#     "thread_id": "thread_ts",
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

    def bot( self, thread_id, prompt, msg_id, channel ):
        with ExecTime( 'Generate' ):
            thread_info,thread_lock= self.thread_cache.get_thread_info( thread_id )
            with thread_lock:
                input_obj= {
                    'prompt': prompt,
                }
                thread_info['mtime']= ExecTime().get_date()
                thread_info['msg_id']= msg_id
                message_list= thread_info['message_list']
                try:
                    if True:
                        response,status_code,local_options= self.assistant.generate_text( input_obj, None, message_list )
                        local_options.tools= ''
                        thread_info['options']= local_options.__dict__
                        thread_info['channel']= channel
                    else:
                        response= '返答だよ'
                finally:
                    self.thread_cache.save_thread_0( thread_id )
        return  response


    #--------------------------------------------------------------------------
    # Slack API

    def get_thread_id( self, message ):
        return  message.get( 'thread_ts' ) or message.get( 'ts' )

    def send_message( self, say, thread_id, message, client ):
        msg_id= message.get( 'client_msg_id', '' )

        # すでに返答済み
        if self.thread_cache.has_message( thread_id, msg_id ):
            return

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
        prompt= f'{user}: {text}'

        reply_text= self.bot( thread_id, prompt, msg_id, channel )
        say( text=reply_text, thread_ts=thread_id, blocks= [
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
            print( '$$$$$$$<message>' )
            print( message )
            print( '$$$$$$$<message>' )

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


#------------------------------------------------------------------------------

def usage():
    print( 'SlackBot v1.00 Hiroyuki Ogasawara' )
    print( 'usage: SlackBot [<options>' )
    print( 'options:' )
    print( '  --preset <preset>             default: chatbot' )
    print( '  --config <config_file>        default: config.txt' )
    print( '  --prompt_dir <dir>' )
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
    slack_bot= SlackBot( SlackBotOptions() )

    app= App( token= os.environ['SLACK_BOT_TOKEN'] )
    app.event('app_mention')( ack=respound_within_3_seconds, lazy=[handle_app_mention_events] )
    app.message()(ack=respound_within_3_seconds, lazy=[handle_message])
    handler= SocketModeHandler( app, os.environ['SLACK_APP_TOKEN'] )
    handler.start()

    return  0

if __name__ == '__main__':
    sys.exit( main( sys.argv ) )


