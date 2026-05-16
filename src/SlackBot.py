# 2026/04/21 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
import time
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.middleware.assistant import Assistant as SlackAssistant

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
import ChatEngine

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
#  App Home
#
#      Message Tab => ON
#          Allow users to send Slash commands and messages from the messages tab => ON  (DM)
#
#  OAuth & Permissions
#
#      BotTokenScope
#
#          app_mention:read
#          assistant:write
#          channels:history
#          channels:read
#          chat:write
#          chat:write.customize
#          emoji:read
#          files:read
#          files:write
#          groups:history
#          groups:read
#          groups:write
#          im:history (DM)
#          im:read (DM)
#          im:write (DM)
#          mpim:history (?)
#          mpim:read (?)
#          mpim:write (?)
#          pins:read (?)
#          pins:write (?)
#          reactions:read
#          reactions:write
#          usergroups:read
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
#          message.im  (DM)
#
#  Install App
#      [Install to Workspace]
#      Bot User OAuth Token      => SLACK_BOT_TOKEN (or SLACK_API_TOKEN)

#------------------------------------------------------------------------------

slack_app= None

#------------------------------------------------------------------------------

def respond_within_3_seconds( ack ):
    ack()

def handle_app_mention_events( body, say, client ):
    global slack_app
    slack_app.event_app_mention( body, say, client )

def handle_message( message, say, client ):
    global slack_app
    slack_app.event_message( message, say, client )

def handle_message_events( body ):
    message_type= body.get( 'type', '' )    # event_callback
    event= body.get( 'event', {} )
    event_type= event.get( 'type', '' )     # message
    subtype= event.get( 'subtype', '' )     # message_deleted/message_changed/bot_message
    channel= event.get( 'channel', '' )     # C0
    ts= event.get( 'ts', '' )
    text= f'receved {message_type} {event_type} {subtype} {channel} {ts}'
    print( text )

#------------------------------------------------------------------------------

def assistant_respond_within_3_seconds( event, set_status ):
    global slack_app
    if not slack_app.is_allowed( event ):
        return
    set_status( status='むむむむ' )

def assistant_handle_app_mention_events( body, say, client ):
    global slack_app
    slack_app.event_app_mention( body, say, client )

def assistant_handle_message( message, say, client ):
    global slack_app
    slack_app.event_message( message, say, client )

def start_assistant_thread( say, set_suggested_prompts ):
    say( 'Hey' )

def respond_in_assistant_thread( payload, say, client, set_status ):
    set_status( status='むむむむ' )
    global slack_app
    slack_app.event_message( payload, say, client )


#------------------------------------------------------------------------------

