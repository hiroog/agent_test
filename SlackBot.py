# 2026/04/21 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
import Assistant
from OllamaAPI4 import ExecTime
from SlackAPI import save_json, load_json


#------------------------------------------------------------------------------

class SlackBotOptions(Assistant.AssistantOptions):
    def __init__( self, **args ):
        super().__init__()
        self.preset= 'chatbot'
        self.debug_echo= True
        #---------------------------
        self.apply_params( args )


class SlackBot:
    THREAD_FILE= 'thread.json'

    def __init__( self, options ):
        self.thread_map= load_json( self.THREAD_FILE )
        if self.thread_map is None:
            self.thread_map= {}
        self.options= options
        self.assistant= Assistant.Assistant( options )

    def save_threads( self ):
        save_json( self.THREAD_FILE, self.thread_map )

    def reset( self, thread_id ):
        self.thread_map[thread_id]= { 'thread_id': thread_id, 'message_list': [], 'date': ExecTime().get_date(), 'mtime': '' }

    def bot( self, thread_id, message ):
        with ExecTime( 'Generate' ):
            input_obj= {
                'prompt': message,
            }
            if thread_id not in self.thread_map:
                self.reset( thread_id )
            thread_info= self.thread_map[thread_id]
            thread_info['mtime']= ExecTime().get_date()
            message_list= thread_info['message_list']
            response,status_code,prompt= self.assistant.generate_text( input_obj, None, message_list )
        return  response


#------------------------------------------------------------------------------

# SLACK_BOT_TOKEN
# SLACK_APP_TOKEN

app= App( token= os.environ['SLACK_BOT_TOKEN'] )

slack_bot= None

@app.message()
def handle_message( message, say, logger ):
    global slack_bot

    # DMは無視
    if message.get('channel_type') == 'im':
        return

    # botのメッセージは無視
    if message.get('bot_id'):
        return

    prompt= message.get( 'text', '' )

    thread_ts= message.get( 'thread_ts' )
    ts= message.get( 'ts' )
    thread_id= thread_ts or ts

    is_root= not thread_ts or thread_ts == ts
    if is_root:
        slack_bot.reset( thread_id )

    reply_text= slack_bot.bot( thread_id, prompt )
    say( text=reply_text, thread_ts=thread_id )
    logger.info(f'replied to {message["ts"]} in channel {message["channel"]}')


#------------------------------------------------------------------------------

def usage():
    print( 'SlackBot v1.00' )
    sys.exit( 1 )


def main( argv ):
    func_list= []
    acount= len(argv)
    ai= 1
    while ai < acount:
        arg= argv[ai]
        if arg[0] == '-':
            pass
        else:
            usage()

    try:
        global slack_bot
        slack_bot= SlackBot( SlackBotOptions() )
        handler= SocketModeHandler( app, os.environ['SLACK_APP_TOKEN'] )
        handler.start()
    finally:
        slack_bot.save_threads()

    return  0

if __name__ == '__main__':
    sys.exit( main( sys.argv ) )