class SlackBotApp:
    def __init__( self, options ):
        self.options= options
        self.chatbot= ChatEngine.ChatEngine( options )
        global slack_app
        slack_app= self

    def close( self ):
        self.chatbot.close()
        self.chatbot= None

    #--------------------------------------------------------------------------
    # Application

    def get_bottoken( self ):
        return  os.environ.get('SLACK_BOT_TOKEN', os.environ.get('SLACK_API_TOKEN'))

    def app_start( self, app ):
        handler= SocketModeHandler( app, os.environ['SLACK_APP_TOKEN'] )
        handler.start()

    def run_app( self ):
        app= App( token= self.get_bottoken() )
        if not self.options.assistant_mode:
            app.event('app_mention')( ack=respond_within_3_seconds, lazy=[handle_app_mention_events] )
            app.message()(ack=respond_within_3_seconds, lazy=[handle_message])
            app.event('message')(ack=respond_within_3_seconds, lazy=[handle_message_events])
        else:
            app.event('app_mention')( ack=assistant_respond_within_3_seconds, lazy=[assistant_handle_app_mention_events] )
            app.message()(ack=assistant_respond_within_3_seconds, lazy=[assistant_handle_message])
            app.event('message')(ack=respond_within_3_seconds, lazy=[handle_message_events])
            assistant= SlackAssistant()
            assistant.thread_started( start_assistant_thread )
            assistant.user_message( respond_in_assistant_thread )
            app.use( assistant )
        self.app_start( app )

    #--------------------------------------------------------------------------
    # Slack API

    def is_allowed( self, event ):
        channel= event.get( 'channel', '' )
        user= event.get( 'user', '' )
        # DM の場合
        if event.get('channel_type') == 'im':
            if not self.options.dm_enabled:
                print( 'DM not allowed' )
                return  False
            # 許可ユーザーじゃなければ無視
            if user not in self.options.channel_allow_list:
                print( 'Deny <<<< USER %s' % user )
                return  False
            print( 'Allow >>>> USEER %s' % user )
        else:
            # 許可チャンネルじゃなければ無視
            if channel not in self.options.channel_allow_list:
                print( 'Deny <<<< CHANNEL %s' % channel )
                return  False
            print( 'Allow >>>> CHANNEL %s' % channel )
        return  True


    #--------------------------------------------------------------------------
    # Session ID

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

    #--------------------------------------------------------------------------
    # Message

    def send_message( self, say, thread_id, message, client ):
        # bot のメッセージは無視
        if message.get('bot_id'):
            print( 'BOT' )
            return

        if not self.is_allowed( message ):
            return

        channel= message.get( 'channel', '' )
        user= message.get( 'user', '' )

        # すでに返答済み
        msg_id= message.get( 'client_msg_id', '' )
        if self.chatbot.has_message( thread_id, msg_id ):
            return

        thread_ts= self.get_thread_ts( message )

        # Reaction Mark
        ts= message.get( 'ts', '' )
        try:
            reaction_mark= 'robot_face'
            client.reactions_add( channel=channel, timestamp=ts, name=reaction_mark )
        except Exception as e:
            print( f'Error reaction:{e}\n' )

        text= message.get( 'text', '' )
        tsstr= time.strftime( '%Y-%m-%d %H:%M:%S', self.ts_to_local_time( ts ) )
        prompt= f'{tsstr} {user}: {text}'

        msg_info= {
            'channel': channel,
            'thread_ts': thread_ts,
        }

        reply_text= self.chatbot.bot( thread_id, prompt, msg_id, msg_info )
        say( text=reply_text, thread_ts=thread_ts, blocks= [
                {
                    'type': 'markdown',
                    'text': reply_text
                }
            ])

    #--------------------------------------------------------------------------
    # Event

    def event_app_mention( self, body, say, client ):
        if self.options.debug_echo:
            print( '######(mention)' )
            print( body )
            print( '######(mention)' )

        message= body['event']

        # すでに参加済みなら無視
        thread_id= self.get_thread_id( message )
        if self.chatbot.has_session( thread_id ):
            return

        # 途中から参加
        self.send_message( say, thread_id, message, client )

    def event_message( self, message, say, client ):
        if self.options.debug_echo:
            print( '$$$$$$<message>' )
            print( message )
            print( '$$$$$$<message>' )

        # bot のメッセージは無視
        if message.get('bot_id'):
            return

        # Channel の場合会話に参加していないスレッドは無視
        thread_id= self.get_thread_id( message )
        if message.get('channel_type') != 'im':
            if not self.chatbot.has_session( thread_id ):
                return

        self.send_message( say, thread_id, message, client )


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
    print( '  --dm' )
    print( '  --assistant' )
    print( '  --print' )
    print( '  --debug' )
    sys.exit( 1 )


def main( argv ):
    acount= len(argv)
    options= ChatEngine.ChatEngineOptions()
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
            elif arg == '--assistant':
                options.assistant_mode= True
            elif arg == '--dm':
                options.dm_enabled= True
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

    botapp= SlackBotApp( options )
    try:
        botapp.run_app()
    finally:
        botapp.close()
    return  0

if __name__ == '__main__':
    sys.exit( main( sys.argv ) )


